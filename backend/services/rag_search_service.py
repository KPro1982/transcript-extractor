"""RAG search service for finding relevant Q&A items in deposition transcripts."""
import logging
import re
from typing import Dict, List, Set, Optional
import tiktoken

from openai import AsyncOpenAI
from config import settings

logger = logging.getLogger(__name__)


def detect_query_type(user_query: str) -> str:
    """
    Detect if query requires exhaustive search or relevance search.
    
    Args:
        user_query: User's question
        
    Returns:
        "exhaustive" or "relevance"
    """
    query_lower = user_query.lower()
    exhaustive_patterns = [
        "list all", "all occurrences", "every time",
        "where does", "show me all", "find all instances",
        "all mentions", "all references", "all times",
        "list by page", "list by line"
    ]
    
    if any(pattern in query_lower for pattern in exhaustive_patterns):
        return "exhaustive"
    return "relevance"


def extract_keywords(query: str) -> Set[str]:
    """
    Extract keywords from user query, removing stop words.
    
    Args:
        query: User's question
        
    Returns:
        Set of keywords (lowercased)
    """
    # Common stop words to filter out
    stop_words = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
        "be", "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "must", "can", "this", "that",
        "these", "those", "i", "you", "he", "she", "it", "we", "they",
        "what", "which", "who", "whom", "whose", "where", "when", "why",
        "how", "about", "into", "through", "during", "including", "against",
        "among", "throughout", "despite", "towards", "upon", "concerning"
    }
    
    # Extract words (alphanumeric sequences)
    words = re.findall(r'\b[a-zA-Z0-9]+\b', query.lower())
    
    # Filter out stop words and short words (< 2 chars)
    keywords = {w for w in words if w not in stop_words and len(w) > 2}
    
    return keywords


