"""Chunk coordinator for multi-worker parallel processing."""
import logging
import asyncio
from typing import Optional, List
from uuid import UUID

from services.db_service import db_service
from services.cache_service import cache_service
from config import settings

logger = logging.getLogger(__name__)


async def should_use_chunking(total_qa_pairs: int) -> bool:
    """Determine if document should be chunked based on size and available workers.
    
    Args:
        total_qa_pairs: Estimated or known total Q&A pairs in document
        
    Returns:
        True if chunking should be used, False otherwise
    """
    if not settings.enable_chunking:
        return False
    
    # Only chunk if document is large enough
    if total_qa_pairs < settings.chunking_threshold:
        logger.info(f"Document too small for chunking ({total_qa_pairs} < {settings.chunking_threshold} pairs)")
        return False
    
    # Check if multiple worker keys are available
    available_keys = settings.available_worker_keys
    if available_keys < 2:
        logger.info("Only 1 API key available, chunking disabled")
        return False
    
    logger.info(f"Chunking enabled: {total_qa_pairs} pairs, {available_keys} keys available")
    return True


def calculate_optimal_chunks(total_pages: int, available_keys: int) -> int:
    """Calculate optimal number of chunks based on document size and available keys.
    
    Args:
        total_pages: Total pages in document
        available_keys: Number of available API keys/workers
        
    Returns:
        Optimal number of chunks
    """
    # Don't exceed available keys
    max_chunks = min(available_keys, settings.max_chunks)
    
    # Ensure each chunk has at least 50 pages
    min_pages_per_chunk = 50
    chunks_by_pages = total_pages // min_pages_per_chunk
    
    optimal_chunks = min(max_chunks, max(1, chunks_by_pages))
    
    logger.info(f"Optimal chunks: {optimal_chunks} (pages={total_pages}, keys={available_keys})")
    return optimal_chunks


async def create_chunk_jobs(
    parent_job_id: str,
    document_id: str,
    total_pages: int,
    num_chunks: int,
    first_page_offset: int = 0
) -> List[dict]:
    """Create chunk jobs for parallel processing.
    
    Args:
        parent_job_id: Parent processing job ID
        document_id: Document to process
        total_pages: Total pages in document (relative to offset)
        num_chunks: Number of chunks to create
        first_page_offset: Offset to add to calculated page numbers (default: 0)
                          Used when processing doesn't start from page 1
        
    Returns:
        List of chunk job records
    """
    pages_per_chunk = total_pages // num_chunks
    chunk_jobs = []
    
    for i in range(num_chunks):
        # Calculate relative page numbers (starting from 1)
        relative_first = i * pages_per_chunk + 1
        relative_last = (i + 1) * pages_per_chunk if i < num_chunks - 1 else total_pages
        
        # Apply offset to get actual page numbers
        first_page = relative_first + first_page_offset - 1
        last_page = relative_last + first_page_offset - 1
        
        # Create chunk job record
        chunk_job_id = await db_service.fetchval(
            """
            INSERT INTO chunk_jobs (
                parent_job_id, document_id, chunk_index, 
                first_page, last_page, status, worker_id
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
            """,
            parent_job_id,
            document_id,
            i,
            first_page,
            last_page,
            'pending',
            i % settings.available_worker_keys  # Round-robin worker assignment
        )
        
        chunk_jobs.append({
            'id': str(chunk_job_id),
            'chunk_index': i,
            'first_page': first_page,
            'last_page': last_page,
            'worker_id': i % settings.available_worker_keys
        })
        
        logger.info(f"Created chunk {i}: pages {first_page}-{last_page}, worker {i % settings.available_worker_keys}")
    
    return chunk_jobs


async def update_chunk_progress(chunk_job_id: str, progress: int, items_processed: int = 0):
    """Update progress for a chunk job.
    
    Args:
        chunk_job_id: Chunk job ID
        progress: Progress percentage (0-100)
        items_processed: Number of items processed so far
    """
    await db_service.execute(
        """
        UPDATE chunk_jobs 
        SET progress = $1, items_processed = $2
        WHERE id = $3
        """,
        progress,
        items_processed,
        chunk_job_id
    )
    
    # Also update parent job progress
    await update_parent_job_progress(chunk_job_id)


