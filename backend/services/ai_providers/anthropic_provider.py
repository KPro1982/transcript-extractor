"""Anthropic Claude API provider implementation."""
import json
from typing import List, Dict

from .base_provider import BaseAIProvider, RateLimitError


class AnthropicProvider(BaseAIProvider):
    """Anthropic Claude provider for fallback."""
    
    def __init__(self, api_key: str):
        super().__init__(api_key, "Anthropic")
        self.base_url = "https://api.anthropic.com/v1"
        self.model = "claude-3-haiku-20240307"  # Fast and cost-effective
        self.max_tokens = 500
    
    async def summarize(self, question: str, answer: str, colloquy: str = None, timeout: int = 60) -> str:
        """Summarize single Q&A pair."""
        qa_text = f"Q: {question}\n"
        if colloquy:
            qa_text += f"[Colloquy: {colloquy}]\n"
        qa_text += f"A: {answer}"
        
        system_prompt = "You are a legal assistant. Provide concise 1-2 sentence summaries in third person."
        
        try:
            response = await self.client.post(
                    f"{self.base_url}/messages",
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "max_tokens": self.max_tokens,
                        "system": system_prompt,
                        "messages": [
                            {"role": "user", "content": f"Summarize this testimony:\n\n{qa_text}"}
                        ]
                    }
                )
                
                if response.status_code == 429:
                    raise RateLimitError("Anthropic rate limit exceeded")
                
            response.raise_for_status()
            result = response.json()
            return result["content"][0]["text"].strip()
            
        except Exception as e:
            self.logger.error(f"Anthropic API error: {e}")
            raise
    
    async def summarize_batch(self, qa_items: List[Dict], timeout: int = 60) -> List[Dict]:
        """Summarize multiple Q&A pairs."""
        system_prompt = """Summarize deposition testimony. Return a JSON array of summaries in the same order as input.
Format: ["Summary 1", "Summary 2", ...]"""
        
        user_prompt = "Summarize these Q&A exchanges:\n\n"
        for i, qa in enumerate(qa_items, 1):
            user_prompt += f"[{i}] Q: {qa.get('question', '')}\nA: {qa.get('answer', '')}\n\n"
        
        try:
            response = await self.client.post(
                    f"{self.base_url}/messages",
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "max_tokens": len(qa_items) * 80,
                        "system": system_prompt,
                        "messages": [
                            {"role": "user", "content": user_prompt}
                        ]
                    }
                )
                
                if response.status_code == 429:
                    raise RateLimitError("Anthropic rate limit exceeded")
                
                response.raise_for_status()
                result = response.json()
                content = result["content"][0]["text"].strip()
                
            summaries = json.loads(content)
            return [{"summary": s, "topic": None} for s in summaries]
            
        except Exception as e:
            self.logger.error(f"Anthropic batch error: {e}")
            raise
    
    async def classify_topics(self, qa_items: List[Dict], timeout: int = 60) -> List[str]:
        """Classify topics for Q&A pairs."""
        return ["Other"] * len(qa_items)  # Simplified for now
    
    async def summarize_and_classify_batch(self, qa_items: List[Dict], timeout: int = 60) -> List[Dict]:
        """Combined summarization and classification."""
        summaries = await self.summarize_batch(qa_items, timeout)
        return summaries

