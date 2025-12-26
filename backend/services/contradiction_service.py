"""Service for detecting contradictions between claims."""
import logging
import json
import re
from typing import List, Dict, Optional, Tuple
from uuid import UUID
from openai import AsyncOpenAI

from services.db_service import db_service
from config import settings

logger = logging.getLogger(__name__)

# Initialize OpenAI client
openai_client = AsyncOpenAI(api_key=settings.openai_api_key_1 or settings.openai_api_key)


class ContradictionService:
    """Service for detecting contradictions between atomic claims."""
    
    def __init__(self):
        pass
    
    async def find_contradiction_candidates(
        self,
        document_id: UUID
    ) -> List[Tuple[Dict, Dict]]:
        """
        Find candidate claim pairs that might be contradictory using indexed retrieval.
        
        Matches candidates by:
        - Same subject + predicate (different object)
        - Same event_id
        - Same normalized entities
        
        Args:
            document_id: Document UUID
            
        Returns:
            List of (claim_a, claim_b) tuples
        """
        # Get all claims for document
        claims = await db_service.fetch(
            """
            SELECT 
                id, document_id, qa_item_id, subject, predicate, object,
                time, location, polarity, certainty, modality, scope,
                explicit_date, inferred_date, date_source, date_anchor,
                page_number, line_number, answer_end_page, answer_end_line,
                raw_quote, normalized_subject, normalized_object, event_id
            FROM claims
            WHERE document_id = $1
            ORDER BY page_number, line_number
            """,
            document_id
        )
        
        claims_list = [dict(claim) for claim in claims]
        logger.info(f"Loaded {len(claims_list)} claims for contradiction detection")
        
        # Find candidates using indexed matching
        candidates = []
        
        # Strategy 1: Same subject + predicate, different object
        subject_predicate_map = {}
        for claim in claims_list:
            key = (claim['normalized_subject'] or claim['subject'], claim['predicate'])
            if key not in subject_predicate_map:
                subject_predicate_map[key] = []
            subject_predicate_map[key].append(claim)
        
        for key, claims_group in subject_predicate_map.items():
            if len(claims_group) > 1:
                # Compare all pairs in this group
                for i in range(len(claims_group)):
                    for j in range(i + 1, len(claims_group)):
                        claim_a = claims_group[i]
                        claim_b = claims_group[j]
                        
                        # Check if objects differ or polarity differs
                        if claim_a['object'] != claim_b['object'] or claim_a['polarity'] != claim_b['polarity']:
                            candidates.append((claim_a, claim_b))
        
        # Strategy 2: Same event_id
        event_map = {}
        for claim in claims_list:
            if claim['event_id'] and claim['event_id'] != 'unclustered':
                if claim['event_id'] not in event_map:
                    event_map[claim['event_id']] = []
                event_map[claim['event_id']].append(claim)
        
        for event_id, claims_group in event_map.items():
            if len(claims_group) > 1:
                # Compare all pairs in this event
                for i in range(len(claims_group)):
                    for j in range(i + 1, len(claims_group)):
                        claim_a = claims_group[i]
                        claim_b = claims_group[j]
                        
                        # Add to candidates if not already present
                        if (claim_a, claim_b) not in candidates and (claim_b, claim_a) not in candidates:
                            candidates.append((claim_a, claim_b))
        
        logger.info(f"Found {len(candidates)} candidate contradiction pairs")
        return candidates
    
    def deterministic_filter(
        self,
        claim_a: Dict,
        claim_b: Dict
    ) -> Optional[Dict]:
        """
        Stage 1: Apply deterministic filters to quickly identify obvious contradictions.
        
        Returns:
            Contradiction dict if detected, None otherwise
        """
        # Filter 1: Exact negation patterns
        polarity_a = claim_a.get('polarity', 'positive')
        polarity_b = claim_b.get('polarity', 'positive')
        
        if polarity_a != polarity_b:
            # One positive, one negative on same subject+predicate
            if (claim_a['subject'] == claim_b['subject'] and 
                claim_a['predicate'] == claim_b['predicate']):
                return {
                    'contradiction_type': 'direct_negation',
                    'confidence': 95,
                    'severity': 90,
                    'explanation': f"Direct negation: '{claim_a['subject']} {claim_a['predicate']}' stated as both positive and negative."
                }
        
        # Filter 2: Numeric/quantity conflicts
        obj_a = str(claim_a.get('object', ''))
        obj_b = str(claim_b.get('object', ''))
        
        # Extract numbers from objects
        numbers_a = re.findall(r'\d+', obj_a)
        numbers_b = re.findall(r'\d+', obj_b)
        
        if numbers_a and numbers_b:
            try:
                num_a = int(numbers_a[0])
                num_b = int(numbers_b[0])
                
                # Check for significant difference (>10% or absolute >5)
                diff = abs(num_a - num_b)
                if diff > 5 and (diff / max(num_a, num_b)) > 0.1:
                    return {
                        'contradiction_type': 'quantity_conflict',
                        'confidence': 80,
                        'severity': 70,
                        'explanation': f"Quantity conflict: {num_a} vs {num_b} for same subject/predicate."
                    }
            except (ValueError, IndexError):
                pass
        
        # Filter 3: Mutually exclusive values (yes/no, true/false, etc.)
        exclusive_pairs = [
            ('yes', 'no'),
            ('true', 'false'),
            ('present', 'absent'),
            ('before', 'after'),
            ('always', 'never')
        ]
        
        obj_a_lower = obj_a.lower()
        obj_b_lower = obj_b.lower()
        
        for val1, val2 in exclusive_pairs:
            if (val1 in obj_a_lower and val2 in obj_b_lower) or (val2 in obj_a_lower and val1 in obj_b_lower):
                return {
                    'contradiction_type': 'mutually_exclusive',
                    'confidence': 85,
                    'severity': 85,
                    'explanation': f"Mutually exclusive values: '{obj_a}' vs '{obj_b}'."
                }
        
        # No deterministic contradiction found
        return None
    
    async def llm_verification(
        self,
        claim_a: Dict,
        claim_b: Dict
    ) -> Optional[Dict]:
        """
        Stage 2: Use LLM to verify if claims are actually contradictory.
        
        Args:
            claim_a: First claim dictionary
            claim_b: Second claim dictionary
            
        Returns:
            Contradiction dict if verified, None otherwise
        """
        system_prompt = """You are a legal assistant analyzing deposition testimony for contradictions.

Analyze two claims extracted from testimony and determine if they are contradictory.

CONTRADICTION TYPES:
1. direct_negation: One claim affirms what the other denies
   Example: "I was alone" vs "My sister was with me"

2. mutually_exclusive: Claims state incompatible specifics
   Example: "I was at home" vs "I was at work" (same time)

3. quantity_conflict: Numerical/extent disagreements
   Example: "No prior injuries" vs "I hurt my knee in 2019"

4. memory_drift: Uncertainty changed to certainty
   Example: "I don't recall" → "Yes, definitely"

5. scope_mismatch: Mismatched qualifications (NOT a contradiction if properly scoped)
   Example: "No injuries in last 10 years" vs "Knee injury 15 years ago" (NOT contradictory)

IMPORTANT:
- REJECT paraphrases (same meaning, different words)
- REJECT scope mismatches where qualifications differ appropriately
- REJECT "I don't recall" vs "I don't know" (both uncertain)
- REQUIRE actual logical conflict for contradiction

RESPONSE FORMAT: JSON
{
  "is_contradiction": boolean,
  "contradiction_type": "direct_negation|mutually_exclusive|quantity_conflict|memory_drift|scope_mismatch",
  "confidence": 0-100,
  "severity": 0-100,
  "explanation": "Brief explanation of why contradictory",
  "requires_human_review": boolean,
  "suggested_followups": ["impeachment question 1", "impeachment question 2"]
}

If NOT contradictory, return: {"is_contradiction": false}"""
        
        # Build user prompt with claim details
        user_prompt = f"""Analyze these two claims for contradictions:

CLAIM A (Page {claim_a['page_number']}, Line {claim_a['line_number']}):
- Subject: {claim_a['subject']}
- Predicate: {claim_a['predicate']}
- Object: {claim_a.get('object', 'N/A')}
- Polarity: {claim_a.get('polarity', 'positive')}
- Certainty: {claim_a.get('certainty', 100)}
- Modality: {claim_a.get('modality', 'certain')}
- Date: {claim_a.get('explicit_date') or claim_a.get('inferred_date', 'N/A')}
- Raw Quote: {claim_a['raw_quote'][:200]}

CLAIM B (Page {claim_b['page_number']}, Line {claim_b['line_number']}):
- Subject: {claim_b['subject']}
- Predicate: {claim_b['predicate']}
- Object: {claim_b.get('object', 'N/A')}
- Polarity: {claim_b.get('polarity', 'positive')}
- Certainty: {claim_b.get('certainty', 100)}
- Modality: {claim_b.get('modality', 'certain')}
- Date: {claim_b.get('explicit_date') or claim_b.get('inferred_date', 'N/A')}
- Raw Quote: {claim_b['raw_quote'][:200]}

Are these contradictory? Return JSON."""
        
        try:
            response = await openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            result_text = response.choices[0].message.content
            result = json.loads(result_text)
            
            if not result.get('is_contradiction', False):
                return None
            
            return {
                'contradiction_type': result.get('contradiction_type', 'other'),
                'confidence': result.get('confidence', 50),
                'severity': result.get('severity', 50),
                'explanation': result.get('explanation', 'Detected by LLM'),
                'requires_human_review': result.get('requires_human_review', False),
                'suggested_followups': result.get('suggested_followups', [])
            }
            
        except Exception as e:
            logger.error(f"LLM verification failed: {e}")
            return None
    
    async def detect_contradictions(
        self,
        document_id: UUID
    ) -> List[Dict]:
        """
        Two-stage contradiction detection: deterministic filters + LLM verification.
        
        Args:
            document_id: Document UUID
            
        Returns:
            List of detected contradictions
        """
        # Find candidates
        candidates = await self.find_contradiction_candidates(document_id)
        
        if not candidates:
            logger.info("No contradiction candidates found")
            return []
        
        logger.info(f"Analyzing {len(candidates)} candidate pairs...")
        
        contradictions = []
        
        for claim_a, claim_b in candidates:
            # Stage 1: Deterministic filter
            deterministic_result = self.deterministic_filter(claim_a, claim_b)
            
            if deterministic_result:
                # Deterministic contradiction found
                contradiction = {
                    'document_id': str(document_id),
                    'claim_a_id': claim_a['id'],
                    'claim_b_id': claim_b['id'],
                    **deterministic_result,
                    'requires_human_review': False,
                    'suggested_followups': []
                }
                contradictions.append(contradiction)
                logger.info(f"Deterministic contradiction: {deterministic_result['contradiction_type']}")
                continue
            
            # Stage 2: LLM verification (for non-obvious cases)
            llm_result = await self.llm_verification(claim_a, claim_b)
            
            if llm_result:
                contradiction = {
                    'document_id': str(document_id),
                    'claim_a_id': claim_a['id'],
                    'claim_b_id': claim_b['id'],
                    **llm_result
                }
                contradictions.append(contradiction)
                logger.info(f"LLM contradiction: {llm_result['contradiction_type']} (confidence: {llm_result['confidence']})")
        
        logger.info(f"Detected {len(contradictions)} contradictions total")
        return contradictions
    
    async def store_contradictions(
        self,
        contradictions: List[Dict]
    ) -> List[UUID]:
        """
        Store detected contradictions in database.
        
        Args:
            contradictions: List of contradiction dictionaries
            
        Returns:
            List of contradiction UUIDs
        """
        contradiction_ids = []
        
        for contradiction in contradictions:
            try:
                contradiction_id = await db_service.fetchval(
                    """
                    INSERT INTO contradictions (
                        document_id, claim_a_id, claim_b_id, contradiction_type,
                        severity, confidence, explanation, requires_human_review,
                        suggested_followups
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    RETURNING id
                    """,
                    UUID(contradiction['document_id']) if isinstance(contradiction['document_id'], str) else contradiction['document_id'],
                    UUID(contradiction['claim_a_id']) if isinstance(contradiction['claim_a_id'], str) else contradiction['claim_a_id'],
                    UUID(contradiction['claim_b_id']) if isinstance(contradiction['claim_b_id'], str) else contradiction['claim_b_id'],
                    contradiction['contradiction_type'],
                    contradiction.get('severity', 50),
                    contradiction.get('confidence', 50),
                    contradiction.get('explanation', ''),
                    contradiction.get('requires_human_review', False),
                    contradiction.get('suggested_followups', [])
                )
                contradiction_ids.append(contradiction_id)
            except Exception as e:
                logger.error(f"Failed to store contradiction: {e}")
                logger.error(f"Contradiction data: {contradiction}")
                continue
        
        logger.info(f"Stored {len(contradiction_ids)} contradictions in database")
        return contradiction_ids


# Global service instance
contradiction_service = ContradictionService()

