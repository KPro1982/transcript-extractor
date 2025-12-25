"""Chat service for handling deposition Q&A interactions."""
import json
import logging
from typing import Dict, List, Optional, AsyncGenerator
from uuid import UUID
from datetime import datetime

from openai import AsyncOpenAI

from config import settings
from services.db_service import persistent_db_service
from services.deposition_context_builder import context_builder
from models.chat_models import Citation

logger = logging.getLogger(__name__)


class ChatService:
    """Handle chat interactions with deposition RAG."""
    
    def __init__(self):
        # Use primary API key (openai_api_key_1 or openai_api_key fallback)
        api_key = settings.openai_api_key_1 or settings.openai_api_key
        if not api_key:
            raise ValueError("OpenAI API key not configured. Set OPENAI_API_KEY_1 or OPENAI_API_KEY.")
        self.openai_client = AsyncOpenAI(api_key=api_key)
        self.model = "gpt-4o-mini"  # Use same model as summarization
        self.max_tokens = 1000
        self.temperature = 0.3  # More deterministic for legal analysis
    
    async def generate_response(
        self,
        session_id: UUID,
        user_message: str,
        stream: bool = False
    ) -> Dict:
        """
        Generate AI response using RAG.
        
        Args:
            session_id: UUID of the chat session
            user_message: User's question
            stream: Whether to stream the response
            
        Returns:
            Dictionary with message_id, content, citations, created_at
        """
        try:
            # Get session info
            session = await persistent_db_service.fetchrow(
                """
                SELECT id, user_id, document_id, title
                FROM chat_sessions
                WHERE id = $1
                """,
                session_id
            )
            
            if not session:
                raise ValueError(f"Chat session {session_id} not found")
            
            document_id = session["document_id"]
            
            # Save user message first
            user_msg_id = await self._save_message(
                session_id,
                "user",
                user_message,
                None
            )
            
            # Load document context
            context = await context_builder.build_full_context(document_id)
            
            # Load recent chat history (last 10 messages)
            history = await self._load_chat_history(session_id, limit=10)
            
            # Build prompt (basic version without RAG semantic search for now)
            system_prompt = self._build_system_prompt()
            context_prompt = self._build_context_prompt(
                context["metadata"],
                context["qa_items"][:30]  # Use first 30 Q&As for now
            )
            
            # Prepare messages for OpenAI
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "system", "content": context_prompt}
            ]
            
            # Add chat history
            for msg in history[:-1]:  # Exclude the user message we just saved
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
            
            # Add current user message
            messages.append({
                "role": "user",
                "content": user_message
            })
            
            # Call OpenAI
            logger.info(f"Calling OpenAI for session {session_id}")
            response = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )
            
            # Extract response
            assistant_content = response.choices[0].message.content
            
            # Extract citations (basic pattern matching for now)
            citations = self._extract_citations(assistant_content, context["qa_items"])
            
            # Save assistant message
            assistant_msg_id = await self._save_message(
                session_id,
                "assistant",
                assistant_content,
                citations
            )
            
            # Update session timestamp
            await persistent_db_service.execute(
                """
                UPDATE chat_sessions
                SET updated_at = NOW()
                WHERE id = $1
                """,
                session_id
            )
            
            return {
                "message_id": assistant_msg_id,
                "role": "assistant",
                "content": assistant_content,
                "citations": citations,
                "created_at": datetime.utcnow()
            }
            
        except Exception as e:
            logger.error(f"Chat response generation failed: {e}", exc_info=True)
            raise
    
    def _build_system_prompt(self) -> str:
        """Build system prompt for legal assistant."""
        return """You are an expert legal assistant analyzing a deposition transcript. You have access to:

1. Complete Q&A pairs from the deposition with AI-generated summaries
2. Document metadata (case information, witness name, deposition date)
3. The ability to cite specific locations in the transcript

Your responsibilities:
- Answer questions about the deposition accurately and thoroughly
- ALWAYS provide citations with page and line numbers for your statements
- Identify patterns such as conflicts, corrections, and refusals to answer
- Provide strategic insights for trial preparation
- Be precise, concise, and professional

Citation Rules:
- Format citations as [Page X, Line Y]
- When referencing testimony, include a brief quote
- Cite multiple sources when applicable

Remember: Accuracy is paramount. If you're unsure, say so and explain why."""
    
    def _build_context_prompt(
        self,
        metadata: Dict,
        relevant_qas: List[Dict]
    ) -> str:
        """Build context section with metadata and relevant Q&As."""
        lines = ["DOCUMENT INFORMATION:"]
        
        if metadata.get("case_name"):
            lines.append(f"Case: {metadata['case_name']}")
        if metadata.get("witness_name"):
            lines.append(f"Witness: {metadata['witness_name']}")
        if metadata.get("deposition_date"):
            lines.append(f"Date: {metadata['deposition_date']}")
        lines.append(f"Total Pages: {metadata['total_pages']}")
        lines.append("")
        
        lines.append("RELEVANT Q&A ITEMS:")
        lines.append("")
        
        for idx, qa in enumerate(relevant_qas[:20], 1):  # Limit to top 20
            lines.append(f"[Q&A #{idx} - Page {qa['page']}, Line {qa['line']}]")
            lines.append(f"Topic: {qa['topic']}")
            if qa.get('event_date'):
                lines.append(f"Date Reference: {qa['event_date']}")
            if qa['summary']:
                lines.append(f"Summary: {qa['summary']}")
            lines.append(f"Question: {qa['question'][:200]}...")
            lines.append(f"Answer: {qa['answer'][:200]}...")
            lines.append("---")
            lines.append("")
        
        return "\n".join(lines)
    
    def _extract_citations(
        self,
        response_text: str,
        qa_items: List[Dict]
    ) -> List[Dict]:
        """
        Extract citations from AI response.
        For now, use basic pattern matching: [Page X, Line Y]
        """
        import re
        citations = []
        
        # Pattern: [Page 5, Line 12] or [Page 5, Ln 12] or [Pg 5, Line 12]
        pattern = r'\[(?:Page|Pg)\s+(\d+),\s+(?:Line|Ln)\s+(\d+)\]'
        
        matches = re.findall(pattern, response_text, re.IGNORECASE)
        
        for page_str, line_str in matches:
            page = int(page_str)
            line = int(line_str)
            
            # Find matching Q&A item
            for qa in qa_items:
                if qa['page'] == page and qa['line'] == line:
                    citations.append({
                        "qa_item_id": qa['qa_item_id'],
                        "page": page,
                        "line": line,
                        "text_snippet": qa['answer'][:100]
                    })
                    break
        
        return citations
    
    async def _save_message(
        self,
        session_id: UUID,
        role: str,
        content: str,
        citations: Optional[List[Dict]]
    ) -> UUID:
        """Save a chat message to the database."""
        citations_json = json.dumps(citations) if citations else None
        
        msg_id = await persistent_db_service.fetchval(
            """
            INSERT INTO depo_chat_messages (session_id, role, content, citations)
            VALUES ($1, $2, $3, $4)
            RETURNING id
            """,
            session_id,
            role,
            content,
            citations_json
        )
        
        return msg_id
    
    async def _load_chat_history(
        self,
        session_id: UUID,
        limit: int = 10
    ) -> List[Dict]:
        """Load recent chat history for context."""
        rows = await persistent_db_service.fetch(
            """
            SELECT id, role, content, citations, created_at
            FROM depo_chat_messages
            WHERE session_id = $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            session_id,
            limit
        )
        
        # Reverse to get chronological order
        messages = []
        for row in reversed(rows):
            messages.append({
                "id": str(row["id"]),
                "role": row["role"],
                "content": row["content"],
                "citations": json.loads(row["citations"]) if row["citations"] else [],
                "created_at": row["created_at"]
            })
        
        return messages


# Global instance
chat_service = ChatService()

