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
        
        # SECURITY: ALWAYS clear all existing data before processing ANY document upload
        # This ensures data isolation and fresh start for every upload, even if same file
        # Each transcript import should start completely fresh with zero data
        logger.info("Clearing all existing data for document import (fresh start)...")
        
        # Clear database tables (in order to respect foreign key constraints)
        await db_service.execute("DELETE FROM qa_items")
        await db_service.execute("DELETE FROM processing_jobs")
        await db_service.execute("DELETE FROM documents")
        
        logger.info("All existing documents, Q&A items, and jobs cleared - starting fresh")
        
        # Save to temporary location for processing
        temp_path = f"/tmp/upload_{file_hash[:16]}.pdf"
        async with aiofiles.open(temp_path, 'wb') as f:
            await f.write(content)
        
        # Extract basic PDF info
        pdf_info = await pdf_service.get_pdf_info(temp_path)
        
        # Store PDF content in Redis for worker access (24hr TTL)
        # This allows workers in different containers to access the file
        await cache_service.set_pdf_content(file_hash, content, ttl_hours=24)
        
        # Always create a new document entry (database was cleared above)
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
        
        logger.info(f"Document uploaded and ready for processing: {file.filename} ({file_hash[:8]}...) - Fresh start with zero existing data")
        
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
    """Get all FINAL Q&A items for a document with line range information.
    
    Returns Q&A items from the final_qa_items table, which contains only
    complete final Q/A pairs with summaries. Interim/variable items are
    stored separately in qa_items table and are not returned here.
    
    Each item includes start and end positions for citation formatting.
    End positions use the stored answer_end_line/answer_end_page from parsing,
    falling back to calculated values for backward compatibility.
    
    Returns:
        - page_number: The PRINTED transcript page number (for display/citation)
        - pdf_page_index: The 1-based index in the PDF file (for rendering)
        - end_page/end_line: Where the answer ends (from stored data)
    """
    # Check if final_qa_items table exists and has data
    has_final_table = False
    try:
        table_check = await db_service.fetchval(
            """
            SELECT COUNT(*) FROM information_schema.tables 
            WHERE table_name = 'final_qa_items'
            """
        )
        has_final_table = table_check > 0
        
        # Also check if table has any rows for this document
        if has_final_table:
            row_count = await db_service.fetchval(
                """
                SELECT COUNT(*) FROM final_qa_items WHERE document_id = $1
                """,
                document_id
            )
            logger.info(f"final_qa_items table exists with {row_count} rows for document {document_id}")
            if row_count == 0:
                # Table exists but empty - check old table and migrate if needed
                logger.warning(f"final_qa_items table is empty for document {document_id}, checking qa_items table")
                # Try to migrate data from qa_items to final_qa_items
                try:
                    old_items = await db_service.fetch(
                        """
                        SELECT id, page_number, line_number, pdf_page_index, answer_end_page, answer_end_line, question, answer, summary, topic, is_final
                        FROM qa_items
                        WHERE document_id = $1 AND (is_final IS NULL OR is_final = TRUE)
                        ORDER BY page_number, line_number
                        """,
                        document_id
                    )
                    if old_items and len(old_items) > 0:
                        logger.info(f"Found {len(old_items)} items in qa_items table, migrating to final_qa_items")
                        # Migrate items to final_qa_items
                        for old_item in old_items:
                            await db_service.execute(
                                """
                                INSERT INTO final_qa_items (document_id, page_number, line_number, pdf_page_index, answer_end_page, answer_end_line, question, answer, summary, topic)
                                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                                ON CONFLICT DO NOTHING
                                """,
                                document_id,
                                old_item.get('page_number'),
                                old_item.get('line_number'),
                                old_item.get('pdf_page_index'),
                                old_item.get('answer_end_page'),
                                old_item.get('answer_end_line'),
                                old_item.get('question'),
                                old_item.get('answer'),
                                old_item.get('summary') or '',
                                old_item.get('topic') or 'Other'
                            )
                        logger.info(f"Migrated {len(old_items)} items to final_qa_items")
                        # Re-query final_qa_items
                        items = await db_service.fetch(
                            """
                            SELECT id, page_number, line_number, pdf_page_index, answer_end_page, answer_end_line, question, answer, summary, topic
                            FROM final_qa_items
                            WHERE document_id = $1
                            ORDER BY page_number, line_number
                            """,
                            document_id
                        )
                        logger.info(f"After migration: Retrieved {len(items)} items from final_qa_items table")
                    else:
                        logger.warning(f"No items found in qa_items table either for document {document_id}")
                except Exception as migrate_error:
                    logger.error(f"Error migrating data: {migrate_error}")
                    # Fall through to use old table
                    has_final_table = False
    except Exception as e:
        # If check fails, assume old schema
        logger.warning(f"Error checking final_qa_items table: {e}")
        has_final_table = False
    
    if has_final_table:
        # Use new schema with final_qa_items table
        logger.info(f"Querying final_qa_items table for document {document_id}")
        items = await db_service.fetch(
            """
            SELECT id, page_number, line_number, pdf_page_index, answer_end_page, answer_end_line, question, answer, summary, topic
            FROM final_qa_items
            WHERE document_id = $1
            ORDER BY page_number, line_number
            """,
            document_id
        )
        logger.info(f"Retrieved {len(items)} items from final_qa_items table")
        
        # If table is empty, try to migrate from old table
        if len(items) == 0:
            logger.warning(f"final_qa_items table is empty for document {document_id}, attempting migration from qa_items")
            try:
                old_items = await db_service.fetch(
                    """
                    SELECT id, page_number, line_number, pdf_page_index, answer_end_page, answer_end_line, question, answer, summary, topic, is_final
                    FROM qa_items
                    WHERE document_id = $1 AND (is_final IS NULL OR is_final = TRUE)
                    ORDER BY page_number, line_number
                    """,
                    document_id
                )
                if old_items and len(old_items) > 0:
                    logger.info(f"Found {len(old_items)} items in qa_items table, migrating to final_qa_items")
                    # Migrate items to final_qa_items
                    migrated_count = 0
                    for old_item in old_items:
                        try:
                            await db_service.execute(
                                """
                                INSERT INTO final_qa_items (document_id, page_number, line_number, pdf_page_index, answer_end_page, answer_end_line, question, answer, summary, topic)
                                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                                ON CONFLICT DO NOTHING
                                """,
                                document_id,
                                old_item.get('page_number'),
                                old_item.get('line_number'),
                                old_item.get('pdf_page_index'),
                                old_item.get('answer_end_page'),
                                old_item.get('answer_end_line'),
                                old_item.get('question'),
                                old_item.get('answer'),
                                old_item.get('summary') or '',
                                old_item.get('topic') or 'Other'
                            )
                            migrated_count += 1
                        except Exception as insert_error:
                            logger.error(f"Error inserting item during migration: {insert_error}")
                    logger.info(f"Migrated {migrated_count} items to final_qa_items")
                    # Re-query final_qa_items
                    items = await db_service.fetch(
                        """
                        SELECT id, page_number, line_number, pdf_page_index, answer_end_page, answer_end_line, question, answer, summary, topic
                        FROM final_qa_items
                        WHERE document_id = $1
                        ORDER BY page_number, line_number
                        """,
                        document_id
                    )
                    logger.info(f"After migration: Retrieved {len(items)} items from final_qa_items table")
                else:
                    logger.warning(f"No items found in qa_items table either for document {document_id}")
            except Exception as migrate_error:
                logger.error(f"Error during migration: {migrate_error}")
        
        # Log summary status for first few items
        for idx, item in enumerate(items[:5]):
            has_summary = bool(item.get('summary'))
            logger.info(f"Item {idx+1}: page={item.get('page_number')}, line={item.get('line_number')}, summary={'present' if has_summary else 'MISSING'}, summary_preview={item.get('summary', '')[:50] if has_summary else 'N/A'}...")
    else:
        # Fallback: use old schema (final_qa_items table doesn't exist yet)
        logger.info("Using fallback query - final_qa_items table not yet migrated")
        # Check if is_final column exists
        try:
            column_check = await db_service.fetchval(
                """
                SELECT COUNT(*) FROM information_schema.columns 
                WHERE table_name = 'qa_items' AND column_name = 'is_final'
                """
            )
            has_is_final = column_check > 0
        except Exception:
            has_is_final = False
        
        if has_is_final:
            # Use qa_items with is_final filter
            items = await db_service.fetch(
                """
                SELECT id, page_number, line_number, pdf_page_index, answer_end_page, answer_end_line, question, answer, summary, topic
                FROM qa_items
                WHERE document_id = $1 AND (is_final IS NULL OR is_final = TRUE)
                ORDER BY page_number, line_number
                """,
                document_id
            )
        else:
            # Oldest schema - no is_final column
            items = await db_service.fetch(
                """
                SELECT id, page_number, line_number, pdf_page_index, question, answer, summary, topic
                FROM qa_items
                WHERE document_id = $1
                ORDER BY page_number, line_number
                """,
                document_id
            )
            # Add missing columns with None values
            items = [
                {
                    **item,
                    "answer_end_page": None,
                    "answer_end_line": None
                }
                for item in items
            ]
    
    # Convert to list
    items_list = list(items)
    qa_items_with_ranges = []
    
    for item in items_list:
        # Use stored answer_end_line/answer_end_page if available
        # Fall back to calculated values for backward compatibility
        if item.get("answer_end_page") is not None and item.get("answer_end_line") is not None:
            end_page = item["answer_end_page"]
            end_line = item["answer_end_line"]
        else:
            # Fallback: Calculate based on next item's position (backward compatibility)
            end_page = item["page_number"]
            end_line = None
            
            # Look for the next item on the same page
            item_index = items_list.index(item)
            for j in range(item_index + 1, len(items_list)):
                next_item = items_list[j]
                if next_item["page_number"] == item["page_number"]:
                    # Found next item on same page: end line is one before its start
                    end_line = next_item["line_number"] - 1
                    break
            
            # If no next item on same page found
            if end_line is None:
                if item_index + 1 < len(items_list):
                    # Next item is on a different page: current item goes to end of its page
                    end_line = 25  # Legal transcript standard lines per page
                else:
                    # Last item: goes to end of page
                    end_line = 25
            
            # Ensure end_line is at least the start line (safety check)
            if end_line < item["line_number"]:
                end_line = item["line_number"]
        
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
    
    result = {
        "document_id": str(document_id),
        "qa_items": qa_items_with_ranges
    }
    
    # Log final result summary
    total_items = len(qa_items_with_ranges)
    items_with_summaries = sum(1 for item in qa_items_with_ranges if item.get('summary') and item.get('summary').strip())
    logger.info(f"API Response: {total_items} total items, {items_with_summaries} with summaries ({items_with_summaries/total_items*100:.1f}%)")
    
    return result


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


