"""Cache management endpoints."""
from fastapi import APIRouter, Query, status
from fastapi.responses import JSONResponse
import logging

from services.cache_service import cache_service

router = APIRouter(prefix="/cache", tags=["cache"])
logger = logging.getLogger(__name__)


@router.post("/clear", status_code=status.HTTP_200_OK)
async def clear_cache(
    cache_type: str = Query("summaries", description="Type of cache to clear: 'summaries', 'pdfs', 'all'")
):
    """Clear cached data.
    
    Args:
        cache_type: What to clear
            - 'summaries': Clear only AI-generated summaries
            - 'pdfs': Clear only cached PDF files  
            - 'all': Clear everything
    
    Use this when:
    - Summaries are empty (missing API key during processing)
    - AI prompts changed and you want fresh summaries
    - Free up Redis memory
    """
    try:
        deleted_count = 0
        
        if cache_type == "summaries":
            # Clear summary cache
            keys = []
            async for key in cache_service.redis.scan_iter(match="summary:*"):
                keys.append(key)
            
            if keys:
                await cache_service.redis.delete(*keys)
                deleted_count = len(keys)
                logger.info(f"Cleared {deleted_count} cached summaries")
            
            return {
                "status": "success",
                "message": f"Cleared {deleted_count} cached summaries",
                "cache_type": "summaries",
                "keys_deleted": deleted_count
            }
        
        elif cache_type == "pdfs":
            # Clear PDF cache
            keys = []
            async for key in cache_service.redis.scan_iter(match="pdf:*"):
                keys.append(key)
            
            if keys:
                await cache_service.redis.delete(*keys)
                deleted_count = len(keys)
                logger.info(f"Cleared {deleted_count} cached PDFs")
            
            return {
                "status": "success",
                "message": f"Cleared {deleted_count} cached PDF files",
                "cache_type": "pdfs",
                "keys_deleted": deleted_count
            }
        
        elif cache_type == "all":
            # Clear everything
            await cache_service.redis.flushdb()
            logger.warning("Cleared ALL cached data (FLUSHDB)")
            
            return {
                "status": "success",
                "message": "Cleared all cached data",
                "cache_type": "all",
                "warning": "All cache data has been cleared"
            }
        
        else:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "status": "error",
                    "message": f"Invalid cache_type: {cache_type}. Use 'summaries', 'pdfs', or 'all'"
                }
            )
    
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": "error", "message": str(e)}
        )


@router.get("/stats", status_code=status.HTTP_200_OK)
async def cache_stats():
    """Get cache statistics."""
    try:
        # Count keys by type
        summary_count = 0
        pdf_count = 0
        other_count = 0
        
        async for key in cache_service.redis.scan_iter(match="*"):
            key_str = key.decode('utf-8') if isinstance(key, bytes) else key
            if key_str.startswith("summary:"):
                summary_count += 1
            elif key_str.startswith("pdf:"):
                pdf_count += 1
            else:
                other_count += 1
        
        # Get Redis info
        info = await cache_service.redis.info()
        memory_used = info.get('used_memory_human', 'unknown')
        total_keys = info.get('db0', {}).get('keys', 0) if 'db0' in info else 0
        
        return {
            "status": "success",
            "summary_cache_count": summary_count,
            "pdf_cache_count": pdf_count,
            "other_cache_count": other_count,
            "total_keys": summary_count + pdf_count + other_count,
            "memory_used": memory_used,
            "redis_version": info.get('redis_version', 'unknown')
        }
    
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": "error", "message": str(e)}
        )



