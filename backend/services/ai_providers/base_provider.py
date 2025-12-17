"""Base class for AI providers."""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import logging
import httpx

logger = logging.getLogger(__name__)


class RateLimitError(Exception):
    """Raised when API rate limit is hit."""
    pass


class BaseAIProvider(ABC):
    """Abstract base class for AI providers."""
    
    def __init__(self, api_key: str, name: str):
        self.api_key = api_key
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{name}")
        
        # HTTP client with connection pooling for performance
        # - Reuses TCP connections across requests (eliminates handshake overhead)
        # - HTTP/2 multiplexing for parallel requests over single connection
        # - Keeps up to 20 idle connections alive for 60s
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=10.0),
            limits=httpx.Limits(
                max_keepalive_connections=20,
                max_connections=100,
                keepalive_expiry=60.0
            ),
            http2=True  # Enable HTTP/2 for better performance
        )
    
    @abstractmethod
    async def summarize(self, question: str, answer: str, colloquy: str = None, timeout: int = 60) -> str:
        """Generate summary for a single Q&A pair."""
        pass
    
    @abstractmethod
    async def summarize_batch(
        self,
        qa_items: List[Dict],
        timeout: int = 60
    ) -> List[Dict]:
        """
        Summarize multiple Q&A pairs in one API call.
        Returns list of dicts with 'summary' and 'topic' fields.
        """
        pass
    
    @abstractmethod
    async def classify_topics(
        self,
        qa_items: List[Dict],
        timeout: int = 60
    ) -> List[str]:
        """Classify topics for multiple Q&A pairs."""
        pass
    
    async def summarize_and_classify_batch(
        self,
        qa_items: List[Dict],
        timeout: int = 60
    ) -> List[Dict]:
        """
        Combined summarization and topic classification in one API call.
        Default implementation calls both methods, but providers can override for efficiency.
        """
        results = await self.summarize_batch(qa_items, timeout)
        return results
    
    def _handle_rate_limit(self, response_data: dict):
        """Check if response indicates rate limiting."""
        # Override in subclasses if needed
        pass
    
    def is_available(self) -> bool:
        """Check if provider is configured and available."""
        return self.api_key is not None and len(self.api_key) > 0
    
    async def close(self):
        """Close HTTP client and cleanup resources."""
        await self.client.close()
        self.logger.info(f"{self.name} provider closed")

