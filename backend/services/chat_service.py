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
from services.rag_search_service import RAGSearchService, detect_query_type
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
        self.default_max_tokens = 2000  # Default for relevance queries
        self.exhaustive_max_tokens = 4000  # Higher limit for exhaustive queries
        self.temperature = 0.3  # More deterministic for legal analysis
        
        # Initialize RAG search service
        self.rag_search = RAGSearchService()
        
        # Token budget for context (~8K tokens)
        self.context_token_budget = 8000
    
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
            
            # Use RAG search to find relevant Q&A items
            relevant_qas = await self.rag_search.search_relevant_qa_items(
                context["qa_items"],
                user_message,
                max_results=50
            )
            
            logger.info(f"RAG search found {len(relevant_qas)} relevant Q&A items")
            
            # Load recent chat history (last 10 messages)
            history = await self._load_chat_history(session_id, limit=10)
            
            # Build prompt with RAG-searched Q&A items
            system_prompt = self._build_system_prompt()
            query_type = detect_query_type(user_message)
            context_prompt = self._build_context_prompt(
                context["metadata"],
                relevant_qas,
                query_type=query_type
            )
            
            # Determine max_tokens based on query type
            if query_type == "exhaustive":
                max_response_tokens = self.exhaustive_max_tokens
                logger.info(f"Using exhaustive query max_tokens: {max_response_tokens}")
            else:
                max_response_tokens = self.default_max_tokens
                logger.info(f"Using relevance query max_tokens: {max_response_tokens}")
            
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
            logger.info(f"Calling OpenAI for session {session_id} with max_tokens={max_response_tokens}")
            response = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_response_tokens,
                temperature=self.temperature
            )
            
            # Extract response
            assistant_content = response.choices[0].message.content
            
            # Extract citations with enhanced support for question/answer distinction
            citations = self._extract_citations(assistant_content, relevant_qas)
            
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
- For queries asking to "list all occurrences" or "all references", provide a comprehensive list with page/line citations for EVERY match
- Identify patterns such as conflicts, corrections, and refusals to answer
- Provide strategic insights for trial preparation
- Be precise, concise, and professional

Citation Rules:
- Format citations as [Page X, Line Y] for single locations
- Format multi-page citations as [Page X, Line Y - Page Z, Line W] when answers span pages
- Format line ranges as [Page X, Lines Y-Z] when within the same page
- When referencing testimony, include a brief quote
- Cite multiple sources when applicable
- Clearly indicate whether information comes from the question (Q:) or answer (A:)

