"""Job processing and status endpoints."""
import logging
from uuid import UUID
from typing import Optional, List

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, field_validator

from services.db_service import db_service, persistent_db_service
from services.cache_service import cache_service
from services.pdf_service import pdf_service
from workers.tasks import process_document_task, process_document_chunk_task
from workers.chunk_coordinator import (
    should_use_chunking,
    calculate_optimal_chunks,
    create_chunk_jobs
)
from config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


class PageRange(BaseModel):
    """A single page range."""
    start: int
    end: int
    
    @field_validator('start', 'end')
    @classmethod
    def validate_positive(cls, v):
        if v < 1:
            raise ValueError('Page numbers must be positive')
        return v
    
    @field_validator('end')
    @classmethod
    def validate_end_after_start(cls, v, info):
        if 'start' in info.data and v < info.data['start']:
            raise ValueError('End page must be >= start page')
        return v


class JobRequest(BaseModel):
    """Request to start document processing."""
    document_id: UUID
    first_page: int = 1
    last_page: Optional[int] = None
    page_ranges: Optional[List[PageRange]] = None  # New: support multiple ranges


def validate_page_ranges(ranges: List[PageRange], total_pages: int) -> None:
    """
    Validate page ranges for overlaps and bounds.
    
    Args:
        ranges: List of page ranges to validate
        total_pages: Total number of pages in document
        
    Raises:
        HTTPException: If validation fails
    """
    if not ranges:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one page range is required"
        )
    
    # Check all pages are within document bounds
    for r in ranges:
        if r.start > total_pages:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Start page {r.start} exceeds document length ({total_pages} pages)"
            )
        if r.end > total_pages:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"End page {r.end} exceeds document length ({total_pages} pages)"
            )
    
    # Check for overlaps
    sorted_ranges = sorted(ranges, key=lambda r: r.start)
    for i in range(len(sorted_ranges) - 1):
        if sorted_ranges[i].end >= sorted_ranges[i + 1].start:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Overlapping ranges: {sorted_ranges[i].start}-{sorted_ranges[i].end} and {sorted_ranges[i + 1].start}-{sorted_ranges[i + 1].end}"
            )


def merge_ranges_to_first_last(ranges: List[PageRange]) -> tuple[int, int]:
    """
    Merge multiple page ranges into overall first and last page.
    Used for backward compatibility with single-range processing.
    """
    if not ranges:
        return 1, None
    
    sorted_ranges = sorted(ranges, key=lambda r: r.start)
    return sorted_ranges[0].start, sorted_ranges[-1].end


class JobResponse(BaseModel):
    """Job creation response."""
    job_id: str
    status: str
    websocket_url: str


class JobStatus(BaseModel):
    """Job status response."""
    job_id: str
    document_id: str
    status: str
    progress: int
    error_message: Optional[str] = None


