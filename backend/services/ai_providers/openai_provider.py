"""OpenAI API provider implementation."""
import asyncio
import json
from typing import List, Dict
import httpx

from .base_provider import BaseAIProvider, RateLimitError


class OpenAIProvider(BaseAIProvider):
    """OpenAI GPT-4 provider with optimal batch processing."""
    
    def __init__(self, api_key: str):
        super().__init__(api_key, "OpenAI")
        self.base_url = "https://api.openai.com/v1"
        self.model = "gpt-4o-mini"  # Fast and cost-effective
        self.max_tokens = 500
        self.temperature = 0.3
    
    async def summarize(self, question: str, answer: str, colloquy: str = None, timeout: int = 60) -> str:
        """Summarize single Q&A pair."""
        qa_text = f"Q: {question}\n"
        if colloquy:
            qa_text += f"[Colloquy: {colloquy}]\n"
        qa_text += f"A: {answer}"
        
        system_prompt = """You are a legal assistant summarizing deposition testimony.
Convert the Q&A exchange into a factual statement about what the witness testified.

CRITICAL: Do NOT repeat the question. Transform into a narrative statement.

Example:
Q: Where did you work in 2019?
A: I worked at ABC Corporation.
Summary: "The witness testified that they worked at ABC Corporation in 2019."

Rules:
- Write in third person ("The witness testified that...")
- Be concise (1-2 sentences)
- Include specific names, dates, numbers"""
        
        try:
            response = await self.client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": f"Summarize this testimony:\n\n{qa_text}"}
                        ],
                        "temperature": self.temperature,
                        "max_tokens": self.max_tokens
                    }
            )
            
            if response.status_code == 429:
                retry_after = response.headers.get('retry-after', 'unknown')
                self.logger.error(f"⚠️  RATE LIMIT: OpenAI API rate limit exceeded. Retry after: {retry_after}s")
                self.logger.error(f"Rate limit headers: {dict(response.headers)}")
                raise RateLimitError(f"OpenAI rate limit exceeded. Retry after: {retry_after}s")
            
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"].strip()
            
        except httpx.TimeoutException:
            self.logger.error(f"⏱️  TIMEOUT: OpenAI request timed out after {timeout}s")
            raise
        except RateLimitError:
            raise
        except Exception as e:
            self.logger.error(f"❌ OpenAI API error: {e}")
            raise
    
    async def summarize_batch(self, qa_items: List[Dict], timeout: int = 60) -> List[Dict]:
        """Summarize multiple Q&A pairs in one API call."""
        system_prompt = """You are a legal assistant summarizing deposition testimony.

You will receive NUMBERED Q&A exchanges. For EACH one, create a summary.

CRITICAL RULES:
1. Return a JSON array with EXACTLY one summary per input Q&A
2. The array length MUST match the number of inputs
3. Transform Q&A into narrative statements (DO NOT repeat the question)
4. Use third person ("The witness testified that...")
5. Be concise (1-2 sentences per summary)

Example input:
1. Q: Where did you work?
A: ABC Corp.

2. Q: When did you start?
A: January 2020.

Example output:
["The witness testified that they worked at ABC Corp.", "The witness stated they started in January 2020."]

IMPORTANT: Return ONLY a JSON array of strings. One string per input Q&A."""
        
        # Build user prompt with all Q&A items
        user_prompt = f"Summarize these {len(qa_items)} Q&A exchanges:\n\n"
        for i, qa in enumerate(qa_items, 1):
            qa_text = f"{i}. Q: {qa.get('question', '')}\n"
            if qa.get('colloquy'):
                qa_text += f"[Colloquy: {qa['colloquy']}]\n"
            qa_text += f"A: {qa.get('answer', '')}\n"
            user_prompt += qa_text + "\n"
        
        user_prompt += f"\nReturn a JSON array with EXACTLY {len(qa_items)} summary strings."
        
        try:
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": self.temperature,
                    "max_tokens": len(qa_items) * 100
                }
            )
            
            if response.status_code == 429:
                retry_after = response.headers.get('retry-after', 'unknown')
                remaining_requests = response.headers.get('x-ratelimit-remaining-requests', 'unknown')
                remaining_tokens = response.headers.get('x-ratelimit-remaining-tokens', 'unknown')
                self.logger.error(f"⚠️  RATE LIMIT (BATCH): OpenAI rate limit exceeded for batch of {len(qa_items)} items")
                self.logger.error(f"Retry after: {retry_after}s")
                self.logger.error(f"Remaining requests: {remaining_requests}, Remaining tokens: {remaining_tokens}")
                self.logger.error(f"Full headers: {dict(response.headers)}")
                raise RateLimitError(f"OpenAI batch rate limit exceeded. Items: {len(qa_items)}, Retry after: {retry_after}s")
            
            response.raise_for_status()
            result = response.json()
            content = result["choices"][0]["message"]["content"].strip()
            
            # Parse JSON - try multiple formats
            try:
                parsed = json.loads(content)
                
                # Handle different response formats
                if isinstance(parsed, list):
                    summaries = parsed
                elif isinstance(parsed, dict):
                    # Try common keys
                    summaries = parsed.get("summaries") or parsed.get("results") or parsed.get("data") or []
                    if not summaries and len(parsed) == 1:
                        # Single key with array value
                        summaries = list(parsed.values())[0]
                else:
                    summaries = []
                
                # Ensure we have strings
                if summaries and isinstance(summaries[0], dict):
                    summaries = [s.get("summary", str(s)) for s in summaries]
                
                if len(summaries) == len(qa_items):
                    return [{"summary": s, "topic": None} for s in summaries]
                else:
                    self.logger.warning(f"Result count mismatch: got {len(summaries)}, expected {len(qa_items)}")
                    # Pad or truncate
                    if len(summaries) < len(qa_items):
                        # Use what we have, fill rest with empty
                        results = [{"summary": s, "topic": None} for s in summaries]
                        results.extend([{"summary": "", "topic": None} for _ in range(len(qa_items) - len(summaries))])
                        return results
                    else:
                        return [{"summary": s, "topic": None} for s in summaries[:len(qa_items)]]
                        
            except json.JSONDecodeError:
                self.logger.warning("Failed to parse JSON, falling back to text parsing")
                # Fallback: split by newlines
                summaries = [s.strip() for s in content.split('\n') if s.strip()]
                return [{"summary": s, "topic": None} for s in summaries[:len(qa_items)]]
        
        except RateLimitError:
            raise
        except Exception as e:
            self.logger.error(f"❌ OpenAI batch API error: {e}")
            raise
    
    async def classify_topics(self, qa_items: List[Dict], timeout: int = 60) -> List[str]:
        """Classify topics for Q&A pairs."""
        system_prompt = """You are a legal assistant classifying deposition testimony topics.
For each Q&A exchange, assign ONE topic from this list:
- Background & Education
- Employment History
- Incident Description
- Medical Treatment
- Damages & Injuries
- Timeline & Chronology
- Documents & Evidence
- Witness Statements
- Expert Opinions
- Other

Return a JSON array of topic strings in the EXACT same order as input."""
        
        user_prompt = "Classify these Q&A exchanges:\n\n"
        for i, qa in enumerate(qa_items, 1):
            user_prompt += f"[{i}] Q: {qa.get('question', '')}\nA: {qa.get('answer', '')}\n\n"
        
        try:
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": 0.2,
                    "max_tokens": len(qa_items) * 20
                }
            )
            
            if response.status_code == 429:
                retry_after = response.headers.get('retry-after', 'unknown')
                remaining_requests = response.headers.get('x-ratelimit-remaining-requests', 'unknown')
                remaining_tokens = response.headers.get('x-ratelimit-remaining-tokens', 'unknown')
                self.logger.error(f"⚠️  RATE LIMIT (CLASSIFY): OpenAI rate limit exceeded for classification of {len(qa_items)} items")
                self.logger.error(f"Retry after: {retry_after}s, Remaining requests: {remaining_requests}, Remaining tokens: {remaining_tokens}")
                raise RateLimitError(f"OpenAI classify rate limit exceeded. Items: {len(qa_items)}, Retry after: {retry_after}s")
            
            response.raise_for_status()
            result = response.json()
            content = result["choices"][0]["message"]["content"].strip()
            
            topics = json.loads(content)
            return topics if isinstance(topics, list) else ["Other"] * len(qa_items)
        
        except RateLimitError:
            raise
        except Exception as e:
            self.logger.error(f"❌ OpenAI classify error: {e}")
            return ["Other"] * len(qa_items)
    
    async def summarize_and_classify_batch(self, qa_items: List[Dict], timeout: int = 60, _retry_mode: bool = False, user_prompt_settings: Dict = None) -> List[Dict]:
        """Optimized batch processing with JSON mode.
        
        Uses OpenAI's JSON mode for guaranteed structured output.
        
        Args:
            qa_items: List of Q&A dictionaries
            timeout: Request timeout in seconds
            _retry_mode: Internal flag to prevent infinite recursion on retries
            user_prompt_settings: User's custom prompt preferences
        """
        num_items = len(qa_items)
        
        # Build additional instructions from user settings
        additional_instructions = ""
        if user_prompt_settings:
            preset_options = user_prompt_settings.get("preset_options", {})
            custom_instructions = user_prompt_settings.get("custom_instructions")
            
            if preset_options:
                additional_instructions += "\n\nUser preferences:"
                if preset_options.get("witness_last_name"):
                    additional_instructions += "\n- Refer to witnesses by last name only"
                if preset_options.get("exclude_colloquy"):
                    additional_instructions += "\n- Exclude non-substantive colloquy and attorney dialogue"
                if preset_options.get("factual_only"):
                    additional_instructions += "\n- Focus exclusively on factual testimony, not opinions or speculation"
                if preset_options.get("include_objections"):
                    additional_instructions += "\n- Include context about objections and their outcomes"
                if preset_options.get("chronological_order"):
                    additional_instructions += "\n- Maintain strict chronological order of events"
                if preset_options.get("highlight_inconsistencies"):
                    additional_instructions += "\n- Note any contradictions or changes in testimony"
            
            if custom_instructions:
                additional_instructions += f"\n\nAdditional custom instructions from user:\n{custom_instructions}"
        
        system_prompt = f"""You are a legal assistant analyzing deposition testimony.

You will receive EXACTLY {num_items} NUMBERED Q&A exchanges. You MUST provide a SEPARATE summary for EACH numbered item.

CRITICAL REQUIREMENTS - READ CAREFULLY:
1. You will receive {num_items} numbered Q&A pairs (numbered 1 through {num_items})
2. You MUST return EXACTLY {num_items} summaries - one for each numbered input
3. The "results" array MUST contain EXACTLY {num_items} objects - NO MORE, NO LESS
4. DO NOT skip any numbered items
5. DO NOT combine multiple Q&A into one summary
6. Each object must have: {{"summary": "...", "topic": "..."}}

Summary rules:
- Transform each Q&A into a narrative statement (DO NOT repeat the question)
- Use third person: "The witness testified that..."
- Be concise: 1-2 sentences per summary
- Each summary must be unique and specific to its Q&A pair{additional_instructions}

Topics (pick one per Q&A): Background & Education, Employment History, Incident Description, Medical Treatment, Damages & Injuries, Timeline & Chronology, Documents & Evidence, Witness Statements, Expert Opinions, Other

EXAMPLE JSON for 2 inputs:
Input:
1. Q: Where did you work?
A: ABC Corp.

2. Q: When did you start?
A: January 2020.

Example JSON Output (MUST have exactly 2 items):
{{"results": [
  {{"summary": "The witness testified they worked at ABC Corp.", "topic": "Employment History"}},
  {{"summary": "The witness stated they started in January 2020.", "topic": "Employment History"}}
]}}

IMPORTANT: Return your response in JSON format with a "results" array.
VERIFICATION: Count the number of items in your "results" array. It MUST equal {num_items}. If it doesn't, you have made an error."""
        
        # More explicit user prompt with numbering
        user_prompt = f"You will analyze EXACTLY {num_items} Q&A exchanges. Return a summary for EACH one in JSON format:\n\n"
        for i, qa in enumerate(qa_items, 1):
            user_prompt += f"[{i}/{num_items}] Q: {qa['question']}\nA: {qa['answer']}\n\n"
        user_prompt += f"\nRemember: You received {num_items} Q&A pairs. Return EXACTLY {num_items} summaries in the 'results' array as JSON."
        
        try:
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "response_format": {"type": "json_object"},  # Must be json_object for structured output
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": 0.3,
                    "max_tokens": min(4000, num_items * 150)  # Cap at 4000 tokens, more per item
                }
            )
            
            if response.status_code == 429:
                retry_after = response.headers.get('retry-after', 'unknown')
                self.logger.error(f"⚠️  RATE LIMIT (COMBINED): OpenAI rate limit exceeded for {num_items} items")
                raise RateLimitError(f"OpenAI combined rate limit exceeded. Items: {num_items}, Retry after: {retry_after}s")
            
            if response.status_code == 400:
                # Log the error details for debugging
                try:
                    error_data = response.json()
                    self.logger.error(f"❌ OpenAI 400 Bad Request for {num_items} items:")
                    self.logger.error(f"Error: {error_data}")
                    self.logger.error(f"Request preview: model={self.model}, max_tokens={num_items * 120}, prompt_length={len(user_prompt)}")
                except:
                    error_text = response.text[:500]
                    self.logger.error(f"❌ OpenAI 400 Bad Request (non-JSON): {error_text}")
                # Return empty summaries instead of raising - allow processing to continue
                self.logger.warning(f"Returning empty summaries for {num_items} items due to 400 error")
                return [{"summary": "", "topic": "Other"} for _ in qa_items]
            
            response.raise_for_status()
            result = response.json()
            content = result["choices"][0]["message"]["content"].strip()
            
            # Log raw response for debugging
            self.logger.info(f"OpenAI raw response length: {len(content)} chars")
            self.logger.debug(f"OpenAI raw response preview: {content[:200]}...")
            
            # Parse JSON
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError as e:
                self.logger.error(f"❌ Failed to parse OpenAI JSON response: {e}")
                self.logger.error(f"Response content: {content[:500]}")
                raise
            
            # Handle different response formats
            if isinstance(parsed, dict) and "results" in parsed:
                results = parsed["results"]
                self.logger.debug(f"Found 'results' key with {len(results)} items")
            elif isinstance(parsed, list):
                results = parsed
                self.logger.debug(f"Response is direct array with {len(results)} items")
            elif isinstance(parsed, dict):
                # Try other common keys
                results = parsed.get("summaries") or parsed.get("data") or []
                if not results and len(parsed) == 1:
                    results = list(parsed.values())[0]
                    self.logger.debug(f"Found single key with {len(results) if isinstance(results, list) else 'non-list'} value")
                else:
                    self.logger.warning(f"Unexpected dict format: keys={list(parsed.keys())}")
            else:
                results = []
                self.logger.error(f"Unexpected response type: {type(parsed)}")
            
            # Validate and normalize results
            normalized = []
            for i, r in enumerate(results):
                if isinstance(r, dict):
                    summary_text = r.get("summary", "")
                    if not summary_text:
                        self.logger.warning(f"Result {i} has empty summary: {r}")
                    normalized.append({
                        "summary": summary_text,
                        "topic": r.get("topic", "Other")
                    })
                elif isinstance(r, str):
                    if not r.strip():
                        self.logger.warning(f"Result {i} is empty string")
                    normalized.append({"summary": r, "topic": "Other"})
                else:
                    self.logger.warning(f"Result {i} has unexpected type {type(r)}: {r}")
                    normalized.append({"summary": "", "topic": "Other"})
            
            if len(normalized) == num_items:
                # Check if any summaries are empty
                empty_count = sum(1 for n in normalized if not n["summary"].strip())
                if empty_count > 0:
                    self.logger.warning(f"⚠️ Got {num_items} results but {empty_count} are empty!")
                else:
                    self.logger.info(f"✅ Successfully got {num_items} summaries from OpenAI")
                return normalized
            
            # Handle count mismatch - don't return empty!
            self.logger.warning(f"Result count mismatch: got {len(normalized)}, expected {num_items}")
            self.logger.warning(f"First result preview: {normalized[0] if normalized else 'NONE'}")
            
            if len(normalized) > 0:
                # Check if we got any valid summaries
                valid_count = sum(1 for n in normalized if n["summary"].strip())
                self.logger.warning(f"Got {len(normalized)} results, {valid_count} have non-empty summaries")
                
                if len(normalized) == 1 and num_items > 1:
                    # OpenAI returned a single combined summary - try to split it
                    self.logger.error(f"❌ OpenAI returned 1 combined summary instead of {num_items} individual summaries")
                    self.logger.error(f"Combined summary: {normalized[0]['summary'][:200]}...")
                    # Try to split by common patterns
                    combined_text = normalized[0]["summary"]
                    # Look for numbered patterns or sentence breaks
                    import re
                    # Try splitting by numbered items (1., 2., etc.)
                    parts = re.split(r'\n\s*\d+[\.\)]\s*', combined_text)
                    if len(parts) > 1:
                        self.logger.info(f"Attempting to split combined summary into {len(parts)} parts")
                        normalized = []
                        for part in parts:
                            part = part.strip()
                            if part:
                                normalized.append({"summary": part, "topic": "Other"})
                        # If we got the right number, use it
                        if len(normalized) == num_items:
                            self.logger.info(f"✅ Successfully split combined summary into {num_items} parts")
                            return normalized
                    
                    # If splitting failed, return empty for all but log error
                    self.logger.error(f"❌ Could not split combined summary. Returning empty summaries.")
                    return [{"summary": "", "topic": "Other"} for _ in qa_items]
                
                if len(normalized) < num_items:
                    # OpenAI returned fewer results
                    missing = num_items - len(normalized)
                    missing_indices = list(range(len(normalized), num_items))
                    
                    if not _retry_mode:
                        # Retry missing items individually (only if not already in retry mode)
                        self.logger.warning(f"⚠️ OpenAI returned only {len(normalized)} results for {num_items} items. Retrying {missing} missing items individually...")
                        
                        # Process missing items one by one
                        for idx in missing_indices:
                            try:
                                qa = qa_items[idx]
                                # Retry with single item (set retry_mode=True to prevent recursion)
                                single_result = await self.summarize_and_classify_batch(
                                    [qa],
                                    timeout=timeout,
                                    _retry_mode=True,
                                    user_prompt_settings=user_prompt_settings
                                )
                                if single_result and len(single_result) > 0 and single_result[0].get("summary"):
                                    normalized.append(single_result[0])
                                    self.logger.info(f"✅ Retried item {idx+1}/{num_items} successfully")
                                else:
                                    self.logger.error(f"❌ Retry failed for item {idx+1}, using empty summary")
                                    normalized.append({"summary": "", "topic": "Other"})
                            except Exception as e:
                                self.logger.error(f"❌ Error retrying item {idx+1}: {e}")
                                normalized.append({"summary": "", "topic": "Other"})
                        
                        if len(normalized) == num_items:
                            valid_count = sum(1 for n in normalized if n["summary"].strip())
                            self.logger.info(f"✅ Successfully recovered all {num_items} summaries via retry ({valid_count} valid)")
                        return normalized
                    else:
                        # Already in retry mode - just pad with empty to avoid infinite recursion
                        self.logger.error(f"❌ In retry mode: OpenAI returned only {len(normalized)} results for {num_items} items. Padding {missing} with empty.")
                        while len(normalized) < num_items:
                            normalized.append({"summary": "", "topic": "Other"})
                        return normalized
                else:
                    # Truncate to expected count
                    normalized = normalized[:num_items]
                    # Check if any are empty
                    empty_count = sum(1 for n in normalized if not n["summary"].strip())
                    if empty_count > 0:
                        self.logger.warning(f"⚠️ {empty_count} summaries are empty out of {num_items}")
                    return normalized
            else:
                # No results at all - return empty but log error
                self.logger.error(f"❌ OpenAI returned no parseable results for {num_items} items")
                return [{"summary": "", "topic": "Other"} for _ in qa_items]
            
        except RateLimitError:
            raise
        except Exception as e:
            self.logger.error(f"❌ OpenAI combined API error: {e}")
            raise