Remember: Accuracy is paramount. If you're unsure, say so and explain why."""
    
    def _build_context_prompt(
        self,
        metadata: Dict,
        relevant_qas: List[Dict],
        query_type: str = "relevance"
    ) -> str:
        """
        Build context section with metadata and relevant Q&As.
        
        Args:
            metadata: Document metadata
            relevant_qas: List of relevant Q&A items from RAG search
            query_type: "exhaustive" or "relevance"
        """
        lines = ["DOCUMENT INFORMATION:"]
        
        if metadata.get("case_name"):
            lines.append(f"Case: {metadata['case_name']}")
        if metadata.get("witness_name"):
            lines.append(f"Witness: {metadata['witness_name']}")
        if metadata.get("deposition_date"):
            lines.append(f"Date: {metadata['deposition_date']}")
        lines.append(f"Total Pages: {metadata['total_pages']}")
        lines.append("")
        
        if query_type == "exhaustive":
            lines.append(f"ALL MATCHING Q&A ITEMS ({len(relevant_qas)} total):")
        else:
            lines.append(f"RELEVANT Q&A ITEMS ({len(relevant_qas)} items):")
        lines.append("")
        
        # Track token usage
        current_tokens = self.rag_search.count_tokens("\n".join(lines))
        max_context_tokens = self.context_token_budget
        
        # Format Q&A items based on query type
        items_added = 0
        for idx, qa in enumerate(relevant_qas, 1):
            if query_type == "exhaustive":
                # Compact format for exhaustive queries
                item_text = self._format_qa_item_compact(qa, idx)
            else:
                # Full format for relevance queries
                item_text = self._format_qa_item_full(qa, idx)
            
            item_tokens = self.rag_search.count_tokens(item_text)
            
            # Check if adding this item would exceed budget
            if current_tokens + item_tokens > max_context_tokens:
                logger.warning(
                    f"Token budget reached: {current_tokens}/{max_context_tokens} tokens. "
                    f"Included {items_added}/{len(relevant_qas)} items."
                )
                break
            
            lines.append(item_text)
            current_tokens += item_tokens
            items_added += 1
        
        if items_added < len(relevant_qas):
            lines.append("")
            lines.append(f"(Note: Showing {items_added} of {len(relevant_qas)} matching items due to token limits)")
        
        return "\n".join(lines)
    
    def _format_qa_item_compact(self, qa: Dict, idx: int) -> str:
        """
        Format Q&A item in compact format for exhaustive queries.
        
        Args:
            qa: Q&A item dictionary
            idx: Item index
            
        Returns:
            Formatted string
        """
        page = qa.get("page", 0)
        line = qa.get("line", 0)
        answer_end_page = qa.get("answer_end_page")
        answer_end_line = qa.get("answer_end_line")
        
        # Build citation string
        if answer_end_page and answer_end_page != page:
            citation = f"[Page {page}, Line {line} - Page {answer_end_page}, Line {answer_end_line}]"
        elif answer_end_line and answer_end_line != line:
            citation = f"[Page {page}, Lines {line}-{answer_end_line}]"
        else:
            citation = f"[Page {page}, Line {line}]"
        
        question = qa.get("question", "")
        answer = qa.get("answer", "")
        
        # Truncate for compact format (keep it brief)
        question_preview = question[:150] + "..." if len(question) > 150 else question
        answer_preview = answer[:200] + "..." if len(answer) > 200 else answer
        
        lines = [
            f"[Q&A #{idx} - {citation}]",
            f"Q: {question_preview}",
            f"A: {answer_preview}",
            "---"
        ]
        
        return "\n".join(lines)
    
    def _format_qa_item_full(self, qa: Dict, idx: int) -> str:
        """
        Format Q&A item in full format for relevance queries.
        
        Args:
            qa: Q&A item dictionary
            idx: Item index
            
        Returns:
            Formatted string
        """
        page = qa.get("page", 0)
        line = qa.get("line", 0)
        answer_end_page = qa.get("answer_end_page")
        answer_end_line = qa.get("answer_end_line")
        
        # Build citation string
        if answer_end_page and answer_end_page != page:
            citation = f"[Page {page}, Line {line} - Page {answer_end_page}, Line {answer_end_line}]"
        elif answer_end_line and answer_end_line != line:
            citation = f"[Page {page}, Lines {line}-{answer_end_line}]"
        else:
            citation = f"[Page {page}, Line {line}]"
        
        lines = [
            f"[Q&A #{idx} - {citation}]",
            f"Topic: {qa.get('topic', 'Other')}"
        ]
        
        if qa.get('event_date'):
            lines.append(f"Date Reference: {qa['event_date']}")
        
        if qa.get('summary'):
            lines.append(f"Summary: {qa['summary']}")
        
        lines.append(f"Q: {qa.get('question', '')}")
        lines.append(f"A: {qa.get('answer', '')}")
        lines.append("---")
        
        return "\n".join(lines)
    
    def _extract_citations(
        self,
        response_text: str,
        qa_items: List[Dict]
    ) -> List[Dict]:
        """
        Extract citations from AI response with enhanced support for:
        - Multi-page citations
        - Question vs answer source distinction
        - Line range citations
        """
        import re
        citations = []
        seen_citations = set()  # Avoid duplicates
        
        # Pattern 1: Single page/line [Page 5, Line 12]
        # Pattern 2: Line range [Page 5, Lines 12-15]
        # Pattern 3: Multi-page [Page 5, Line 12 - Page 6, Line 5]
        pattern1 = r'\[(?:Page|Pg)\s+(\d+),\s+(?:Line|Ln)\s+(\d+)\]'
        pattern2 = r'\[(?:Page|Pg)\s+(\d+),\s+Lines\s+(\d+)-(\d+)\]'
        pattern3 = r'\[(?:Page|Pg)\s+(\d+),\s+(?:Line|Ln)\s+(\d+)\s*-\s*(?:Page|Pg)\s+(\d+),\s+(?:Line|Ln)\s+(\d+)\]'
        
        # Match single page/line
        for page_str, line_str in re.findall(pattern1, response_text, re.IGNORECASE):
            page = int(page_str)
            line = int(line_str)
            citation_key = (page, line)
            
            if citation_key in seen_citations:
                continue
            
            # Find matching Q&A item
            qa_match = self._find_qa_by_page_line(qa_items, page, line)
            if qa_match:
                citations.append({
                    "qa_item_id": qa_match['qa_item_id'],
                    "page": page,
                    "line": line,
                    "answer_end_page": qa_match.get("answer_end_page"),
                    "answer_end_line": qa_match.get("answer_end_line"),
                    "source_type": "answer",  # Default to answer
                    "text_snippet": qa_match.get('answer', '')[:100],
                    "is_multi_page": qa_match.get("answer_end_page") and qa_match.get("answer_end_page") != page
                })
                seen_citations.add(citation_key)
        
        # Match line range
        for page_str, line_start_str, line_end_str in re.findall(pattern2, response_text, re.IGNORECASE):
            page = int(page_str)
            line_start = int(line_start_str)
            line_end = int(line_end_str)
            citation_key = (page, line_start, line_end)
            
            if citation_key in seen_citations:
                continue
            
            # Find matching Q&A item (match by start line)
            qa_match = self._find_qa_by_page_line(qa_items, page, line_start)
            if qa_match:
                citations.append({
                    "qa_item_id": qa_match['qa_item_id'],
                    "page": page,
                    "line": line_start,
                    "answer_end_page": page,
                    "answer_end_line": line_end,
                    "source_type": "answer",
                    "text_snippet": qa_match.get('answer', '')[:100],
                    "is_multi_page": False
                })
                seen_citations.add(citation_key)
        
        # Match multi-page
        for page1_str, line1_str, page2_str, line2_str in re.findall(pattern3, response_text, re.IGNORECASE):
            page1 = int(page1_str)
            line1 = int(line1_str)
            page2 = int(page2_str)
            line2 = int(line2_str)
            citation_key = (page1, line1, page2, line2)
            
            if citation_key in seen_citations:
                continue
            
            # Find matching Q&A item
            qa_match = self._find_qa_by_page_line(qa_items, page1, line1)
            if qa_match:
                citations.append({
                    "qa_item_id": qa_match['qa_item_id'],
                    "page": page1,
                    "line": line1,
                    "answer_end_page": page2,
                    "answer_end_line": line2,
                    "source_type": "answer",
                    "text_snippet": qa_match.get('answer', '')[:100],
                    "is_multi_page": True
                })
                seen_citations.add(citation_key)
        
        return citations
    
    def _find_qa_by_page_line(
        self,
        qa_items: List[Dict],
        page: int,
        line: int
    ) -> Optional[Dict]:
        """
        Find Q&A item by page and line number.
        
        Args:
            qa_items: List of Q&A items
            page: Page number
            line: Line number
            
        Returns:
            Matching Q&A item or None
        """
        for qa in qa_items:
            if qa.get('page') == page and qa.get('line') == line:
                return qa
        return None
    
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