async def update_parent_job_progress(chunk_job_id: str):
    """Update parent job progress based on all chunk progress.
    
    Args:
        chunk_job_id: Any chunk job ID (used to find parent)
    """
    # Get parent job ID
    parent_job_id = await db_service.fetchval(
        "SELECT parent_job_id FROM chunk_jobs WHERE id = $1",
        chunk_job_id
    )
    
    if not parent_job_id:
        return
    
    # Calculate average progress across all chunks
    avg_progress = await db_service.fetchval(
        """
        SELECT COALESCE(AVG(progress), 0)::INT
        FROM chunk_jobs
        WHERE parent_job_id = $1
        """,
        parent_job_id
    )
    
    # Update parent job
    await db_service.execute(
        """
        UPDATE processing_jobs
        SET progress = $1
        WHERE id = $2
        """,
        avg_progress,
        parent_job_id
    )
    
    # Publish update via Redis pub/sub
    await cache_service.publish_job_update(
        str(parent_job_id),
        "progress",
        {
            "status": "processing",
            "progress": avg_progress,
            "message": f"Processing in parallel ({avg_progress}% complete)"
        }
    )


async def mark_chunk_complete(chunk_job_id: str):
    """Mark a chunk job as complete.
    
    Args:
        chunk_job_id: Chunk job ID
    """
    await db_service.execute(
        """
        UPDATE chunk_jobs
        SET status = 'completed', completed_at = NOW(), progress = 100
        WHERE id = $1
        """,
        chunk_job_id
    )
    
    logger.info(f"Chunk {chunk_job_id[:8]}... marked complete")
    
    # Check if all chunks are complete
    await check_and_complete_parent(chunk_job_id)


async def mark_chunk_failed(chunk_job_id: str, error_message: str):
    """Mark a chunk job as failed.
    
    Args:
        chunk_job_id: Chunk job ID
        error_message: Error description
    """
    await db_service.execute(
        """
        UPDATE chunk_jobs
        SET status = 'failed', error_message = $1, completed_at = NOW()
        WHERE id = $2
        """,
        error_message,
        chunk_job_id
    )
    
    logger.error(f"Chunk {chunk_job_id[:8]}... failed: {error_message}")
    
    # Also check parent (may need to fail parent job)
    await check_and_complete_parent(chunk_job_id)


async def check_and_complete_parent(chunk_job_id: str):
    """Check if all chunks are complete and finalize parent job.
    
    Args:
        chunk_job_id: Any chunk job ID
    """
    # Get parent job ID
    parent_info = await db_service.fetchrow(
        "SELECT parent_job_id, document_id FROM chunk_jobs WHERE id = $1",
        chunk_job_id
    )
    
    if not parent_info:
        return
    
    parent_job_id = parent_info['parent_job_id']
    document_id = parent_info['document_id']
    
    # Get all chunk statuses
    chunks = await db_service.fetch(
        "SELECT status, error_message FROM chunk_jobs WHERE parent_job_id = $1",
        parent_job_id
    )
    
    all_complete = all(c['status'] == 'completed' for c in chunks)
    any_failed = any(c['status'] == 'failed' for c in chunks)
    
    if any_failed:
        # Mark parent as failed
        failed_errors = [c['error_message'] for c in chunks if c['status'] == 'failed']
        await db_service.execute(
            """
            UPDATE processing_jobs
            SET status = 'failed', error_message = $1, completed_at = NOW()
            WHERE id = $2
            """,
            f"One or more chunks failed: {'; '.join(failed_errors)}",
            parent_job_id
        )
        
        await cache_service.publish_job_update(
            str(parent_job_id),
            "error",
            {"error_message": "Processing failed in one or more chunks"}
        )
        
    elif all_complete:
        # All chunks complete - finalize parent job
        total_items = await db_service.fetchval(
            "SELECT COUNT(*) FROM final_qa_items WHERE document_id = $1",
            document_id
        )
        
        await db_service.execute(
            """
            UPDATE processing_jobs
            SET status = 'completed', progress = 100, completed_at = NOW()
            WHERE id = $1
            """,
            parent_job_id
        )
        
        logger.info(f"Parent job {parent_job_id[:8]}... completed: {total_items} items processed")
        
        await cache_service.publish_job_update(
            str(parent_job_id),
            "complete",
            {
                "document_id": str(document_id),
                "total_qa_pairs": total_items,
                "message": "All chunks processed successfully"
            }
        )


async def get_chunk_job_info(chunk_job_id: str) -> Optional[dict]:
    """Get chunk job information.
    
    Args:
        chunk_job_id: Chunk job ID
        
    Returns:
        Chunk job info or None
    """
    chunk = await db_service.fetchrow(
        """
        SELECT id, parent_job_id, document_id, chunk_index, worker_id,
               first_page, last_page, status, progress, error_message
        FROM chunk_jobs
        WHERE id = $1
        """,
        chunk_job_id
    )
    
    if chunk:
        return dict(chunk)
    return None