class RAGSearchService:
    """Service for searching and ranking Q&A items using RAG."""
    
    def __init__(self):
        # Use primary API key for re-ranking
        api_key = settings.openai_api_key_1 or settings.openai_api_key
        if not api_key:
            raise ValueError("OpenAI API key not configured. Set OPENAI_API_KEY_1 or OPENAI_API_KEY.")
        self.openai_client = AsyncOpenAI(api_key=api_key)
        self.model = "gpt-4o-mini"
        
        # Initialize tokenizer for token counting
        try:
            self.tokenizer = tiktoken.encoding_for_model("gpt-4o-mini")
        except Exception as e:
            logger.warning(f"Failed to load tiktoken: {e}")
            self.tokenizer = None
    
    async def search_relevant_qa_items(
        self,
        qa_items: List[Dict],
        user_query: str,
        max_results: int = 50
    ) -> List[Dict]:
        """
        Search and rank Q&A items by relevance.
        
        Args:
            qa_items: List of all Q&A items from the document
            user_query: User's question
            max_results: Maximum number of results for relevance queries
            
        Returns:
            List of ranked Q&A items with citations
        """
        query_type = detect_query_type(user_query)
        logger.info(f"Query type detected: {query_type} for query: {user_query[:100]}")
        
        if query_type == "exhaustive":
            return await self._exhaustive_search(qa_items, user_query)
        else:
            return await self._relevance_search(qa_items, user_query, max_results)
    
    async def _exhaustive_search(
        self,
        qa_items: List[Dict],
        user_query: str
    ) -> List[Dict]:
        """
        Find ALL matching Q&A items (no limit).
        
        Args:
            qa_items: List of all Q&A items
            user_query: User's question
            
        Returns:
            List of ALL matching Q&A items
        """
        keywords = extract_keywords(user_query)
        logger.info(f"Exhaustive search with keywords: {keywords}")
        
        if not keywords:
            # If no keywords extracted, return empty (shouldn't happen)
            logger.warning("No keywords extracted from query")
            return []
        
        matches = []
        for qa in qa_items:
            score = self._calculate_keyword_score(qa, keywords)
            if score > 0:
                # Add score to Q&A item for potential sorting
                qa_with_score = qa.copy()
                qa_with_score["relevance_score"] = score
                matches.append(qa_with_score)
        
        # Sort by score descending, then by page/line
        matches.sort(key=lambda x: (-x["relevance_score"], x["page"], x["line"]))
        
        logger.info(f"Exhaustive search found {len(matches)} matches")
        return matches
    
    async def _relevance_search(
        self,
        qa_items: List[Dict],
        user_query: str,
        max_results: int = 50
    ) -> List[Dict]:
        """
        Find top N most relevant Q&A items.
        
        Args:
            qa_items: List of all Q&A items
            user_query: User's question
            max_results: Maximum number of results
            
        Returns:
            List of top N most relevant Q&A items
        """
        # Step 1: Keyword-based filtering
        keywords = extract_keywords(user_query)
        logger.info(f"Relevance search with keywords: {keywords}")
        
        if not keywords:
            # If no keywords, return first N items
            logger.warning("No keywords extracted, returning first items")
            return qa_items[:max_results]
        
        # Score all items
        scored_items = []
        for qa in qa_items:
            score = self._calculate_keyword_score(qa, keywords)
            if score > 0:
                qa_with_score = qa.copy()
                qa_with_score["relevance_score"] = score
                scored_items.append(qa_with_score)
        
        # Sort by score and take top 100-200 candidates
        scored_items.sort(key=lambda x: -x["relevance_score"])
        top_candidates = scored_items[:min(200, len(scored_items))]
        
        logger.info(f"Keyword search found {len(scored_items)} matches, selecting top {len(top_candidates)} for re-ranking")
        
        # Step 2: OpenAI re-ranking (if we have candidates)
        if len(top_candidates) <= max_results:
            # Already have enough, just return them
            return top_candidates[:max_results]
        
        # Re-rank with OpenAI
        reranked = await self._rerank_with_openai(top_candidates, user_query, max_results)
        return reranked
    
    def _calculate_keyword_score(
        self,
        qa_item: Dict,
        keywords: Set[str]
    ) -> float:
        """
        Calculate relevance score for a Q&A item based on keyword matches.
        
        Scoring weights:
        - Topic matches: 5x
        - Summary matches: 3x
        - Question matches: 2x
        - Answer matches: 1x
        
        Args:
            qa_item: Q&A item dictionary
            keywords: Set of keywords to match
            
        Returns:
            Relevance score (0 if no matches)
        """
        score = 0.0
        
        # Normalize text for matching
        def normalize_text(text: str) -> str:
            if not text:
                return ""
            return text.lower()
        
        # Check topic (highest weight)
        topic = normalize_text(qa_item.get("topic", ""))
        if topic:
            for keyword in keywords:
                if keyword in topic:
                    score += 5.0
        
        # Check summary (high weight)
        summary = normalize_text(qa_item.get("summary", ""))
        if summary:
            for keyword in keywords:
                # Count occurrences
                count = summary.count(keyword)
                score += 3.0 * count
        
        # Check question (medium weight)
        question = normalize_text(qa_item.get("question", ""))
        if question:
            for keyword in keywords:
                count = question.count(keyword)
                score += 2.0 * count
        
        # Check answer (base weight)
        answer = normalize_text(qa_item.get("answer", ""))
        if answer:
            for keyword in keywords:
                count = answer.count(keyword)
                score += 1.0 * count
        
        return score
    
    async def _rerank_with_openai(
        self,
        candidates: List[Dict],
        user_query: str,
        top_k: int = 50
    ) -> List[Dict]:
        """
        Use OpenAI to re-rank candidates by semantic relevance.
        
        Args:
            candidates: List of candidate Q&A items (already scored)
            user_query: User's question
            top_k: Number of top items to return
            
        Returns:
            List of top K re-ranked items
        """
        if not candidates:
            return []
        
        # Build prompt for re-ranking
        # Format: Show user query and list of candidates with their current scores
        prompt_lines = [
            f"User Query: {user_query}",
            "",
            "Rank the following Q&A items by relevance to the user query. "
            "Return ONLY a comma-separated list of item numbers (1-N) in order of relevance, "
            "most relevant first. Do not include any explanation.",
            ""
        ]
        
        # Add candidates (limit to avoid token limits)
        max_candidates_for_rerank = min(200, len(candidates))
        for idx, qa in enumerate(candidates[:max_candidates_for_rerank], 1):
            # Create compact representation
            page = qa.get("page", 0)
            line = qa.get("line", 0)
            question_preview = qa.get("question", "")[:150]
            answer_preview = qa.get("answer", "")[:150]
            summary = qa.get("summary", "")[:100]
            
            prompt_lines.append(
                f"{idx}. [Page {page}, Line {line}] "
                f"Q: {question_preview}... "
                f"A: {answer_preview}... "
                f"Summary: {summary}..."
            )
        
        prompt = "\n".join(prompt_lines)
        
        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a ranking system. Return only comma-separated numbers."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.1  # Very deterministic for ranking
            )
            
            ranking_text = response.choices[0].message.content.strip()
            
            # Parse ranking: "1, 5, 3, 2, ..."
            ranked_indices = []
            for num_str in ranking_text.split(","):
                try:
                    idx = int(num_str.strip()) - 1  # Convert to 0-based
                    if 0 <= idx < len(candidates):
                        ranked_indices.append(idx)
                except ValueError:
                    continue
            
            # If ranking is invalid, fall back to original order
            if not ranked_indices or len(ranked_indices) < min(10, len(candidates)):
                logger.warning("Invalid ranking from OpenAI, using original order")
                return candidates[:top_k]
            
            # Return re-ranked items
            reranked = [candidates[idx] for idx in ranked_indices if idx < len(candidates)]
            return reranked[:top_k]
            
        except Exception as e:
            logger.error(f"OpenAI re-ranking failed: {e}, using original order")
            return candidates[:top_k]
    
    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text using tiktoken.
        
        Args:
            text: Text to count
            
        Returns:
            Number of tokens
        """
        if not text:
            return 0
        
        if self.tokenizer:
            try:
                return len(self.tokenizer.encode(text))
            except Exception as e:
                logger.warning(f"Token counting failed: {e}")
        
        # Fallback: rough estimate (1 token ≈ 4 characters)
        return len(text) // 4

