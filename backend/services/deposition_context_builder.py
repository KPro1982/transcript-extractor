"""Service for building deposition context for chat RAG."""
import json
import logging
from typing import Dict, List, Optional
from uuid import UUID

from services.db_service import db_service
from services.cache_service import cache_service

logger = logging.getLogger(__name__)


class DepositionContextBuilder:
    """Build comprehensive context from deposition data for chat."""
    
    def __init__(self):
        self.cache_ttl = 24 * 3600  # 24 hours
    
    async def build_full_context(self, document_id: UUID) -> Dict:
        """
        Build complete context including metadata and all Q&A items.
        
        Args:
            document_id: UUID of the document
            
        Returns:
            Dictionary with:
            - metadata: Document info (case, witness, etc.)
            - qa_items: List of all Q&A items with summaries
        """
        # Check cache first
        cached = await self.get_cached_context(document_id)
        if cached:
            logger.info(f"Context cache hit for document {document_id}")
            return cached
        
        logger.info(f"Building context for document {document_id}")
        
        # Get document metadata
        doc = await db_service.fetchrow(
            """
            SELECT id, filename, case_name, case_number, deposition_date,
                   witness_name, total_pages, attorneys
            FROM documents
            WHERE id = $1
            """,
            document_id
        )
        
        if not doc:
            raise ValueError(f"Document {document_id} not found")
        
        metadata = {
            "document_id": str(doc["id"]),
            "filename": doc["filename"],
            "case_name": doc.get("case_name"),
            "case_number": doc.get("case_number"),
            "deposition_date": doc.get("deposition_date"),
            "witness_name": doc.get("witness_name"),
            "total_pages": doc["total_pages"],
            "attorneys": doc.get("attorneys", [])
        }
        
        # Get all Q&A items with summaries
        qa_rows = await db_service.fetch(
            """
            SELECT id, page_number, line_number, pdf_page_index,
                   answer_end_page, answer_end_line,
                   question, answer, summary, topic, event_date
            FROM final_qa_items
            WHERE document_id = $1
            ORDER BY page_number, line_number
            """,
            document_id
        )
        
        qa_items = []
        for row in qa_rows:
            qa_items.append({
                "qa_item_id": str(row["id"]),
                "page": row["page_number"],
                "line": row["line_number"],
                "pdf_page_index": row["pdf_page_index"],
                "answer_end_page": row["answer_end_page"],
                "answer_end_line": row["answer_end_line"],
                "question": row["question"],
                "answer": row["answer"],
                "summary": row["summary"] or "",
                "topic": row["topic"] or "Other",
                "event_date": row["event_date"]
            })
        
        context = {
            "metadata": metadata,
            "qa_items": qa_items,
            "total_qa_items": len(qa_items)
        }
        
        # Cache the context
        await self.cache_context(document_id, context)
        
        logger.info(f"Built context: {len(qa_items)} Q&A items")
        return context
    
    async def get_cached_context(self, document_id: UUID) -> Optional[Dict]:
        """Get context from Redis cache."""
        cache_key = f"chat_context:{document_id}"
        try:
            cached_json = await cache_service.get(cache_key)
            if cached_json:
                return json.loads(cached_json)
        except Exception as e:
            logger.warning(f"Cache read error: {e}")
        return None
    
    async def cache_context(self, document_id: UUID, context: Dict):
        """Store context in Redis with 24hr TTL."""
        cache_key = f"chat_context:{document_id}"
        try:
            await cache_service.set(
                cache_key,
                json.dumps(context),
                ex=self.cache_ttl
            )
            logger.info(f"Cached context for {document_id}")
        except Exception as e:
            logger.warning(f"Cache write error: {e}")
    
    async def invalidate_cache(self, document_id: UUID):
        """Invalidate cached context for a document."""
        cache_key = f"chat_context:{document_id}"
        try:
            await cache_service.delete(cache_key)
            logger.info(f"Invalidated cache for {document_id}")
        except Exception as e:
            logger.warning(f"Cache delete error: {e}")
    
    async def get_qa_items_subset(
        self,
        document_id: UUID,
        qa_item_ids: List[UUID]
    ) -> List[Dict]:
        """
        Get specific Q&A items by IDs.
        
        Args:
            document_id: UUID of the document
            qa_item_ids: List of Q&A item UUIDs
            
        Returns:
            List of Q&A item dictionaries
        """
        if not qa_item_ids:
            return []
        
        rows = await db_service.fetch(
            """
            SELECT id, page_number, line_number, pdf_page_index,
                   answer_end_page, answer_end_line,
                   question, answer, summary, topic, event_date
            FROM final_qa_items
            WHERE document_id = $1 AND id = ANY($2)
            ORDER BY page_number, line_number
            """,
            document_id,
            qa_item_ids
        )
        
        qa_items = []
        for row in rows:
            qa_items.append({
                "qa_item_id": str(row["id"]),
                "page": row["page_number"],
                "line": row["line_number"],
                "pdf_page_index": row["pdf_page_index"],
                "answer_end_page": row["answer_end_page"],
                "answer_end_line": row["answer_end_line"],
                "question": row["question"],
                "answer": row["answer"],
                "summary": row["summary"] or "",
                "topic": row["topic"] or "Other",
                "event_date": row["event_date"]
            })
        
        return qa_items


# Global instance
context_builder = DepositionContextBuilder()

