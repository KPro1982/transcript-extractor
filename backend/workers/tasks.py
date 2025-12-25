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
from services.people_extraction_service import people_extraction_service
from workers.chunk_coordinator import (
    update_chunk_progress, 
    mark_chunk_complete, 
    mark_chunk_failed,
    get_chunk_job_info
)

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
def process_document_task(job_id: str, document_id: str, first_page: int = 1, last_page: Optional[int] = None, user_id: Optional[str] = None):
    """
    Process a document: extract PDF, parse Q&A, summarize with AI.
    This runs in a background worker process.
    
    Args:
        job_id: UUID of the processing job
        document_id: UUID of the document to process
        first_page: First page to process (1-indexed)
        last_page: Last page to process (None = all pages)
        user_id: Optional UUID of the user for custom prompt settings
    """
    # Run async code in event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_until_complete(
            _process_document_async(job_id, document_id, first_page, last_page, user_id)
        )
        return result
    finally:
        loop.close()


async def _process_document_async(job_id: str, document_id: str, first_page: int, last_page: Optional[int], user_id: Optional[str]):
    """Async implementation with pipeline parallelization.
    
    Uses producer-consumer pattern to overlap PDF extraction and AI processing,
    resulting in 15-25% faster overall processing.
    """
    import time
    start_time = time.time()
    
    try:
        # Initialize connections
        await cache_service.connect()
        await init_db()  # Initialize database and run migrations
        
        # Also initialize persistent DB for metrics
        from services.db_service import persistent_db_service, init_persistent_db
        await init_persistent_db()
        
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
                        progress_callback=batch_progress_callback,
                        user_id=user_id
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
            
            # Get summary and verify it's not empty
            summary_text = item.get('summary', '') or ''
            # Handle topics - get from topics array or fallback to topic string
            topics_list = item.get('topics', [])
            if not topics_list and 'topic' in item:
                topics_list = [item['topic']]
            if not topics_list:
                topics_list = ['Other']
            event_date = item.get('event_date', None)  # Extract event_date from AI response
            
            # Log first few items to debug page/line data
            if idx < 3:
                logger.info(f"Saving final Q&A {idx+1}: printed_page={printed_page_num}, pdf_index={pdf_page_idx}, line={line_num}, answer_end={answer_end_page}:{answer_end_line}, summary={'yes' if summary_text else 'no'}, event_date={event_date}, topics={topics_list}, summary_preview={summary_text[:100] if summary_text else 'EMPTY'}..., question={item['question'][:50]}...")
            
            try:
                qa_item_id = await db_service.fetchval(
                    """
                    INSERT INTO final_qa_items (document_id, page_number, line_number, pdf_page_index, answer_end_page, answer_end_line, question, answer, summary, topics, event_date)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    RETURNING id
                    """,
                    document_id,
                    printed_page_num,
                    line_num,
                    pdf_page_idx,
                    answer_end_page,
                    answer_end_line,
                    item['question'],
                    item['answer'],
                    summary_text,
                    topics_list,
                    event_date
                )
                
                # Extract and store people mentioned in this Q&A
                people_data = item.get('people', [])
                if people_data:
                    witness_name = doc.get('witness_name')
                    await people_extraction_service.extract_and_store_people(
                        document_id,
                        qa_item_id,
                        people_data,
                        witness_name
                    )
                
            except Exception as e:
                logger.error(f"Failed to save final Q&A {idx+1}: {e}")
                logger.error(f"Q&A data: page={printed_page_num}, line={line_num}, summary_length={len(summary_text)}")
                raise
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
        
        # Count only final Q/As for result reporting
        final_count = len(final_qa_items)
        
        # Save processing metrics to persistent database (time per page, not per Q/A)
        end_time = time.time()
        total_processing_time = end_time - start_time
        avg_time_per_page = total_processing_time / total_pages_extracted if total_pages_extracted > 0 else 0
        
        logger.info(f"Processing metrics: {total_pages_extracted} pages in {total_processing_time:.2f}s (avg {avg_time_per_page:.2f}s per page)")
        
        await persistent_db_service.execute(
            """
            INSERT INTO processing_metrics (total_pages, total_processing_time_seconds, avg_time_per_page)
            VALUES ($1, $2, $3)
            """,
            total_pages_extracted,
            total_processing_time,
            avg_time_per_page
        )
        
        await send_job_update(job_id, "processing", 95, message="Finalizing...")
        
        # Step 5: Mark job as complete (100% progress)
        await db_service.execute(
            "UPDATE processing_jobs SET status = 'completed', progress = 100, completed_at = NOW() WHERE id = $1",
            job_id
        )
        
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


