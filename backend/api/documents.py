"""Document upload and management endpoints."""
import hashlib
import logging
import re
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, UploadFile, File, HTTPException, status
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
import aiofiles
import fitz  # PyMuPDF

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
        logger.info("="*80)
        logger.info("CLEARING ALL DATA FOR NEW DOCUMENT IMPORT (FRESH START)")
        logger.info("="*80)
        
        # Clear Redis cache (summaries, PDFs, documents, etc.)
        try:
            logger.info("Clearing Redis cache...")
            await cache_service.redis.flushdb()
            logger.info("✓ Redis cache cleared (all keys deleted)")
        except Exception as cache_error:
            logger.error(f"Error clearing Redis cache: {cache_error}")
            # Continue anyway - cache clear failure shouldn't block upload
        
        # Clear database tables (in order to respect foreign key constraints)
        logger.info("Clearing database tables...")
        try:
            # Delete in order to respect foreign keys
            deleted_qa = await db_service.execute("DELETE FROM qa_items")
            deleted_final_qa = await db_service.execute("DELETE FROM final_qa_items")
            deleted_jobs = await db_service.execute("DELETE FROM processing_jobs")
            deleted_docs = await db_service.execute("DELETE FROM documents")
            logger.info(f"✓ Database cleared: qa_items, final_qa_items, processing_jobs, documents")
        except Exception as db_error:
            logger.error(f"Error clearing database: {db_error}")
            # If final_qa_items doesn't exist yet, that's ok
            if "final_qa_items" not in str(db_error):
                raise
        
        logger.info("="*80)
        logger.info("ALL DATA CLEARED - Starting fresh import")
        logger.info("="*80)
        
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
        
        # Cache document metadata (after clearing - this is the ONLY document now)
        await cache_service.set_document(file_hash, doc_data)
        
        logger.info(f"✓ Document uploaded and ready for processing")
        logger.info(f"  Filename: {file.filename}")
        logger.info(f"  Hash: {file_hash[:16]}...")
        logger.info(f"  Total pages: {pdf_info['total_pages']}")
        logger.info(f"  Status: Fresh start with zero existing data")
        
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
    except Exception as e:
        # If check fails, assume old schema
        logger.warning(f"Error checking final_qa_items table: {e}")
        has_final_table = False
    
    if has_final_table:
        # Use new schema with final_qa_items table
        logger.info(f"Querying final_qa_items table for document {document_id}")
        items = await db_service.fetch(
            """
            SELECT id, page_number, line_number, pdf_page_index, answer_end_page, answer_end_line, question, answer, summary, topic, event_date
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
            "topic": item["topic"],
            "event_date": item.get("event_date")  # Include event date if present
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


class QAItemUpdate(BaseModel):
    """Model for updating QA item summary and date."""
    summary: Optional[str] = None
    event_date: Optional[str] = None


@router.patch("/qa-items/{qa_item_id}")
async def update_qa_item(qa_item_id: UUID, update: QAItemUpdate):
    """
    Update a QA item's summary and/or event date.
    
    Args:
        qa_item_id: UUID of the QA item to update
        update: Fields to update (summary, event_date)
    
    Returns:
        Updated QA item
    """
    try:
        # Check if item exists in final_qa_items table
        item = await db_service.fetchrow(
            """
            SELECT id, document_id, page_number, line_number, pdf_page_index, 
                   answer_end_page, answer_end_line, question, answer, summary, 
                   topic, event_date
            FROM final_qa_items
            WHERE id = $1
            """,
            qa_item_id
        )
        
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="QA item not found"
            )
        
        # Build update query dynamically based on provided fields
        update_fields = []
        update_values = []
        param_count = 1
        
        if update.summary is not None:
            update_fields.append(f"summary = ${param_count}")
            update_values.append(update.summary)
            param_count += 1
        
        if update.event_date is not None:
            update_fields.append(f"event_date = ${param_count}")
            update_values.append(update.event_date)
            param_count += 1
        
        if not update_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update"
            )
        
        # Add the ID as the last parameter
        update_values.append(qa_item_id)
        
        # Execute update
        query = f"""
            UPDATE final_qa_items
            SET {', '.join(update_fields)}
            WHERE id = ${param_count}
            RETURNING id, document_id, page_number, line_number, pdf_page_index,
                      answer_end_page, answer_end_line, question, answer, summary,
                      topic, event_date
        """
        
        updated_item = await db_service.fetchrow(query, *update_values)
        
        logger.info(f"Updated QA item {qa_item_id}: {update_fields}")
        
        return {
            "id": str(updated_item["id"]),
            "document_id": str(updated_item["document_id"]),
            "page_number": updated_item["page_number"],
            "line_number": updated_item["line_number"],
            "pdf_page_index": updated_item["pdf_page_index"],
            "end_page": updated_item["answer_end_page"],
            "end_line": updated_item["answer_end_line"],
            "question": updated_item["question"],
            "answer": updated_item["answer"],
            "summary": updated_item["summary"],
            "topic": updated_item["topic"],
            "event_date": updated_item["event_date"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update QA item: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update QA item: {str(e)}"
        )


@router.get("/{document_id}/qa-page-range")
async def get_qa_page_range(document_id: UUID):
    """
    Detect the first and last pages that contain Q&A pairs.
    
    Scans the document to find pages with Q&A patterns and returns
    the range for default page selection.
    
    Returns:
        {
            "first_qa_page": int,
            "last_qa_page": int,
            "total_pages": int
        }
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
    
    file_hash = doc["file_hash"]
    total_pages = doc["total_pages"]
    
    # Get PDF from Redis cache
    pdf_content = await cache_service.get_pdf_content(file_hash)
    if not pdf_content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PDF content not found in cache. Please re-upload the document."
        )
    
    # Save to temporary file for PyMuPDF
    import tempfile
    import os
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
        tmp_path = tmp_file.name
        tmp_file.write(pdf_content)
    
    try:
        # Q/A detection patterns (same as in pdf_service.py)
        question_patterns = [
            re.compile(r'^[·\s]*Q\.[·\s]*', re.IGNORECASE),
            re.compile(r'^\s*Q\.\s*', re.IGNORECASE),
            re.compile(r'^\s*Q:\s*', re.IGNORECASE),
            re.compile(r'^Q\s+[A-Z]', re.IGNORECASE),
            re.compile(r'^\s*QUESTION[:\s]+', re.IGNORECASE),
            re.compile(r'^BY\s+M[RS]\.\s+\w+:', re.IGNORECASE),
        ]
        
        answer_patterns = [
            re.compile(r'^[·\s]*A\.[·\s]*', re.IGNORECASE),
            re.compile(r'^\s*A\.\s*', re.IGNORECASE),
            re.compile(r'^\s*A:\s*', re.IGNORECASE),
            re.compile(r'^A\s+[A-Z]', re.IGNORECASE),
            re.compile(r'^\s*ANSWER[:\s]+', re.IGNORECASE),
            re.compile(r'^[·\s]*THE\s+WITNESS:[·\s]*', re.IGNORECASE),
        ]
        
        def has_qa_pattern(text: str) -> bool:
            """Check if text matches Q&A patterns."""
            text = text.strip()
            if not text:
                return False
            
            for pattern in question_patterns + answer_patterns:
                if pattern.match(text):
                    return True
            return False
        
        # Scan pages to find Q&A ranges
        first_qa_page = None
        last_qa_page = None
        
        doc_pdf = fitz.open(tmp_path)
        
        # Scan first 20 pages to find first Q&A
        for page_num in range(min(20, total_pages)):
            page = doc_pdf[page_num]
            text = page.get_text()
            lines = text.split('\n')
            
            for line in lines:
                if has_qa_pattern(line):
                    first_qa_page = page_num + 1  # 1-based
                    break
            
            if first_qa_page:
                break
        
        # Scan last 20 pages to find last Q&A
        for page_num in range(max(0, total_pages - 20), total_pages):
            page = doc_pdf[page_num]
            text = page.get_text()
            lines = text.split('\n')
            
            for line in lines:
                if has_qa_pattern(line):
                    last_qa_page = page_num + 1  # 1-based
                    # Don't break - keep scanning to find the last one
        
        doc_pdf.close()
        
        # Fallback if no Q&A detected
        if not first_qa_page:
            first_qa_page = 1
        if not last_qa_page:
            last_qa_page = total_pages
        
        logger.info(f"Detected Q&A range: pages {first_qa_page}-{last_qa_page} (total: {total_pages})")
        
        return {
            "first_qa_page": first_qa_page,
            "last_qa_page": last_qa_page,
            "total_pages": total_pages
        }
        
    finally:
        # Clean up temp file
        try:
            os.unlink(tmp_path)
        except:
            pass



