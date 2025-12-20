"""Job processing and status endpoints."""
import logging
from uuid import UUID
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from services.db_service import db_service, persistent_db_service
from services.cache_service import cache_service
from workers.tasks import process_document_task

router = APIRouter()
logger = logging.getLogger(__name__)


class JobRequest(BaseModel):
    """Request to start document processing."""
    document_id: UUID
    first_page: int = 1
    last_page: Optional[int] = None


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
async def start_job(request: JobRequest):
    """
    Start processing a document.
    Returns job ID for status tracking via WebSocket.
    """
    # Verify document exists
    doc = await db_service.fetchrow(
        "SELECT id, filename FROM documents WHERE id = $1",
        request.document_id
    )
    
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Create job record
    job_id = await db_service.fetchval(
        """
        INSERT INTO processing_jobs (document_id, status, progress)
        VALUES ($1, 'queued', 0)
        RETURNING id
        """,
        request.document_id
    )
    
    # Enqueue task
    try:
        # This will be handled by Celery workers
        process_document_task.delay(
            str(job_id),
            str(request.document_id),
            request.first_page,
            request.last_page
        )
        
        logger.info(f"Job {job_id} queued for document {doc['filename']}")
        
        return {
            "job_id": str(job_id),
            "status": "queued",
            "websocket_url": f"/ws/jobs/{job_id}"
        }
        
    except Exception as e:
        logger.error(f"Failed to enqueue job: {e}", exc_info=True)
        
        # Update job status to failed
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








