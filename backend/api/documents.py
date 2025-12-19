"""Document upload and management endpoints."""
import hashlib
import logging
from typing import List
from uuid import UUID

from fastapi import APIRouter, UploadFile, File, HTTPException, status
from fastapi.responses import JSONResponse, Response
import aiofiles

from services.db_service import db_service
from services.cache_service import cache_service
from services.pdf_service import pdf_service
from models.document import Document, DocumentCreate, DocumentResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(file: UploadFile = File(...)):
    """
    Upload a PDF document and extract basic metadata.
    Returns document ID for subsequent processing.
    """
    if not file.filename.endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported"
        )
    
    try:
        # Read file content
        content = await file.read()
        file_hash = hashlib.sha256(content).hexdigest()
        
        # Check if document already exists
        cached_doc = await cache_service.get_document(file_hash)
        if cached_doc:
            logger.info(f"Document already processed: {file_hash[:8]}...")
            # Still store PDF content for worker access (may have expired)
            await cache_service.set_pdf_content(file_hash, content, ttl_hours=24)
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "message": "Document already exists",
                    "document_id": cached_doc["id"],
                    "cached": True
                }
            )
        
        # Check database
        existing = await db_service.fetchrow(
            "SELECT id, filename, total_pages, created_at FROM documents WHERE file_hash = $1",
            file_hash
        )
        
        if existing:
            logger.info(f"Document found in database: {file_hash[:8]}...")
            doc_data = {
                "id": str(existing["id"]),
                "filename": existing["filename"],
                "file_hash": file_hash,
                "total_pages": existing["total_pages"],
                "created_at": existing["created_at"].isoformat()
            }
            await cache_service.set_document(file_hash, doc_data)
            # Store PDF content for worker access (may have expired)
            await cache_service.set_pdf_content(file_hash, content, ttl_hours=24)
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "message": "Document already exists",
                    "document_id": str(existing["id"]),
                    "cached": False
                }
            )
        
        # SECURITY: Clear all existing data before processing new document
        # This ensures data isolation between different users/documents
        # Each transcript stands alone and should not contain data from previous imports
        logger.info("Clearing all existing data for new document import...")
        
        # Clear database tables (in order to respect foreign key constraints)
        await db_service.execute("DELETE FROM qa_items")
        await db_service.execute("DELETE FROM processing_jobs")
        await db_service.execute("DELETE FROM documents")
        
        # Clear Redis cache to remove any cached document data
        # Note: We keep summary_cache as it's content-based and can be safely reused
        try:
            # Clear document cache (we'll use a pattern if available, otherwise manual clear)
            # For now, we'll let cache expire naturally, but document will be overwritten below
            logger.info("Cache will be overwritten with new document data")
        except Exception as e:
            logger.warning(f"Cache clear warning (non-critical): {e}")
        
        logger.info("All existing documents, Q&A items, and jobs cleared")
        
        # Save to temporary location for processing
        temp_path = f"/tmp/upload_{file_hash[:16]}.pdf"
        async with aiofiles.open(temp_path, 'wb') as f:
            await f.write(content)
        
        # Extract basic PDF info
        pdf_info = await pdf_service.get_pdf_info(temp_path)
        
        # Store PDF content in Redis for worker access (24hr TTL)
        # This allows workers in different containers to access the file
        await cache_service.set_pdf_content(file_hash, content, ttl_hours=24)
        
        # Store in database
        doc_id = await db_service.fetchval(
            """
            INSERT INTO documents (filename, file_hash, s3_key, total_pages)
            VALUES ($1, $2, $3, $4)
            RETURNING id
            """,
            file.filename,
            file_hash,
            f"documents/{file_hash}.pdf",
            pdf_info["total_pages"]
        )
        
        doc_data = {
            "id": str(doc_id),
            "filename": file.filename,
            "file_hash": file_hash,
            "total_pages": pdf_info["total_pages"]
        }
        
        # Cache document metadata
        await cache_service.set_document(file_hash, doc_data)
        
        logger.info(f"New document uploaded: {file.filename} ({file_hash[:8]}...)")
        
        return {
            "document_id": str(doc_id),
            "filename": file.filename,
            "total_pages": pdf_info["total_pages"],
            "file_hash": file_hash
        }
        
    except Exception as e:
        logger.error(f"Document upload failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process document: {str(e)}"
        )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: UUID):
    """Get document metadata by ID."""
    doc = await db_service.fetchrow(
        "SELECT * FROM documents WHERE id = $1",
        document_id
    )
    
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    return {
        "document_id": str(doc["id"]),
        "filename": doc["filename"],
        "total_pages": doc["total_pages"],
        "file_hash": doc["file_hash"],
        "created_at": doc["created_at"].isoformat()
    }