@router.post("/start", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def start_job(request: JobRequest, user_id: Optional[str] = None):
    """
    Start processing a document with automatic chunking support and optional page ranges.
    
    If document is large enough and multiple API keys are available,
    the document will be split into chunks and processed in parallel
    across multiple workers for maximum speed.
    
    Supports:
    - Single range via first_page/last_page (backward compat)
    - Multiple ranges via page_ranges parameter
    """
    # Verify document exists
    doc = await db_service.fetchrow(
        "SELECT id, filename, total_pages, file_hash FROM documents WHERE id = $1",
        request.document_id
    )
    
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    total_pages = doc['total_pages']
    
    # Handle page_ranges parameter if provided
    if request.page_ranges:
        validate_page_ranges(request.page_ranges, total_pages)
        first_page, last_page = merge_ranges_to_first_last(request.page_ranges)
        
        # Log the ranges for debugging
        ranges_str = "; ".join([f"{r.start}-{r.end}" for r in request.page_ranges])
        logger.info(f"Processing page ranges: {ranges_str}")
    else:
        # Use traditional first_page/last_page
        first_page = request.first_page
        last_page = request.last_page if request.last_page else total_pages
    
    # Estimate Q&A pairs for chunking decision (rough: 5 pairs per page)
    # Only count pages that will be processed
    pages_to_process = last_page - first_page + 1
    estimated_qa_pairs = pages_to_process * 5
    
    # Decide if we should use chunking
    use_chunking = await should_use_chunking(estimated_qa_pairs)
    
    if use_chunking and pages_to_process >= 100:  # Also require minimum pages
        # Create parent job for chunked processing
        job_id = await db_service.fetchval(
            """
            INSERT INTO processing_jobs (document_id, status, progress, is_chunked, num_chunks)
            VALUES ($1, 'queued', 0, TRUE, 0)
            RETURNING id
            """,
            request.document_id
        )
        
        # Calculate optimal number of chunks
        num_chunks = calculate_optimal_chunks(pages_to_process, settings.available_worker_keys)
        
        # Update parent job with chunk count
        await db_service.execute(
            "UPDATE processing_jobs SET num_chunks = $1 WHERE id = $2",
            num_chunks,
            job_id
        )
        
        # Create chunk jobs
        chunk_jobs = await create_chunk_jobs(
            str(job_id),
            str(request.document_id),
            pages_to_process,
            num_chunks,
            first_page_offset=first_page  # Start from specified first page
        )
        
        # Dispatch chunk tasks to workers
        try:
            for chunk in chunk_jobs:
                process_document_chunk_task.delay(
                    chunk['id'],
                    str(request.document_id),
                    chunk['first_page'],
                    chunk['last_page'],
                    user_id
                )
            
            logger.info(f"Job {job_id} queued with {num_chunks} chunks for document {doc['filename']}")
            
            return {
                "job_id": str(job_id),
                "status": "queued",
                "websocket_url": f"/ws/jobs/{job_id}"
            }
            
        except Exception as e:
            logger.error(f"Failed to enqueue chunk jobs: {e}", exc_info=True)
            
            await db_service.execute(
                "UPDATE processing_jobs SET status = 'failed', error_message = $1 WHERE id = $2",
                str(e),
                job_id
            )
            
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to start chunked job: {str(e)}"
            )
    
    else:
        # Standard single-worker processing
        job_id = await db_service.fetchval(
            """
            INSERT INTO processing_jobs (document_id, status, progress, is_chunked)
            VALUES ($1, 'queued', 0, FALSE)
            RETURNING id
            """,
            request.document_id
        )
        
        # Enqueue standard task
        try:
            process_document_task.delay(
                str(job_id),
                str(request.document_id),
                first_page,
                last_page,
                user_id
            )
            
            logger.info(f"Job {job_id} queued (standard) for document {doc['filename']} (pages {first_page}-{last_page})")
            
            return {
                "job_id": str(job_id),
                "status": "queued",
                "websocket_url": f"/ws/jobs/{job_id}"
            }
            
        except Exception as e:
            logger.error(f"Failed to enqueue job: {e}", exc_info=True)
            
            await db_service.execute(
                "UPDATE processing_jobs SET status = 'failed', error_message = $1 WHERE id = $2",
                str(e),
                job_id
            )
            
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to start job: {str(e)}"
            )


@router.get("/{job_id}/status", response_model=JobStatus)
async def get_job_status(job_id: UUID):
    """Get current status of a processing job."""
    # Try cache first
    cached_status = await cache_service.get_job_status(str(job_id))
    if cached_status:
        return cached_status
    
    # Fall back to database
    job = await db_service.fetchrow(
        """
        SELECT id, document_id, status, progress, error_message
        FROM processing_jobs
        WHERE id = $1
        """,
        job_id
    )
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    status_data = {
        "job_id": str(job["id"]),
        "document_id": str(job["document_id"]),
        "status": job["status"],
        "progress": job["progress"],
        "error_message": job["error_message"]
    }
    
    # Cache for 60 seconds
    await cache_service.set_job_status(str(job_id), status_data, ttl_seconds=60)
    
    return status_data


@router.get("/metrics/avg-time")
async def get_avg_processing_time():
    """Get average processing time per page based on recent jobs."""
    # Get average from last 10 processing jobs
    result = await persistent_db_service.fetchrow(
        """
        SELECT AVG(avg_time_per_page) as avg_time
        FROM (
            SELECT avg_time_per_page
            FROM processing_metrics
            ORDER BY created_at DESC
            LIMIT 10
        ) recent_jobs
        """
    )
    
    avg_time = result['avg_time'] if result and result['avg_time'] else 1.5  # Default 1.5s per page
    
    return {
        "avg_time_per_page_seconds": float(avg_time),
        "based_on_recent_jobs": 10
    }








