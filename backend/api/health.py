"""Health check endpoints."""
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
import asyncpg
import redis.asyncio as redis
import logging

from config import settings
from services.cache_service import cache_service

router = APIRouter()
logger = logging.getLogger(__name__)


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


@router.post("/cache/clear-summaries", status_code=status.HTTP_200_OK)
async def clear_summary_cache():
    """Clear all cached summaries to force re-generation with AI.
    
    Use this when:
    - Summaries are empty due to missing API key during initial processing
    - AI prompts have been updated and you want fresh summaries
    """
    try:
        # Get all summary cache keys
        keys = []
        async for key in cache_service.redis.scan_iter(match="summary:*"):
            keys.append(key)
        
        if keys:
            await cache_service.redis.delete(*keys)
            logger.info(f"Cleared {len(keys)} cached summaries")
            return {
                "status": "success",
                "message": f"Cleared {len(keys)} cached summaries",
                "keys_deleted": len(keys)
            }
        else:
            return {
                "status": "success", 
                "message": "No cached summaries found",
                "keys_deleted": 0
            }
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": "error", "message": str(e)}
        )


@router.get("/ai/status", status_code=status.HTTP_200_OK)
async def ai_provider_status():
    """Check if AI providers are configured and working."""
    from services.ai_service import ai_service
    
    providers_info = []
    for provider in ai_service.providers:
        providers_info.append({
            "name": provider.name,
            "configured": True
        })
    
    if not providers_info:
        return {
            "status": "not_configured",
            "message": "No AI providers configured! Set OPENAI_API_KEY environment variable.",
            "providers": []
        }
    
    return {
        "status": "configured",
        "message": f"{len(providers_info)} AI provider(s) available",
        "providers": providers_info
    }


