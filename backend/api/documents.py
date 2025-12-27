"""Document upload and management endpoints."""
import hashlib
import logging
import re
from typing import List, Optional
from uuid import UUID
import os

from fastapi import APIRouter, UploadFile, File, HTTPException, status, Query
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
import aiofiles
import fitz  # PyMuPDF

from services.db_service import db_service
from services.cache_service import cache_service
from services.pdf_service import pdf_service
from services.case_info_extractor import case_info_extractor
from services.page_classifier import page_classifier
from services.qa_test_service import qa_test_service
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
        
        # Extract case information from first 10 pages
        logger.info("Extracting case information...")
        case_info = case_info_extractor.extract_case_info(temp_path, max_pages=10)
        logger.info(f"Case info extracted: {case_info}")
        
        # Classify document pages (fast page-by-page analysis)
        logger.info("Classifying document pages...")
        classification_result = await page_classifier.classify_document(
            temp_path, 
            file_hash,  # Use file_hash as temporary ID
            verbose=True  # Always verbose for diagnostics
        )
        logger.info(
            f"Page classification complete: "
            f"{classification_result['frontpages_count']} frontpages, "
            f"{classification_result['examination_count']} examination, "
            f"{classification_result['backpages_count']} backpages"
        )
        if classification_result.get('log_file'):
            logger.info(f"Classification log: {classification_result['log_file']}")
        
        # Store PDF content in Redis for worker access (24hr TTL)
        # This allows workers in different containers to access the file
        await cache_service.set_pdf_content(file_hash, content, ttl_hours=24)
        
        # Always create a new document entry (database was cleared above)
        doc_id = await db_service.fetchval(
            """
            INSERT INTO documents (
                filename, file_hash, s3_key, total_pages,
                case_name, case_number, deposition_date, attorneys, witness_name,
                examination_first_page, examination_last_page, 
                examination_detection_confidence
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            RETURNING id
            """,
            file.filename,
            file_hash,
            f"documents/{file_hash}.pdf",
            pdf_info["total_pages"],
            case_info.get('case_name'),
            case_info.get('case_number'),
            case_info.get('deposition_date'),
            case_info.get('attorneys', []),
            case_info.get('witness_name'),
            classification_result['examination_first_page'],
            classification_result['examination_last_page'],
            'high'  # Page classifier always has high confidence (explicit Q+A check)
        )
        
        # Store page classifications in database
        await page_classifier.store_classifications(str(doc_id), classification_result)
        
        # Run Q/A extraction test
        qa_test_result = None
        test_first_page = None
        test_last_page = None
        
        # Try examination section first
        if classification_result['examination_first_page'] and classification_result['examination_count'] > 0:
            test_first_page = classification_result['examination_first_page']
            test_last_page = classification_result['examination_last_page']
            logger.info(f"Running Q/A extraction test on examination section (pages {test_first_page}-{test_last_page})...")
        else:
            # Fallback: Use qa-page-range detection
            logger.info("No examination section detected - trying qa-page-range detection...")
            try:
                # Use the same detection logic as get_qa_page_range endpoint
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
                    text = text.strip()
                    if not text:
                        return False
                    for pattern in question_patterns + answer_patterns:
                        if pattern.match(text):
                            return True
                    return False
                
                def page_has_qa(page) -> bool:
                    text = page.get_text()
                    lines = text.split('\n')
                    for line in lines:
                        if has_qa_pattern(line):
                            return True
                    return False
                
                doc_pdf = fitz.open(temp_path)
                
                # Find first page with Q&A
                first_qa_page = None
                for page_num in range(min(30, pdf_info["total_pages"])):
                    page = doc_pdf[page_num]
                    if page_has_qa(page):
                        first_qa_page = page_num + 1
                        break
                
                if first_qa_page:
                    # Find last page of continuous Q&A range
                    last_qa_page = first_qa_page
                    consecutive_empty_pages = 0
                    max_gap = 2
                    
                    for page_num in range(first_qa_page - 1, pdf_info["total_pages"]):
                        page = doc_pdf[page_num]
                        if page_has_qa(page):
                            last_qa_page = page_num + 1
                            consecutive_empty_pages = 0
                        else:
                            consecutive_empty_pages += 1
                            if consecutive_empty_pages >= max_gap:
                                break
                    
                    test_first_page = first_qa_page
                    test_last_page = last_qa_page
                    logger.info(f"Found Q&A range via qa-page-range: pages {test_first_page}-{test_last_page}")
                else:
                    logger.warning("No Q&A pages found via qa-page-range detection")
                
                doc_pdf.close()
            except Exception as e:
                logger.error(f"Error detecting Q&A range: {e}", exc_info=True)
        
        # Run Q/A test if we found a range
        if test_first_page and test_last_page:
            qa_test_result = await qa_test_service.test_qa_extraction(
                temp_path,
                str(doc_id),
                test_first_page,
                test_last_page
            )
            
            if qa_test_result['success']:
                logger.info(
                    f"✅ Q/A extraction test PASSED: {qa_test_result['qa_pairs_found']} pairs found"
                )
                logger.info(f"   Test log: {qa_test_result['log_file']}")
            else:
                logger.warning(
                    f"⚠️  Q/A extraction test FAILED: {', '.join(qa_test_result['errors'])}"
                )
                if qa_test_result['log_file']:
                    logger.warning(f"   Test log: {qa_test_result['log_file']}")
            
            # Update document with Q/A test log file path
            if qa_test_result and qa_test_result.get('log_file'):
                await db_service.execute(
                    """
                    UPDATE documents 
                    SET qa_test_log_file = $1 
                    WHERE id = $2
                    """,
                    qa_test_result['log_file'],
                    doc_id
                )
        else:
            logger.warning("No Q&A range detected - skipping Q/A extraction test")
        
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
        
        response_data = {
            "document_id": str(doc_id),
            "filename": file.filename,
            "total_pages": pdf_info["total_pages"],
            "file_hash": file_hash,
            "case_name": case_info.get('case_name'),
            "case_number": case_info.get('case_number'),
            "deposition_date": case_info.get('deposition_date'),
            "attorneys": case_info.get('attorneys', []),
            "witness_name": case_info.get('witness_name'),
            "examination_first_page": classification_result['examination_first_page'],
            "examination_last_page": classification_result['examination_last_page'],
            "examination_detection_confidence": 'high',
            "frontpages_count": classification_result['frontpages_count'],
            "examination_count": classification_result['examination_count'],
            "backpages_count": classification_result['backpages_count']
        }
        
        # Add Q/A test results if available
        if qa_test_result:
            response_data['qa_test_passed'] = qa_test_result['success']
            response_data['qa_test_pairs_found'] = qa_test_result['qa_pairs_found']
            response_data['qa_test_log_file'] = qa_test_result['log_file']
            if qa_test_result['errors']:
                response_data['qa_test_errors'] = qa_test_result['errors']
        
        return response_data
        
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
    
    # Get classification counts from page_classifications table
    classification_counts = await db_service.fetchrow(
        """
        SELECT 
            COUNT(*) FILTER (WHERE classification = 'frontpages') as frontpages_count,
            COUNT(*) FILTER (WHERE classification = 'examination') as examination_count,
            COUNT(*) FILTER (WHERE classification = 'backpages') as backpages_count
        FROM page_classifications
        WHERE document_id = $1
        """,
        document_id
    )
    
    return {
        "document_id": str(doc["id"]),
        "filename": doc["filename"],
        "total_pages": doc["total_pages"],
        "file_hash": doc["file_hash"],
        "case_name": doc.get("case_name"),
        "case_number": doc.get("case_number"),
        "deposition_date": doc.get("deposition_date"),
        "attorneys": doc.get("attorneys"),
        "witness_name": doc.get("witness_name"),
        "created_at": doc["created_at"].isoformat(),
        "examination_first_page": doc.get("examination_first_page"),
        "examination_last_page": doc.get("examination_last_page"),
        "examination_detection_confidence": doc.get("examination_detection_confidence"),
        "qa_test_log_file": doc.get("qa_test_log_file"),
        "frontpages_count": classification_counts['frontpages_count'] if classification_counts else 0,
        "examination_count": classification_counts['examination_count'] if classification_counts else 0,
        "backpages_count": classification_counts['backpages_count'] if classification_counts else 0
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


class CaseInfoUpdate(BaseModel):
    """Model for updating case information."""
    case_name: Optional[str] = None
    case_number: Optional[str] = None
    deposition_date: Optional[str] = None
    attorneys: Optional[List[str]] = None
    witness_name: Optional[str] = None


@router.patch("/{document_id}/case-info")
async def update_case_info(document_id: UUID, update: CaseInfoUpdate):
    """
    Update case information for a document.
    
    Args:
        document_id: UUID of the document to update
        update: Fields to update (any subset of case info fields)
    
    Returns:
        Updated document with case info
    """
    try:
        # Check if document exists
        doc = await db_service.fetchrow(
            "SELECT id FROM documents WHERE id = $1",
            document_id
        )
        
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        # Build dynamic UPDATE query for provided fields
        update_fields = []
        update_values = []
        param_num = 1
        
        if update.case_name is not None:
            update_fields.append(f"case_name = ${param_num}")
            update_values.append(update.case_name)
            param_num += 1
        
        if update.case_number is not None:
            update_fields.append(f"case_number = ${param_num}")
            update_values.append(update.case_number)
            param_num += 1
        
        if update.deposition_date is not None:
            update_fields.append(f"deposition_date = ${param_num}")
            update_values.append(update.deposition_date)
            param_num += 1
        
        if update.attorneys is not None:
            update_fields.append(f"attorneys = ${param_num}")
            update_values.append(update.attorneys)
            param_num += 1
        
        if update.witness_name is not None:
            update_fields.append(f"witness_name = ${param_num}")
            update_values.append(update.witness_name)
            param_num += 1
        
        if not update_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields provided to update"
            )
        
        # Execute update
        update_values.append(document_id)
        query = f"""
            UPDATE documents
            SET {', '.join(update_fields)}
            WHERE id = ${param_num}
            RETURNING *
        """
        
        updated_doc = await db_service.fetchrow(query, *update_values)
        
        logger.info(f"Updated case info for document {document_id}")
        
        return {
            "document_id": str(updated_doc["id"]),
            "filename": updated_doc["filename"],
            "total_pages": updated_doc["total_pages"],
            "file_hash": updated_doc["file_hash"],
            "case_name": updated_doc.get("case_name"),
            "case_number": updated_doc.get("case_number"),
            "deposition_date": updated_doc.get("deposition_date"),
            "attorneys": updated_doc.get("attorneys"),
            "witness_name": updated_doc.get("witness_name"),
            "created_at": updated_doc["created_at"].isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update case info: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update case info: {str(e)}"
        )