@router.get("/{document_id}/qa-items")
async def get_qa_items(document_id: UUID):
    """Get all Q&A items for a document with line range information.
    
    Each item includes start and end positions for citation formatting.
    End positions are calculated based on the next Q&A item's start position.
    
    Returns:
        - page_number: The PRINTED transcript page number (for display/citation)
        - pdf_page_index: The 1-based index in the PDF file (for rendering)
    """
    items = await db_service.fetch(
        """
        SELECT id, page_number, line_number, pdf_page_index, question, answer, summary, topic
        FROM qa_items
        WHERE document_id = $1
        ORDER BY page_number, line_number
        """,
        document_id
    )
    
    # Convert to list for range calculation
    items_list = list(items)
    qa_items_with_ranges = []
    
    for i, item in enumerate(items_list):
        # Calculate end line/page based on next item's position
        if i + 1 < len(items_list):
            next_item = items_list[i + 1]
            if next_item["page_number"] == item["page_number"]:
                # Same page: end line is one before next item's start
                end_page = item["page_number"]
                end_line = max(item["line_number"], next_item["line_number"] - 1)
            else:
                # Different page: current item goes to end of its page
                end_page = item["page_number"]
                end_line = 25  # Legal transcript standard lines per page
        else:
            # Last item: goes to end of page
            end_page = item["page_number"]
            end_line = 25
        
        # Use pdf_page_index if available, fallback to page_number for old data
        pdf_idx = item.get("pdf_page_index") or item["page_number"]
        
        qa_items_with_ranges.append({
            "id": str(item["id"]),
            "page_number": item["page_number"],  # Printed transcript page (for citation)
            "pdf_page_index": pdf_idx,           # PDF index (for rendering)
            "line_number": item["line_number"],
            "end_page": end_page,
            "end_line": end_line,
            "question": item["question"],
            "answer": item["answer"],
            "summary": item["summary"],
            "topic": item["topic"]
        })
    
    return {
        "document_id": str(document_id),
        "qa_items": qa_items_with_ranges
    }


@router.get("/{document_id}/page/{page_number}")
async def get_pdf_page(document_id: UUID, page_number: int):
    """Render a specific PDF page as an image for reading mode.
    
    Returns the page as a PNG image with appropriate headers.
    """
    # Get document to find file hash
    doc = await db_service.fetchrow(
        "SELECT file_hash, total_pages FROM documents WHERE id = $1",
        document_id
    )
    
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    if page_number < 1 or page_number > doc["total_pages"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Page {page_number} out of range (1-{doc['total_pages']})"
        )
    
    # Get PDF content from cache
    pdf_content = await cache_service.get_pdf_content(doc["file_hash"])
    
    if not pdf_content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PDF content not found in cache. Document may need to be re-uploaded."
        )
    
    try:
        # Write to temp file for rendering
        temp_path = f"/tmp/render_{doc['file_hash'][:16]}.pdf"
        async with aiofiles.open(temp_path, 'wb') as f:
            await f.write(pdf_content)
        
        # Render page
        result = await pdf_service.render_page_as_image(temp_path, page_number, scale=2.0)
        
        # Return image with metadata headers
        return Response(
            content=result["image"],
            media_type="image/png",
            headers={
                "X-Page-Number": str(result["page_number"]),
                "X-Total-Pages": str(result["total_pages"]),
                "X-Image-Width": str(result["width"]),
                "X-Image-Height": str(result["height"]),
                "X-Original-Width": str(result["original_width"]),
                "X-Original-Height": str(result["original_height"]),
                "Cache-Control": "public, max-age=3600"  # Cache for 1 hour
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to render page {page_number}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to render page: {str(e)}"
        )


