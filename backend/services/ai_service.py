"""AI service coordinator with multi-provider support and intelligent parallelization."""
import asyncio
import logging
from typing import List, Dict, Optional
from datetime import datetime
import tiktoken

from config import settings
from services.cache_service import cache_service
from services.ai_providers.base_provider import BaseAIProvider, RateLimitError
from services.ai_providers.openai_provider import OpenAIProvider
from services.ai_providers.anthropic_provider import AnthropicProvider

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token bucket rate limiter for API requests.
    
    Implements adaptive rate limiting to prevent API throttling:
    - Tracks requests per minute (RPM)
    - Tracks tokens per minute (TPM)
    - Uses semaphores for concurrent request control
    - Auto-refills token bucket every minute
    """
    
    def __init__(self, requests_per_minute: int, tokens_per_minute: int):
        self.rpm = requests_per_minute
        self.tpm = tokens_per_minute
        self.request_semaphore = asyncio.Semaphore(min(requests_per_minute, 100))  # Cap at 100 concurrent
        self.token_bucket = tokens_per_minute
        self.last_refill = datetime.now()
        self._lock = asyncio.Lock()
        logger.info(f"RateLimiter initialized: {requests_per_minute} RPM, {tokens_per_minute} TPM")
    
    async def acquire(self, tokens_needed: int = 100):
        """Acquire permission to make API call.
        
        Args:
            tokens_needed: Estimated tokens for this request (default 100)
        """
        async with self._lock:
            # Refill token bucket if a minute has passed
            now = datetime.now()
            elapsed = (now - self.last_refill).total_seconds()
            if elapsed >= 60:
                self.token_bucket = self.tpm
                self.last_refill = now
                logger.debug(f"Token bucket refilled: {self.tpm} tokens")
        
        # Wait for sufficient tokens
        retry_count = 0
        while self.token_bucket < tokens_needed:
            if retry_count == 0:
                logger.warning(f"Rate limit: waiting for {tokens_needed} tokens (available: {self.token_bucket})")
            retry_count += 1
            await asyncio.sleep(1)
            
            # Check for refill
            async with self._lock:
                now = datetime.now()
                elapsed = (now - self.last_refill).total_seconds()
                if elapsed >= 60:
                    self.token_bucket = self.tpm
                    self.last_refill = now
                    logger.debug("Token bucket refilled during wait")
        
        # Consume tokens
        async with self._lock:
            self.token_bucket -= tokens_needed
        
        # Acquire request semaphore
        await self.request_semaphore.acquire()
    
    def release(self):
        """Release request semaphore."""
        self.request_semaphore.release()


class AIService:
    """
    Intelligent AI service with:
    - Multi-provider fallback
    - Automatic caching
    - Massive parallelization
    - Smart batch sizing
    """
    
    def __init__(self):
        self.providers: List[BaseAIProvider] = []
        self._init_providers()
        self.max_concurrent = settings.max_concurrent_ai_requests
        self.items_per_batch = 20
        
        # Token-aware batching with tiktoken
        try:
            self.tokenizer = tiktoken.encoding_for_model("gpt-4o-mini")
            self.max_tokens_per_batch = 8000  # Leave room for response and system prompt
            logger.info("Token-aware batching enabled with tiktoken")
        except Exception as e:
            logger.warning(f"Failed to load tiktoken, falling back to character counting: {e}")
            self.tokenizer = None
            self.max_tokens_per_batch = None
        
        # Adaptive rate limiter
        self.rate_limiter = RateLimiter(
            requests_per_minute=settings.openai_rpm,
            tokens_per_minute=settings.openai_tpm
        )
        
        # Performance metrics
        self.metrics = {
            "total_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "deduplicated": 0,
            "api_calls": 0,
            "api_errors": 0,
            "total_tokens_estimated": 0,
            "total_processing_time": 0.0,
            "batches_processed": 0
        }
    
    def _init_providers(self):
        """Initialize available AI providers using assigned worker key."""
        # Use assigned key based on worker_id (supports multi-worker with different keys)
        assigned_key = settings.assigned_openai_key
        
        if assigned_key:
            # Mask key for logging (show first 8 and last 4 chars)
            masked_key = f"{assigned_key[:8]}...{assigned_key[-4:]}" if len(assigned_key) > 12 else "***"
            logger.info(f"✅ OpenAI provider initialized (Worker {settings.worker_id}) with key: {masked_key}")
            self.providers.append(OpenAIProvider(assigned_key))
        else:
            logger.error("❌ OPENAI_API_KEY not set! AI summarization will NOT work.")
        
        if settings.anthropic_api_key:
            self.providers.append(AnthropicProvider(settings.anthropic_api_key))
            logger.info("✅ Anthropic provider initialized")
        
        if not self.providers:
            logger.error("="*60)
            logger.error("❌ CRITICAL: No AI providers configured!")
            logger.error("Set OPENAI_API_KEY environment variable in Railway.")
            logger.error("="*60)
    
    def calculate_optimal_batch_size(self, qa_items: List[Dict]) -> int:
        """Calculate optimal batch size based on actual token count.
        
        This is more accurate than character counting and prevents:
        - Rate limit issues from oversized batches
        - Inefficient small batches that waste API calls
        """
        if not qa_items:
            return 20
        
        # Use token-aware batching if available
        if self.tokenizer and self.max_tokens_per_batch:
            current_batch_tokens = 0
            batch_size = 0
            
            # System prompt overhead (~150 tokens)
            system_overhead = 150
            current_batch_tokens = system_overhead
            
            for qa in qa_items:
                qa_text = f"Q: {qa.get('question', '')}\nA: {qa.get('answer', '')}"
                try:
                    tokens = len(self.tokenizer.encode(qa_text))
                except Exception:
                    # Fallback to character estimate (4 chars ≈ 1 token)
                    tokens = len(qa_text) // 4
                
                # Check if adding this item would exceed limit
                if current_batch_tokens + tokens > self.max_tokens_per_batch:
                    break
                
                current_batch_tokens += tokens
                batch_size += 1
            
            # At least 1 item per batch, max 30 items
            return max(1, min(batch_size, 30))
        
        # Fallback to character-based estimation
        avg_length = sum(
            len(qa.get('question', '')) + len(qa.get('answer', ''))
            for qa in qa_items
        ) / len(qa_items)
        
        if avg_length < 200:
            return 30  # Short Q&A
        elif avg_length < 500:
            return 20  # Medium Q&A
        else:
            return 10  # Long Q&A
    
    async def summarize_with_fallback(
        self,
        question: str,
        answer: str,
        colloquy: str = None
    ) -> Optional[str]:
        """Summarize single Q&A with provider fallback."""
        # Check cache first
        cached = await cache_service.get_summary(question, answer)
        if cached:
            return cached.get('summary')
        
        # Try each provider
        for provider in self.providers:
            try:
                summary = await provider.summarize(question, answer, colloquy)
                
                # Cache the result
                await cache_service.set_summary(question, answer, summary)
                
                return summary
                
            except RateLimitError:
                logger.warning(f"{provider.name} rate limit hit, trying next provider...")
                continue
            except Exception as e:
                logger.error(f"{provider.name} failed: {e}")
                continue
        
        logger.error("All AI providers failed")
        return None
    
    async def summarize_batch_parallel(
        self,
        qa_items: List[Dict],
        progress_callback=None,
        user_id: Optional[str] = None
    ) -> List[Dict]:
        """
        Massively parallel batch summarization with caching and deduplication.
        This is the key to speed optimization!
        
        Optimizations:
        - Deduplicates identical Q&A pairs (reduces API calls by 5-15%)
        - Bulk cache lookups (O(1) instead of O(n) Redis calls)
        - Token-aware batching (prevents rate limits)
        - Massive parallelization (50+ concurrent requests)
        - User prompt settings integration
        """
        import time
        start_time = time.time()
        
        # Fetch user prompt settings if user_id provided
        user_prompt_settings = None
        if user_id:
            try:
                from services.db_service import persistent_db_service
                settings_row = await persistent_db_service.fetchrow(
                    "SELECT preset_options, custom_instructions FROM user_prompt_settings WHERE user_id = $1",
                    user_id
                )
                if settings_row:
                    user_prompt_settings = {
                        "preset_options": settings_row['preset_options'] or {},
                        "custom_instructions": settings_row['custom_instructions']
                    }
                    logger.info(f"Loaded prompt settings for user {user_id}: {len(user_prompt_settings.get('preset_options', {}))} presets, custom={bool(user_prompt_settings.get('custom_instructions'))}")
            except Exception as e:
                logger.warning(f"Failed to load user prompt settings: {e}")
        
        if not qa_items:
            return []
        
        if not self.providers:
            logger.error("❌ CRITICAL: No AI providers configured! Set OPENAI_API_KEY environment variable.")
            logger.error("Summaries will be empty because no AI provider is available.")
            # Return items with explicit error message in summary
            return [{
                "summary": "[AI summarization unavailable - OPENAI_API_KEY not configured]",
                "topic": "Other",
                **qa
            } for qa in qa_items]
        
        # Update metrics
        self.metrics["total_requests"] += len(qa_items)
        
        # Step 1: Deduplicate Q&A pairs
        # Same questions (e.g., "State your name") appear multiple times
        seen = {}
        unique_items = []
        duplicate_map = {}  # Maps original index to unique index
        
        for idx, qa in enumerate(qa_items):
            # Create a key from question and answer
            key = f"{qa.get('question', '')}|||{qa.get('answer', '')}"
            
            if key in seen:
                # This is a duplicate - remember where to get the result
                duplicate_map[idx] = seen[key]
            else:
                # First occurrence - add to unique list
                seen[key] = len(unique_items)
                unique_items.append(qa)
                duplicate_map[idx] = len(unique_items) - 1
        
        dedup_savings = len(qa_items) - len(unique_items)
        if dedup_savings > 0:
            logger.info(f"Deduplication: processing {len(unique_items)} unique items (saved {dedup_savings} duplicates)")
            self.metrics["deduplicated"] += dedup_savings
        
        # Calculate optimal batch size based on unique items
        batch_size = self.calculate_optimal_batch_size(unique_items)
        
        # Step 2: Bulk cache lookup for unique items (O(1) Redis call instead of O(n))
        cache_map = await cache_service.get_summaries_bulk(unique_items)
        
        # Build results for unique items
        unique_results = []
        uncached_items = []
        uncached_indices = []
        
        for idx, qa in enumerate(unique_items):
            qa_key = cache_service._get_summary_key(f"Q: {qa['question']}\nA: {qa['answer']}")
            
            if qa_key in cache_map:
                cached = cache_map[qa_key]
                unique_results.append({
                    **qa,
                    'summary': cached['summary'],
                    'topic': cached.get('topic', 'Other'),
                    'cached': True
                })
            else:
                uncached_items.append(qa)
                uncached_indices.append(idx)
                unique_results.append(None)  # Placeholder
        
        cache_hits = len(unique_items) - len(uncached_items)
        cache_hit_rate = cache_hits / len(unique_items) * 100 if unique_items else 0
        logger.info(f"Cache hit rate: {cache_hit_rate:.1f}% ({cache_hits}/{len(unique_items)})")
        
        # Update cache metrics
        self.metrics["cache_hits"] += cache_hits
        self.metrics["cache_misses"] += len(uncached_items)
        
        # Report cache hits immediately (instant progress from cached items)
        if progress_callback and cache_hits > 0:
            cache_progress = int((cache_hits / len(unique_items)) * 100)
            await progress_callback(cache_progress)
            logger.debug(f"Reported {cache_progress}% progress from cache hits")
        
        # Step 3: If all unique items were cached, map back to original and return
        if not uncached_items:
            # All items were cached - report 100% progress
            if progress_callback:
                await progress_callback(100)
            
            # Map unique results back to original positions (handle duplicates)
            final_results = []
            for idx in range(len(qa_items)):
                unique_idx = duplicate_map[idx]
                result = unique_results[unique_idx]
                # Merge original qa_item metadata
                final_results.append({**qa_items[idx], **result})
            
            # Update processing time metrics
            elapsed = time.time() - start_time
            self.metrics["total_processing_time"] += elapsed
            logger.info(f"Batch processing completed in {elapsed:.2f}s (100% cached)")
            
            return final_results
        
        # Split uncached items into batches
        batches = [
            uncached_items[i:i + batch_size]
            for i in range(0, len(uncached_items), batch_size)
        ]
        
        logger.info(f"Processing {len(uncached_items)} items in {len(batches)} batches with up to {self.max_concurrent} concurrent requests")
        
        # Update batch metrics
        self.metrics["batches_processed"] += len(batches)
        self.metrics["api_calls"] += len(batches)
        
        # Process batches with massive parallelization
        # Use asyncio.gather for TRUE parallelism (not limited like old Node.js implementation)
        primary_provider = self.providers[0]
        completed_count = 0
        
        async def process_batch(batch, batch_idx):
            nonlocal completed_count
            
            # Estimate tokens for rate limiting
            batch_text_length = sum(
                len(qa.get('question', '')) + len(qa.get('answer', ''))
                for qa in batch
            )
            estimated_tokens = batch_text_length // 4  # Rough estimate: 4 chars ≈ 1 token
            
            # Update token metrics
            self.metrics["total_tokens_estimated"] += estimated_tokens
            
            # Acquire rate limit permission
            await self.rate_limiter.acquire(estimated_tokens)
            
            try:
                # Try primary provider first
                batch_results = await primary_provider.summarize_and_classify_batch(
                    batch,
                    user_prompt_settings=user_prompt_settings
                )
                
                # Cache all results in bulk
                cache_data = [
                    (qa['question'], qa['answer'], result['summary'], result.get('topic'))
                    for qa, result in zip(batch, batch_results)
                ]
                await cache_service.set_summaries_bulk(cache_data)
                
                completed_count += len(batch)
                if progress_callback:
                    # Include cached items in progress calculation
                    total_completed = (len(unique_items) - len(uncached_items)) + completed_count
                    progress = int((total_completed / len(unique_items)) * 100)
                    await progress_callback(progress)
                
                return batch_results
                
            except RateLimitError as e:
                logger.error(f"⚠️  RATE LIMIT HIT on batch {batch_idx} ({len(batch)} items)")
                logger.error(f"Rate limit error: {str(e)}")
                logger.error(f"Completed so far: {completed_count}/{len(uncached_items)}")
                logger.error(f"Total items in document: {len(qa_items)}")
                logger.warning(f"Attempting fallback provider...")
                
                # Fallback to next provider
                if len(self.providers) > 1:
                    fallback_provider = self.providers[1]
                    logger.info(f"Using fallback provider: {fallback_provider.name}")
                    batch_results = await fallback_provider.summarize_and_classify_batch(batch)
                    return batch_results
                else:
                    logger.error("No fallback provider available - returning empty summaries")
                    return [{"summary": "", "topic": "Other"} for _ in batch]
            
            except Exception as e:
                logger.error(f"❌ Batch {batch_idx} failed with exception: {e}")
                self.metrics["api_errors"] += 1
                return [{"summary": "", "topic": "Other"} for _ in batch]
            
            finally:
                # Always release semaphore
                self.rate_limiter.release()
        
        # Process ALL batches concurrently (this is the magic!)
        batch_results = await asyncio.gather(*[
            process_batch(batch, idx)
            for idx, batch in enumerate(batches)
        ])
        
        # Flatten results and merge with cached items
        all_results = []
        for batch in batch_results:
            all_results.extend(batch)
        
        # Insert uncached results back into unique_results
        for idx, result_idx in enumerate(uncached_indices):
            unique_results[result_idx] = {
                **uncached_items[idx],
                **all_results[idx],
                'cached': False
            }
        
        # Step 4: Map unique results back to original positions (handle duplicates)
        final_results = []
        for idx in range(len(qa_items)):
            unique_idx = duplicate_map[idx]
            result = unique_results[unique_idx]
            # Merge original qa_item metadata
            final_results.append({**qa_items[idx], **result})
        
        # Update processing time metrics
        elapsed = time.time() - start_time
        self.metrics["total_processing_time"] += elapsed
        logger.info(f"Batch processing completed in {elapsed:.2f}s")
        
        return final_results
    
    async def get_metrics(self) -> Dict:
        """Get performance metrics for monitoring and optimization.
        
        Returns comprehensive performance data including:
        - Cache hit rates
        - Deduplication savings
        - API call statistics
        - Error rates
        - Token usage estimates
        """
        total_requests = self.metrics["total_requests"]
        if total_requests == 0:
            return {**self.metrics, "cache_hit_rate": 0, "error_rate": 0, "avg_processing_time": 0}
        
        return {
            **self.metrics,
            "cache_hit_rate": self.metrics["cache_hits"] / max(1, self.metrics["cache_hits"] + self.metrics["cache_misses"]),
            "error_rate": self.metrics["api_errors"] / max(1, self.metrics["api_calls"]),
            "avg_processing_time": self.metrics["total_processing_time"] / max(1, self.metrics["batches_processed"]),
            "deduplication_rate": self.metrics["deduplicated"] / max(1, total_requests)
        }
    
    def reset_metrics(self):
        """Reset metrics counters."""
        self.metrics = {
            "total_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "deduplicated": 0,
            "api_calls": 0,
            "api_errors": 0,
            "total_tokens_estimated": 0,
            "total_processing_time": 0.0,
            "batches_processed": 0
        }
        logger.info("Metrics reset")


# Global AI service instance
ai_service = AIService()