@router.get("/{document_id}/qa-page-range")
async def get_qa_page_range(document_id: UUID):
    """
    Detect the first and last pages of the continuous Q&A range.
    
    Scans forward from the beginning to find:
    1. First page with Q&A patterns (start of testimony)
    2. Continues forward until finding a page WITHOUT Q&A patterns
    3. The page before the gap is the last Q&A page
    
    This correctly handles:
    - Cover pages, indexes before testimony
    - Certificate pages, signature pages after testimony
    - Pages that are entirely answer continuations (bounded by Q/A markers)
    
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
        
        def page_has_qa(page) -> bool:
            """Check if a page has any Q&A patterns."""
            text = page.get_text()
            lines = text.split('\n')
            
            for line in lines:
                if has_qa_pattern(line):
                    return True
            return False
        
        doc_pdf = fitz.open(tmp_path)
        
        # Find first page with Q&A (scan up to first 30 pages)
        first_qa_page = None
        for page_num in range(min(30, total_pages)):
            page = doc_pdf[page_num]
            if page_has_qa(page):
                first_qa_page = page_num + 1  # 1-based
                logger.info(f"Found first Q&A on page {first_qa_page}")
                break
        
        # If no Q&A found in first 30 pages, default to page 1
        if not first_qa_page:
            logger.warning("No Q&A patterns found in first 30 pages, defaulting to page 1")
            first_qa_page = 1
            last_qa_page = total_pages
        else:
            # Find last page of continuous Q&A range
            # Scan forward from first_qa_page until we find a page WITHOUT Q&A
            last_qa_page = first_qa_page
            consecutive_empty_pages = 0
            max_gap = 2  # Allow up to 2 consecutive pages without Q/A (for long answer continuations)
            
            for page_num in range(first_qa_page, total_pages):  # 1-based to 0-based
                page = doc_pdf[page_num]
                
                if page_has_qa(page):
                    # Found Q&A - update last page and reset gap counter
                    last_qa_page = page_num + 1  # 1-based
                    consecutive_empty_pages = 0
                else:
                    # No Q&A on this page
                    consecutive_empty_pages += 1
                    
                    # If we've seen multiple consecutive pages without Q&A, we've hit the end
                    if consecutive_empty_pages >= max_gap:
                        logger.info(f"Found {consecutive_empty_pages} consecutive pages without Q&A after page {last_qa_page}")
                        break
            
            logger.info(f"Last Q&A page in continuous range: {last_qa_page}")
        
        doc_pdf.close()
        
        logger.info(f"Detected continuous Q&A range: pages {first_qa_page}-{last_qa_page} (total: {total_pages})")
        
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


@router.get("/qa-test-log")
async def get_qa_test_log(log_file: str = Query(..., description="Path to the log file")):
    """
    Retrieve Q/A test log content.
    
    Args:
        log_file: Path to the log file (from upload response)
        
    Returns:
        Plain text content of the log file
    """
    try:
        # Security: only allow files in /tmp/ with qa_test_ prefix
        if not log_file.startswith('/tmp/qa_test_') or '..' in log_file:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid log file path"
            )
        
        # Check if file exists
        if not os.path.exists(log_file):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Log file not found. It may have been cleaned up."
            )
        
        # Read file content
        async with aiofiles.open(log_file, 'r', encoding='utf-8') as f:
            content = await f.read()
        
        return Response(
            content=content,
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to read log file: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read log file: {str(e)}"
        )



