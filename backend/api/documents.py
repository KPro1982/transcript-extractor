"""Document upload and management endpoints."""
import hashlib
import logging
from typing import List
from uuid import UUID

from fastapi import APIRouter, UploadFile, File, HTTPException, status
from fastapi.responses import JSONResponse
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
    """Get all Q&A items for a document."""
    items = await db_service.fetch(
        """
        SELECT id, page_number, line_number, question, answer, summary, topic
        FROM qa_items
        WHERE document_id = $1
        ORDER BY page_number, line_number
        """,
        document_id
    )
    
    return {
        "document_id": str(document_id),
        "qa_items": [
            {
                "id": str(item["id"]),
                "page_number": item["page_number"],
                "line_number": item["line_number"],
                "question": item["question"],
                "answer": item["answer"],
                "summary": item["summary"],
                "topic": item["topic"]
            }
            for item in items
        ]
    }


