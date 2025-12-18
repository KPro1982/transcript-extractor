"""Redis caching service for AI summaries and document metadata."""
import hashlib
import json
import logging
from typing import Optional, List, Dict
from datetime import timedelta

import redis.asyncio as redis

from config import settings

logger = logging.getLogger(__name__)


class CacheService:
    """Redis cache manager for AI summaries and document data."""
    
    def __init__(self):
        self.redis: Optional[redis.Redis] = None
        self.redis_binary: Optional[redis.Redis] = None  # For binary data (PDFs)
        self.ttl_days = settings.cache_ttl_days
    
    async def connect(self):
        """Connect to Redis."""
        self.redis = await redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True
        )
        # Separate connection for binary data (no decode)
        self.redis_binary = await redis.from_url(
            settings.redis_url,
            decode_responses=False
        )
        logger.info("Redis cache connected")
    
    async def disconnect(self):
        """Disconnect from Redis."""
        if self.redis:
            await self.redis.close()
        if self.redis_binary:
            await self.redis_binary.close()
            logger.info("Redis cache disconnected")
    
    def _get_summary_key(self, qa_text: str) -> str:
        """Generate cache key for Q&A summary."""
        text_hash = hashlib.sha256(qa_text.encode()).hexdigest()
        return f"summary:{text_hash}"
    
    def _get_document_key(self, file_hash: str) -> str:
        """Generate cache key for document metadata."""
        return f"document:{file_hash}"
    
    def _get_job_key(self, job_id: str) -> str:
        """Generate cache key for job status."""
        return f"job:{job_id}"
    
    def _get_pdf_content_key(self, file_hash: str) -> str:
        """Generate cache key for PDF binary content."""
        return f"pdf:{file_hash}"
    
    async def get_summary(self, question: str, answer: str) -> Optional[dict]:
        """Get cached summary for Q&A pair."""
        qa_text = f"Q: {question}\nA: {answer}"
        key = self._get_summary_key(qa_text)
        
        try:
            cached = await self.redis.get(key)
            if cached:
                logger.debug(f"Cache hit for summary: {key[:16]}...")
                # Update last accessed time
                await self.redis.expire(key, timedelta(days=self.ttl_days))
                return json.loads(cached)
        except Exception as e:
            logger.error(f"Cache get error: {e}")
        
        return None
    
    async def set_summary(self, question: str, answer: str, summary: str, topic: str = None):
        """Cache summary for Q&A pair."""
        qa_text = f"Q: {question}\nA: {answer}"
        key = self._get_summary_key(qa_text)
        
        data = {
            "summary": summary,
            "topic": topic,
            "question": question,
            "answer": answer
        }
        
        try:
            await self.redis.setex(
                key,
                timedelta(days=self.ttl_days),
                json.dumps(data)
            )
            logger.debug(f"Cached summary: {key[:16]}...")
        except Exception as e:
            logger.error(f"Cache set error: {e}")
    
    async def get_summaries_bulk(self, qa_items: List[Dict]) -> Dict[str, dict]:
        """Get multiple summaries in one Redis call using MGET.
        
        Returns a dict mapping cache keys to cached data.
        This reduces O(n) Redis calls to O(1).
        """
        if not qa_items:
            return {}
        
        keys = [
            self._get_summary_key(f"Q: {qa['question']}\nA: {qa['answer']}") 
            for qa in qa_items
        ]
        
        try:
            cached_values = await self.redis.mget(keys)
            results = {}
            
            for key, value in zip(keys, cached_values):
                if value:
                    results[key] = json.loads(value)
                    # Update expiry for accessed keys
                    await self.redis.expire(key, timedelta(days=self.ttl_days))
            
            if results:
                logger.info(f"Bulk cache hit: {len(results)}/{len(keys)} items")
            
            return results
        except Exception as e:
            logger.error(f"Bulk cache get error: {e}")
            return {}
    
    async def set_summaries_bulk(self, qa_results: List[tuple]):
        """Set multiple summaries in one Redis pipeline call.
        
        Args:
            qa_results: List of (question, answer, summary, topic) tuples
        
        This uses Redis pipelining to reduce network round-trips.
        """
        if not qa_results:
            return
        
        try:
            pipe = self.redis.pipeline()
            
            for question, answer, summary, topic in qa_results:
                qa_text = f"Q: {question}\nA: {answer}"
                key = self._get_summary_key(qa_text)
                data = {
                    "summary": summary,
                    "topic": topic,
                    "question": question,
                    "answer": answer
                }
                pipe.setex(
                    key,
                    timedelta(days=self.ttl_days),
                    json.dumps(data)
                )
            
            await pipe.execute()
            logger.info(f"Bulk cached {len(qa_results)} summaries")
        except Exception as e:
            logger.error(f"Bulk cache set error: {e}")
    
    async def get_document(self, file_hash: str) -> Optional[dict]:
        """Get cached document metadata."""
        key = self._get_document_key(file_hash)
        
        try:
            cached = await self.redis.get(key)
            if cached:
                logger.info(f"Cache hit for document: {file_hash[:8]}...")
                return json.loads(cached)
        except Exception as e:
            logger.error(f"Cache get error: {e}")
        
        return None
    
    async def set_document(self, file_hash: str, metadata: dict):
        """Cache document metadata."""
        key = self._get_document_key(file_hash)
        
        try:
            await self.redis.setex(
                key,
                timedelta(days=self.ttl_days),
                json.dumps(metadata)
            )
            logger.info(f"Cached document: {file_hash[:8]}...")
        except Exception as e:
            logger.error(f"Cache set error: {e}")
    
    async def get_job_status(self, job_id: str) -> Optional[dict]:
        """Get cached job status."""
        key = self._get_job_key(job_id)
        
        try:
            cached = await self.redis.get(key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.error(f"Cache get error: {e}")
        
        return None
    
    async def set_job_status(self, job_id: str, status: dict, ttl_seconds: int = 3600):
        """Cache job status (shorter TTL)."""
        key = self._get_job_key(job_id)
        
        try:
            await self.redis.setex(
                key,
                timedelta(seconds=ttl_seconds),
                json.dumps(status)
            )
        except Exception as e:
            logger.error(f"Cache set error: {e}")
    
    async def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        try:
            info = await self.redis.info("stats")
            return {
                "hits": info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0),
                "keys": await self.redis.dbsize(),
                "memory_used": info.get("used_memory_human", "unknown")
            }
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {}
    
    async def set_pdf_content(self, file_hash: str, content: bytes, ttl_hours: int = 24):
        """Store PDF binary content in Redis for worker access.
        
        This allows workers in separate containers to access uploaded files.
        TTL prevents Redis from filling with stale PDFs.
        """
        key = self._get_pdf_content_key(file_hash)
        
        try:
            await self.redis_binary.setex(
                key,
                timedelta(hours=ttl_hours),
                content
            )
            logger.info(f"Stored PDF in Redis: {file_hash[:8]}... ({len(content)} bytes, TTL: {ttl_hours}h)")
        except Exception as e:
            logger.error(f"Failed to store PDF content: {e}")
            raise
    
    async def get_pdf_content(self, file_hash: str) -> Optional[bytes]:
        """Retrieve PDF binary content from Redis.
        
        Returns None if not found (expired or never stored).
        """
        key = self._get_pdf_content_key(file_hash)
        
        try:
            content = await self.redis_binary.get(key)
            if content:
                logger.info(f"Retrieved PDF from Redis: {file_hash[:8]}... ({len(content)} bytes)")
                # Extend TTL on access
                await self.redis_binary.expire(key, timedelta(hours=24))
            return content
        except Exception as e:
            logger.error(f"Failed to retrieve PDF content: {e}")
            return None


# Global cache service instance
cache_service = CacheService()

