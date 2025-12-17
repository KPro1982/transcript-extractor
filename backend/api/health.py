"""Health check endpoints."""
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
import asyncpg
import redis.asyncio as redis

from config import settings
from services.cache_service import cache_service

router = APIRouter()


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """Basic health check endpoint."""
    return {"status": "healthy", "service": "depodigest-api", "version": "2.0.0"}


@router.get("/health/detailed", status_code=status.HTTP_200_OK)
async def detailed_health_check():
    """Detailed health check including dependencies."""
    health_status = {
        "api": "healthy",
        "database": "unknown",
        "cache": "unknown",
        "workers": "unknown"
    }
    
    # Check database
    try:
        conn = await asyncpg.connect(settings.database_url)
        await conn.execute("SELECT 1")
        await conn.close()
        health_status["database"] = "healthy"
    except Exception as e:
        health_status["database"] = f"unhealthy: {str(e)}"
    
    # Check cache
    try:
        await cache_service.redis.ping()
        health_status["cache"] = "healthy"
    except Exception as e:
        health_status["cache"] = f"unhealthy: {str(e)}"
    
    # Determine overall status
    overall_healthy = all(
        status == "healthy" 
        for key, status in health_status.items() 
        if key != "workers"  # Workers optional for basic health
    )
    
    status_code = status.HTTP_200_OK if overall_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    
    return JSONResponse(
        status_code=status_code,
        content={"status": "healthy" if overall_healthy else "degraded", "services": health_status}
    )

