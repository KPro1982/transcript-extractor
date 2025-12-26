"""Service for extracting atomic claims from Q&A pairs and detecting contradictions."""
import logging
import json
from typing import List, Dict, Optional, Tuple
from uuid import UUID
from openai import AsyncOpenAI

from services.db_service import db_service
from services.people_extraction_service import people_extraction_service
from config import settings

logger = logging.getLogger(__name__)

# Initialize OpenAI client
openai_client = AsyncOpenAI(api_key=settings.openai_api_key_1 or settings.openai_api_key)


class ClaimExtractionService:
    """Service for extracting atomic claims from deposition Q&A pairs."""
    
    def __init__(self):
        self.event_clusters = {}  # Cache for event clustering
    
    async def extract_claims_from_qa(
        self,
        qa_item: Dict,
        document_id: UUID,
        witness_name: Optional[str] = None
    ) -> List[Dict]:
        """
        Extract atomic claims from a Q&A pair using LLM with structured output.
        
        Args:
            qa_item: Q&A dictionary with question, answer, page, line, etc.
            document_id: Document UUID
            witness_name: Full witness name for entity normalization
            
        Returns:
            List of claim dictionaries with all required fields
        """
        question = qa_item.get('question', '')
        answer = qa_item.get('answer', '')
        page_number = qa_item.get('page', 1)
        line_number = qa_item.get('line', 1)
        answer_end_page = qa_item.get('answer_end_page', page_number)
        answer_end_line = qa_item.get('answer_end_line', line_number)
        raw_quote = f"Q: {question}\nA: {answer}"
        
        # Build extraction prompt
        system_prompt = """You are a legal assistant extracting atomic facts from deposition testimony.

Extract ATOMIC CLAIMS as Subject-Predicate-Object triples. Each claim should represent ONE fact.

For each claim, provide:
- subject: Who/what the claim is about (person, entity, concept)
- predicate: The relationship or action (was, did, had, located at, etc.)
- object: The target of the predicate (can be null for intransitive verbs)
- time: Temporal context if mentioned
- location: Location if mentioned
- polarity: "positive" (affirmative), "negative" (negated), or "uncertain" (I don't know/recall)
- certainty: 0-100 confidence level in the claim
- modality: "certain", "maybe", "dont_recall", "believes", "thinks"
- scope: JSON with qualifications (time_range, location_range, qualification)
- explicit_date: Date explicitly stated (e.g., "January 15, 2020", "March 2021")
- inferred_date: Date inferred from context (e.g., "two weeks later", "the next day")
- date_source: "explicit", "inferred", "relative_to_anchor", or "none"
- date_anchor: Reference point for relative dates (e.g., "deposition_date", "incident_date", "previous_claim")

CRITICAL DATE EXTRACTION RULES:
- Explicit dates: Extract verbatim when witness states specific date/time
  Examples: "January 15, 2020", "on 3/15/2019", "March 2021", "in August 2020"
- Inferred dates: Extract relative dates and note anchor point
  Examples: "two weeks later" → inferred_date="two weeks later", date_anchor="incident_date"
  Examples: "the next day" → inferred_date="the next day", date_anchor="previous_claim"
- Mark date_source: "explicit" for direct statements, "inferred" for relative/contextual dates
- If no date mentioned: date_source="none", leave explicit_date and inferred_date null

NEGATION & UNCERTAINTY:
- "I was NOT alone" → polarity="negative"
- "I don't recall" → polarity="uncertain", modality="dont_recall", certainty=0
- "Maybe" / "I think" → polarity="positive", modality="maybe" or "thinks", certainty=50

SCOPE QUALIFICATIONS:
- "In the last 10 years" → scope={"time_range": "last_10_years"}
- "At that location" → scope={"location_range": "specific_location"}
- "To the best of my knowledge" → scope={"qualification": "to_best_of_knowledge"}

SPLIT MULTI-FACT ANSWERS:
- If answer contains multiple facts, extract each as separate claim
- Example: "I was at the store and bought milk" → 2 claims

RESPONSE FORMAT: JSON array of claims
[{
  "subject": "string",
  "predicate": "string",
  "object": "string or null",
  "time": "string or null",
  "location": "string or null",
  "polarity": "positive|negative|uncertain",
  "certainty": 0-100,
  "modality": "certain|maybe|dont_recall|believes|thinks",
  "scope": {},
  "explicit_date": "string or null",
  "inferred_date": "string or null",
  "date_source": "explicit|inferred|relative_to_anchor|none",
  "date_anchor": "string or null"
}]"""
        
        user_prompt = f"""Extract atomic claims from this deposition Q&A:

Q: {question}
A: {answer}

Return JSON array of claims."""
        
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
            
            # Handle both {"claims": [...]} and direct array responses
            claims_list = result.get("claims", result if isinstance(result, list) else [])
            
            if not claims_list:
                logger.warning(f"No claims extracted from Q&A at page {page_number}, line {line_number}")
                return []
            
            # Enrich claims with provenance and normalize
            enriched_claims = []
            for claim in claims_list:
                enriched_claim = {
                    "document_id": str(document_id),
                    "qa_item_id": qa_item.get('id'),
                    "subject": claim.get("subject", ""),
                    "predicate": claim.get("predicate", ""),
                    "object": claim.get("object"),
                    "time": claim.get("time"),
                    "location": claim.get("location"),
                    "polarity": claim.get("polarity", "positive"),
                    "certainty": claim.get("certainty", 100),
                    "modality": claim.get("modality", "certain"),
                    "scope": json.dumps(claim.get("scope", {})),
                    "explicit_date": claim.get("explicit_date"),
                    "inferred_date": claim.get("inferred_date"),
                    "date_source": claim.get("date_source", "none"),
                    "date_anchor": claim.get("date_anchor"),
                    "page_number": page_number,
                    "line_number": line_number,
                    "answer_end_page": answer_end_page,
                    "answer_end_line": answer_end_line,
                    "raw_quote": raw_quote,
                    "normalized_subject": None,  # Will be normalized next
                    "normalized_object": None,
                    "event_id": None  # Will be assigned during event clustering
                }
                enriched_claims.append(enriched_claim)
            
            logger.info(f"Extracted {len(enriched_claims)} claims from Q&A at page {page_number}, line {line_number}")
            return enriched_claims
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response for Q&A at page {page_number}, line {line_number}: {e}")
            return []
        except Exception as e:
            logger.error(f"Failed to extract claims from Q&A at page {page_number}, line {line_number}: {e}")
            return []
    
    async def normalize_entities(
        self,
        claims: List[Dict],
        document_id: UUID,
        witness_name: Optional[str] = None
    ) -> List[Dict]:
        """
        Normalize entities in claims for matching and coreference resolution.
        
        Args:
            claims: List of claim dictionaries
            document_id: Document UUID
            witness_name: Full witness name
            
        Returns:
            Claims with normalized_subject and normalized_object fields populated
        """
        for claim in claims:
            # Normalize subject (usually a person)
            subject = claim.get("subject", "")
            if subject:
                normalized_subject = people_extraction_service.normalize_name(subject, witness_name)
                claim["normalized_subject"] = normalized_subject
            
            # Normalize object (could be person, location, or concept)
            obj = claim.get("object", "")
            if obj and isinstance(obj, str):
                # Try person normalization first
                normalized_object = people_extraction_service.normalize_name(obj, witness_name)
                claim["normalized_object"] = normalized_object
        
        return claims
    
    async def cluster_claims_by_event(
        self,
        claims: List[Dict],
        document_id: UUID
    ) -> List[Dict]:
        """
        Cluster claims by event (incident, employment, medical, etc.) using LLM.
        
        Args:
            claims: List of claim dictionaries
            document_id: Document UUID
            
        Returns:
            Claims with event_id field populated
        """
        if not claims:
            return claims
        
        # Build prompt for event clustering
        system_prompt = """You are a legal assistant clustering claims by event.

Common event types in depositions:
- incident: The main incident/event being litigated
- employment: Job history, positions, employment events
- medical: Medical history, injuries, treatments
- training: Training, education, certifications
- complaint: Filed complaints, grievances
- harassment: Harassment incidents
- discrimination: Discrimination incidents
- background: Personal background, education
- other: Other events

For each claim, assign an event_id in format: event_type_date or event_type_description

Examples:
- "incident_2023-01-15" (main incident on specific date)
- "employment_acme_corp" (employment at Acme Corp)
- "medical_knee_injury_2019" (knee injury in 2019)
- "training_safety_2020" (safety training in 2020)

RESPONSE FORMAT: JSON object with claim indexes mapped to event_ids
{
  "0": "incident_2023-01-15",
  "1": "incident_2023-01-15",
  "2": "employment_acme_corp",
  ...
}"""
        
        # Build claim summaries for clustering
        claim_summaries = []
        for idx, claim in enumerate(claims):
            summary = f"{idx}: {claim.get('subject', '')} {claim.get('predicate', '')} {claim.get('object', '')}"
            if claim.get('explicit_date'):
                summary += f" on {claim['explicit_date']}"
            claim_summaries.append(summary)
        
        user_prompt = f"""Cluster these claims by event:

{chr(10).join(claim_summaries)}

Return JSON mapping claim indexes to event_ids."""
        
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
            
            # Assign event_ids to claims
            for idx_str, event_id in result.items():
                idx = int(idx_str)
                if 0 <= idx < len(claims):
                    claims[idx]["event_id"] = event_id
            
            logger.info(f"Clustered {len(claims)} claims into events")
            return claims
            
        except Exception as e:
            logger.error(f"Failed to cluster claims by event: {e}")
            # Fallback: assign generic event_id
            for claim in claims:
                claim["event_id"] = "unclustered"
            return claims
    
    async def store_claims(
        self,
        claims: List[Dict]
    ) -> List[UUID]:
        """
        Store claims in database.
        
        Args:
            claims: List of claim dictionaries
            
        Returns:
            List of claim UUIDs
        """
        claim_ids = []
        
        for claim in claims:
            try:
                claim_id = await db_service.fetchval(
                    """
                    INSERT INTO claims (
                        document_id, qa_item_id, subject, predicate, object,
                        time, location, polarity, certainty, modality, scope,
                        explicit_date, inferred_date, date_source, date_anchor,
                        page_number, line_number, answer_end_page, answer_end_line,
                        raw_quote, normalized_subject, normalized_object, event_id
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23)
                    RETURNING id
                    """,
                    UUID(claim["document_id"]) if isinstance(claim["document_id"], str) else claim["document_id"],
                    UUID(claim["qa_item_id"]) if claim.get("qa_item_id") and isinstance(claim["qa_item_id"], str) else claim.get("qa_item_id"),
                    claim["subject"],
                    claim["predicate"],
                    claim.get("object"),
                    claim.get("time"),
                    claim.get("location"),
                    claim.get("polarity", "positive"),
                    claim.get("certainty", 100),
                    claim.get("modality", "certain"),
                    claim.get("scope", "{}"),
                    claim.get("explicit_date"),
                    claim.get("inferred_date"),
                    claim.get("date_source", "none"),
                    claim.get("date_anchor"),
                    claim["page_number"],
                    claim["line_number"],
                    claim.get("answer_end_page"),
                    claim.get("answer_end_line"),
                    claim["raw_quote"],
                    claim.get("normalized_subject"),
                    claim.get("normalized_object"),
                    claim.get("event_id")
                )
                claim_ids.append(claim_id)
            except Exception as e:
                logger.error(f"Failed to store claim: {e}")
                logger.error(f"Claim data: {claim}")
                continue
        
        logger.info(f"Stored {len(claim_ids)} claims in database")
        return claim_ids
    
    async def extract_and_store_claims(
        self,
        qa_items: List[Dict],
        document_id: UUID,
        witness_name: Optional[str] = None
    ) -> List[UUID]:
        """
        Extract claims from multiple Q&A items and store them.
        
        Args:
            qa_items: List of Q&A dictionaries
            document_id: Document UUID
            witness_name: Full witness name
            
        Returns:
            List of all claim UUIDs
        """
        all_claims = []
        
        # Extract claims from each Q&A
        for qa_item in qa_items:
            claims = await self.extract_claims_from_qa(qa_item, document_id, witness_name)
            all_claims.extend(claims)
        
        if not all_claims:
            logger.warning(f"No claims extracted from {len(qa_items)} Q&A items")
            return []
        
        # Normalize entities
        all_claims = await self.normalize_entities(all_claims, document_id, witness_name)
        
        # Cluster by event
        all_claims = await self.cluster_claims_by_event(all_claims, document_id)
        
        # Store in database
        claim_ids = await self.store_claims(all_claims)
        
        return claim_ids


# Global service instance
claim_extraction_service = ClaimExtractionService()

