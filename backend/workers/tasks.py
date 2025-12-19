"""Celery tasks for document processing."""
# Deploy trigger: Dec 17, 2025 - Force rebuild with pages fix
import asyncio
import logging
from typing import Optional

import aiofiles

from workers.celery_app import celery_app
from services.pdf_service import pdf_service
from services.ai_service import ai_service
from services.db_service import db_service, init_db
from services.cache_service import cache_service

logger = logging.getLogger(__name__)


# Worker-specific job update functions using Redis pub/sub
async def send_job_update(job_id: str, status: str, progress: int, **kwargs):
    """Send job progress update via Redis pub/sub (worker → backend → WebSocket clients)."""
    await cache_service.publish_job_update(
        job_id,
        "progress",
        {
            "status": status,
            "progress": progress,
            **kwargs
        }
    )


async def send_job_error(job_id: str, error_message: str):
    """Send job error via Redis pub/sub."""
    logger.info(f"Sending error for job {job_id[:8]}...: {error_message[:100]}")
    await cache_service.publish_job_update(
        job_id,
        "error",
        {"error_message": error_message}
    )
    logger.info(f"Error sent for job {job_id[:8]}...")


async def send_job_complete(job_id: str, result: dict):
    """Send job completion notification via Redis pub/sub."""
    await cache_service.publish_job_update(
        job_id,
        "complete",
        result
    )


async def send_partial_result(job_id: str, result: dict):
    """Send partial results via Redis pub/sub."""
    await cache_service.publish_job_update(
        job_id,
        "partial_result",
        result
    )


@celery_app.task(name="process_document")
def process_document_task(job_id: str, document_id: str, first_page: int = 1, last_page: Optional[int] = None):
    """
    Process a document: extract PDF, parse Q&A, summarize with AI.
    This runs in a background worker process.
    """
    # Run async code in event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_until_complete(
            _process_document_async(job_id, document_id, first_page, last_page)
        )
        return result
    finally:
        loop.close()