@celery_app.task(name="process_document_chunk")
def process_document_chunk_task(
    chunk_job_id: str,
    document_id: str,
    first_page: int,
    last_page: Optional[int],
    user_id: Optional[str] = None
):
    """
    Process a chunk of a document for parallel multi-worker processing.
    Similar to process_document_task but handles only a subset of pages.
    
    Args:
        chunk_job_id: UUID of the chunk job
        document_id: UUID of the document to process
        first_page: First page of this chunk (1-indexed)
        last_page: Last page of this chunk
        user_id: Optional UUID of the user for custom prompt settings
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_until_complete(
            _process_chunk_async(chunk_job_id, document_id, first_page, last_page, user_id)
        )
        return result
    finally:
        loop.close()


async def _process_chunk_async(
    chunk_job_id: str,
    document_id: str,
    first_page: int,
    last_page: Optional[int],
    user_id: Optional[str]
):
    """Process a document chunk asynchronously.
    
    This is similar to _process_document_async but:
    - Only processes specified page range
    - Reports progress to chunk_job and parent job
    - Uses worker-assigned API key automatically
    """
    import time
    start_time = time.time()
    
    try:
        # Initialize connections
        await cache_service.connect()
        await init_db()
        
        # Get chunk info
        chunk_info = await get_chunk_job_info(chunk_job_id)
        if not chunk_info:
            raise Exception(f"Chunk job {chunk_job_id} not found")
        
        parent_job_id = chunk_info['parent_job_id']
        chunk_index = chunk_info['chunk_index']
        worker_id = chunk_info['worker_id']
        
        logger.info(f"Processing chunk {chunk_index} (Worker {worker_id}): pages {first_page}-{last_page}")
        
        # Update chunk status to processing
        await db_service.execute(
            "UPDATE chunk_jobs SET status = 'processing', started_at = NOW() WHERE id = $1",
            chunk_job_id
        )
        await update_chunk_progress(chunk_job_id, 0, 0)
        
        # Get document info
        doc = await db_service.fetchrow(
            "SELECT filename, file_hash, s3_key FROM documents WHERE id = $1",
            document_id
        )
        
        if not doc:
            raise Exception("Document not found")
        
        logger.info(f"Chunk {chunk_index}: Processing {doc['filename']} pages {first_page}-{last_page}")
        
        # Retrieve PDF from Redis
        pdf_content = await cache_service.get_pdf_content(doc['file_hash'])
        if not pdf_content:
            raise Exception(f"PDF content not found in cache for {doc['file_hash'][:8]}")
        
        # Write to local temp file
        pdf_path = f"/tmp/{doc['file_hash']}_chunk_{chunk_index}.pdf"
        async with aiofiles.open(pdf_path, 'wb') as f:
            await f.write(pdf_content)
        
        logger.info(f"Chunk {chunk_index}: Retrieved PDF from Redis: {len(pdf_content)} bytes")
        
        # Pipeline: Extract and process in parallel
        processing_queue = asyncio.Queue(maxsize=10)
        all_qa_pairs = []
        summarized_items = []
        extraction_complete = False
        total_pages_extracted = 0
        
        async def extract_and_queue():
            """Producer: Extract pages and add Q&A pairs to queue."""
            nonlocal total_pages_extracted, extraction_complete
            
            await update_chunk_progress(chunk_job_id, 5, 0)
            
            try:
                async for page_batch in pdf_service.extract_pages_streaming(pdf_path, first_page, last_page):
                    total_pages_extracted += len(page_batch)
                    
                    batch_qa_pairs = []
                    for page in page_batch:
                        batch_qa_pairs.extend(page['qa_pairs'])
                    
                    # Deduplicate
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
                    
                    if unique_batch_qa:
                        await processing_queue.put(unique_batch_qa)
                        all_qa_pairs.extend(unique_batch_qa)
                    
                    progress = min(20, 5 + (total_pages_extracted * 15 // max(1, (last_page or 100) - first_page + 1)))
                    await update_chunk_progress(chunk_job_id, progress, 0)
                
                await processing_queue.put(None)
                extraction_complete = True
                logger.info(f"Chunk {chunk_index}: Extraction complete: {total_pages_extracted} pages, {len(all_qa_pairs)} Q&A pairs")
                
            except Exception as e:
                logger.error(f"Chunk {chunk_index}: Extraction failed: {e}")
                await processing_queue.put(None)
                raise
        
        async def process_from_queue():
            """Consumer: Process Q&A pairs as they become available."""
            nonlocal summarized_items
            
            await update_chunk_progress(chunk_job_id, 20, 0)
            
            processed_count = 0
            
            while True:
                batch = await processing_queue.get()
                
                if batch is None:
                    break
                
                async def batch_progress_callback(batch_progress_pct):
                    items_in_current_batch = len(batch)
                    current_batch_progress = (batch_progress_pct / 100) * items_in_current_batch
                    total_processed = processed_count + current_batch_progress
                    
                    if all_qa_pairs and len(all_qa_pairs) > 0:
                        overall_pct = (total_processed / len(all_qa_pairs)) * 100
                        progress = 20 + int(overall_pct * 0.7)
                    else:
                        progress = 20
                    
                    await update_chunk_progress(chunk_job_id, min(90, progress), int(total_processed))
                
                # Filter to only final Q/A pairs
                final_batch = [qa for qa in batch if qa.get('is_final', True)]
                non_final_batch = [qa for qa in batch if not qa.get('is_final', True)]
                
                for qa in non_final_batch:
                    summarized_items.append({
                        **qa,
                        'summary': '',
                        'topic': 'Other'
                    })
                
                if not final_batch:
                    processed_count += len(batch)
                    continue
                
                try:
                    summarized_batch = await ai_service.summarize_batch_parallel(
                        final_batch,
                        progress_callback=batch_progress_callback,
                        user_id=user_id
                    )
                    
                    for summarized_qa in summarized_batch:
                        summarized_items.append(summarized_qa)
                    
                    processed_count += len(batch)
                    
                    if all_qa_pairs and len(all_qa_pairs) > 0:
                        overall_progress = int((processed_count / len(all_qa_pairs)) * 70) + 20
                    else:
                        overall_progress = 20
                    
                    await update_chunk_progress(chunk_job_id, min(90, overall_progress), processed_count)
                    
                except Exception as e:
                    logger.error(f"Chunk {chunk_index}: Batch processing failed: {e}")
        
        # Run extraction and processing in parallel
        await asyncio.gather(
            extract_and_queue(),
            process_from_queue()
        )
        
        if not all_qa_pairs:
            raise Exception(f"No Q&A pairs found in chunk {chunk_index}")
        
        await update_chunk_progress(chunk_job_id, 90, len(all_qa_pairs))
        
        # Save results to database
        final_qa_items = [item for item in summarized_items if item.get('is_final', True)]
        interim_qa_items = [item for item in summarized_items if not item.get('is_final', True)]
        
        logger.info(f"Chunk {chunk_index}: Saving {len(final_qa_items)} final Q/A pairs")
        
        # Save final Q/As
        for item in final_qa_items:
            printed_page_num = item.get('page', 1)
            pdf_page_idx = item.get('pdf_page_index', printed_page_num)
            line_num = item.get('line', 1)
            answer_end_page = item.get('answer_end_page', printed_page_num)
            answer_end_line = item.get('answer_end_line', line_num)
            summary_text = item.get('summary', '') or ''
            # Handle topics - get from topics array or fallback to topic string
            topics_list = item.get('topics', [])
            if not topics_list and 'topic' in item:
                topics_list = [item['topic']]
            if not topics_list:
                topics_list = ['Other']
            event_date = item.get('event_date', None)
            
            qa_item_id = await db_service.fetchval(
                """
                INSERT INTO final_qa_items (document_id, page_number, line_number, pdf_page_index, 
                                          answer_end_page, answer_end_line, question, answer, 
                                          summary, topics, event_date)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                RETURNING id
                """,
                document_id, printed_page_num, line_num, pdf_page_idx,
                answer_end_page, answer_end_line,
                item['question'], item['answer'],
                summary_text, topics_list, event_date
            )
            
            # Extract and store people mentioned in this Q&A
            people_data = item.get('people', [])
            if people_data:
                witness_name = doc.get('witness_name')
                await people_extraction_service.extract_and_store_people(
                    document_id,
                    qa_item_id,
                    people_data,
                    witness_name
                )
        
        # Mark chunk complete
        await mark_chunk_complete(chunk_job_id)
        
        elapsed = time.time() - start_time
        logger.info(f"Chunk {chunk_index} complete: {len(final_qa_items)} items in {elapsed:.2f}s")
        
        return {
            "chunk_job_id": chunk_job_id,
            "chunk_index": chunk_index,
            "items_processed": len(final_qa_items),
            "pages_processed": total_pages_extracted
        }
        
    except Exception as e:
        logger.error(f"Chunk processing failed: {e}", exc_info=True)
        await mark_chunk_failed(chunk_job_id, str(e))
        raise
    
    finally:
        await cache_service.disconnect()
        await db_service.close_pool()