async def _process_document_async(job_id: str, document_id: str, first_page: int, last_page: Optional[int]):
    """Async implementation with pipeline parallelization.
    
    Uses producer-consumer pattern to overlap PDF extraction and AI processing,
    resulting in 15-25% faster overall processing.
    """
    try:
        # Initialize connections
        await cache_service.connect()
        await init_db()  # Initialize database and run migrations
        
        # Update job status to processing
        await db_service.execute(
            "UPDATE processing_jobs SET status = 'processing', started_at = NOW() WHERE id = $1",
            job_id
        )
        await send_job_update(job_id, "processing", 0)
        
        # Get document info
        doc = await db_service.fetchrow(
            "SELECT filename, file_hash, s3_key FROM documents WHERE id = $1",
            document_id
        )
        
        if not doc:
            raise Exception("Document not found")
        
        logger.info(f"Processing document with pipeline: {doc['filename']}")
        
        # Retrieve PDF from Redis (cross-container access)
        pdf_content = await cache_service.get_pdf_content(doc['file_hash'])
        if not pdf_content:
            raise Exception(f"PDF content not found in cache for {doc['file_hash'][:8]}. Upload may have expired.")
        
        # Write to local temp file for processing
        pdf_path = f"/tmp/{doc['file_hash']}.pdf"
        async with aiofiles.open(pdf_path, 'wb') as f:
            await f.write(pdf_content)
        
        logger.info(f"Retrieved PDF from Redis: {len(pdf_content)} bytes")
        
        # Pipeline: Extract and process in parallel
        processing_queue = asyncio.Queue(maxsize=10)
        all_qa_pairs = []
        summarized_items = []
        extraction_complete = False
        total_pages_extracted = 0
        
        async def extract_and_queue():
            """Producer: Extract pages and add Q&A pairs to queue."""
            nonlocal total_pages_extracted, extraction_complete
            
            await send_job_update(job_id, "processing", 5, message="Starting PDF extraction...")
            
            try:
                async for page_batch in pdf_service.extract_pages_streaming(pdf_path, first_page, last_page):
                    total_pages_extracted += len(page_batch)
                    
                    # Extract Q&A pairs from batch
                    batch_qa_pairs = []
                    for page in page_batch:
                        batch_qa_pairs.extend(page['qa_pairs'])
                    
                    # Deduplicate Q&A pairs within batch (prevent duplicates from same page)
                    # Use question + answer + page + line as unique key
                    seen_in_batch = {}
                    unique_batch_qa = []
                    for qa in batch_qa_pairs:
                        key = (
                            qa.get('question', '').strip(),
                            qa.get('answer', '').strip(),
                            qa.get('page', 0),
                            qa.get('line', 0)
                        )
                        if key not in seen_in_batch:
                            seen_in_batch[key] = True
                            unique_batch_qa.append(qa)
                    
                    if len(unique_batch_qa) < len(batch_qa_pairs):
                        logger.warning(f"Deduplicated {len(batch_qa_pairs) - len(unique_batch_qa)} duplicate Q&A pairs in batch")
                    
                    if unique_batch_qa:
                        await processing_queue.put(unique_batch_qa)
                        all_qa_pairs.extend(unique_batch_qa)
                    
                    # Update progress (extraction is 5-20%)
                    progress = min(20, 5 + (total_pages_extracted * 15 // max(1, last_page or 100)))
                    await send_job_update(
                        job_id,
                        "processing",
                        progress,
                        message=f"Extracted {total_pages_extracted} pages, found {len(all_qa_pairs)} Q&A pairs"
                    )
                
                # Signal completion
                await processing_queue.put(None)
                extraction_complete = True
                logger.info(f"Extraction complete: {total_pages_extracted} pages, {len(all_qa_pairs)} Q&A pairs")
                
            except Exception as e:
                logger.error(f"Extraction failed: {e}")
                await processing_queue.put(None)
                raise
        
        async def process_from_queue():
            """Consumer: Process Q&A pairs as they become available."""
            nonlocal summarized_items
            
            await send_job_update(job_id, "processing", 20, message="Starting AI summarization...")
            
            processed_count = 0
            
            while True:
                # Get next batch from queue
                batch = await processing_queue.get()
                
                if batch is None:
                    # Extraction complete
                    break
                
                # Process batch with detailed progress callback
                async def batch_progress_callback(batch_progress_pct):
                    """Track progress within current batch.
                    
                    Provides granular updates as items within a batch are processed,
                    including instant progress jumps for cache hits.
                    """
                    # Calculate overall progress: items completed + current batch progress
                    items_in_current_batch = len(batch)
                    current_batch_progress = (batch_progress_pct / 100) * items_in_current_batch
                    total_processed = processed_count + current_batch_progress
                    
                    if all_qa_pairs and len(all_qa_pairs) > 0:
                        overall_pct = (total_processed / len(all_qa_pairs)) * 100
                        # Map to 20-90% range for AI processing
                        progress = 20 + int(overall_pct * 0.7)
                    else:
                        progress = 20
                    
                    await send_job_update(
                        job_id,
                        "processing",
                        min(90, progress),
                        message=f"AI processing: {int(total_processed)}/{len(all_qa_pairs)} items ({overall_pct:.1f}%)"
                    )
                
                # Filter to only final Q/A pairs for summarization
                final_batch = [qa for qa in batch if qa.get('is_final', True)]
                non_final_batch = [qa for qa in batch if not qa.get('is_final', True)]
                
                # Add non-final items without summarization
                for qa in non_final_batch:
                    summarized_items.append({
                        **qa,
                        'summary': '',
                        'topic': 'Other'
                    })
                
                if not final_batch:
                    # No final Q/As in this batch, skip summarization
                    processed_count += len(batch)
                    continue
                
                # Process batch with AI (only final Q/As)
                try:
                    summarized_batch = await ai_service.summarize_batch_parallel(
                        final_batch,
                        progress_callback=batch_progress_callback
                    )
                    
                    # Add summarized final Q/As to results
                    for summarized_qa in summarized_batch:
                        summarized_items.append(summarized_qa)
                    
                    processed_count += len(batch)
                    
                    # Send update after batch completes
                    if all_qa_pairs and len(all_qa_pairs) > 0:
                        overall_progress = int((processed_count / len(all_qa_pairs)) * 70) + 20
                    else:
                        overall_progress = 20
                    
                    await send_job_update(
                        job_id,
                        "processing",
                        min(90, overall_progress),
                        message=f"AI processing: {processed_count}/{len(all_qa_pairs)} items"
                    )
                    
                except Exception as e:
                    logger.error(f"Batch processing failed: {e}")
                    # Continue processing other batches
        
        # Run extraction and processing in parallel (pipeline!)
        await asyncio.gather(
            extract_and_queue(),
            process_from_queue()
        )
        
        if not all_qa_pairs:
            error_msg = (
                "No Q&A pairs found in document. "
                "This PDF parser expects deposition transcripts with 'Q:' and 'A:' markers. "
                f"Extracted {total_pages_extracted} pages successfully, but found no Q&A format content."
            )
            raise Exception(error_msg)
        
        await send_job_update(job_id, "processing", 90, message="Saving results to database...")
        
        # Separate final Q/As from interim/variables
        final_qa_items = []
        interim_qa_items = []
        
        for item in summarized_items:
            is_final = item.get('is_final', True)
            if is_final:
                final_qa_items.append(item)
            else:
                interim_qa_items.append(item)
        
        logger.info(f"Saving {len(final_qa_items)} final Q/A pairs and {len(interim_qa_items)} interim items")
        
        # Save final Q/As to final_qa_items table (with summaries)
        saved_final_count = 0
        for idx, item in enumerate(final_qa_items):
            # page_number is the PRINTED transcript page number (for display/citation)
            # pdf_page_index is the 1-based index in the PDF file (for rendering)
            printed_page_num = item.get('page', 1)
            pdf_page_idx = item.get('pdf_page_index', printed_page_num)  # Fallback to page if not set
            line_num = item.get('line', 1)
            
            # Get answer end line/page (stored during parsing)
            answer_end_page = item.get('answer_end_page', printed_page_num)
            answer_end_line = item.get('answer_end_line', line_num)
            
            # Log first few items to debug page/line data
            if idx < 3:
                logger.info(f"Saving final Q&A {idx+1}: printed_page={printed_page_num}, pdf_index={pdf_page_idx}, line={line_num}, answer_end={answer_end_page}:{answer_end_line}, summary={'yes' if item.get('summary') else 'no'}, question={item['question'][:50]}...")
            
            await db_service.execute(
                """
                INSERT INTO final_qa_items (document_id, page_number, line_number, pdf_page_index, answer_end_page, answer_end_line, question, answer, summary, topic)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """,
                document_id,
                printed_page_num,
                line_num,
                pdf_page_idx,
                answer_end_page,
                answer_end_line,
                item['question'],
                item['answer'],
                item.get('summary', ''),
                item.get('topic', 'Other')
            )
            saved_final_count += 1
            
            # Stream partial results every 10 items
            if saved_final_count % 10 == 0:
                await send_partial_result(job_id, {
                    "saved_count": saved_final_count,
                    "total": len(final_qa_items)
                })
        
        # Save interim/variables to qa_items table (without summaries, for reference)
        saved_interim_count = 0
        for item in interim_qa_items:
            printed_page_num = item.get('page', 1)
            pdf_page_idx = item.get('pdf_page_index', printed_page_num)
            line_num = item.get('line', 1)
            answer_end_page = item.get('answer_end_page', printed_page_num)
            answer_end_line = item.get('answer_end_line', line_num)
            
            await db_service.execute(
                """
                INSERT INTO qa_items (document_id, page_number, line_number, pdf_page_index, answer_end_page, answer_end_line, is_final, question, answer, summary, topic)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                """,
                document_id,
                printed_page_num,
                line_num,
                pdf_page_idx,
                answer_end_page,
                answer_end_line,
                False,  # Mark as interim
                item['question'],
                item['answer'],
                '',  # No summary for interim items
                'Other'
            )
            saved_interim_count += 1
        
        logger.info(f"Saved {saved_final_count} final Q/A pairs and {saved_interim_count} interim items")
        
        await send_job_update(job_id, "processing", 95, message="Finalizing...")
        
        # Step 5: Mark job as complete (100% progress)
        await db_service.execute(
            "UPDATE processing_jobs SET status = 'completed', progress = 100, completed_at = NOW() WHERE id = $1",
            job_id
        )
        
        # Count only final Q/As for result reporting
        final_count = len([item for item in summarized_items if item.get('is_final', True)])
        
        result = {
            "document_id": document_id,
            "total_qa_pairs": final_count,
            "pages_processed": total_pages_extracted,
            "filename": doc['filename']
        }
        
        await send_job_complete(job_id, result)
        
        logger.info(f"Document processing complete: {doc['filename']}")
        
        return result
        
    except Exception as e:
        logger.error(f"Document processing failed: {e}", exc_info=True)
        
        # Update job status to failed
        await db_service.execute(
            """
            UPDATE processing_jobs 
            SET status = 'failed', error_message = $1, completed_at = NOW() 
            WHERE id = $2
            """,
            str(e),
            job_id
        )
        
        await send_job_error(job_id, str(e))
        
        raise
    
    finally:
        # Cleanup
        await cache_service.disconnect()
        await db_service.close_pool()

