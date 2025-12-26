"""API endpoints for claims."""
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict
from uuid import UUID

from services.db_service import db_service
from api.auth import get_current_user

router = APIRouter()


@router.get("/api/documents/{document_id}/claims")
async def get_claims(
    document_id: UUID,
    current_user: dict = Depends(get_current_user)
) -> List[Dict]:
    """
    Get all claims for a document.
    
    Args:
        document_id: Document UUID
        current_user: Authenticated user
        
    Returns:
        List of claim dictionaries
    """
    try:
        claims = await db_service.fetch(
            """
            SELECT 
                id, document_id, qa_item_id, subject, predicate, object,
                time, location, polarity, certainty, modality, scope,
                explicit_date, inferred_date, date_source, date_anchor,
                page_number, line_number, answer_end_page, answer_end_line,
                raw_quote, normalized_subject, normalized_object, event_id,
                created_at
            FROM claims
            WHERE document_id = $1
            ORDER BY page_number, line_number
            """,
            document_id
        )
        
        return [
            {
                "id": str(claim["id"]),
                "document_id": str(claim["document_id"]),
                "qa_item_id": str(claim["qa_item_id"]) if claim["qa_item_id"] else None,
                "subject": claim["subject"],
                "predicate": claim["predicate"],
                "object": claim["object"],
                "time": claim["time"],
                "location": claim["location"],
                "polarity": claim["polarity"],
                "certainty": claim["certainty"],
                "modality": claim["modality"],
                "scope": claim["scope"],
                "explicit_date": claim["explicit_date"],
                "inferred_date": claim["inferred_date"],
                "date_source": claim["date_source"],
                "date_anchor": claim["date_anchor"],
                "page_number": claim["page_number"],
                "line_number": claim["line_number"],
                "answer_end_page": claim["answer_end_page"],
                "answer_end_line": claim["answer_end_line"],
                "raw_quote": claim["raw_quote"],
                "normalized_subject": claim["normalized_subject"],
                "normalized_object": claim["normalized_object"],
                "event_id": claim["event_id"],
                "created_at": claim["created_at"].isoformat() if claim["created_at"] else None
            }
            for claim in claims
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve claims: {str(e)}")


@router.get("/api/documents/{document_id}/claims/{claim_id}")
async def get_claim(
    document_id: UUID,
    claim_id: UUID,
    current_user: dict = Depends(get_current_user)
) -> Dict:
    """
    Get a single claim by ID.
    
    Args:
        document_id: Document UUID
        claim_id: Claim UUID
        current_user: Authenticated user
        
    Returns:
        Claim dictionary
    """
    try:
        claim = await db_service.fetchrow(
            """
            SELECT 
                id, document_id, qa_item_id, subject, predicate, object,
                time, location, polarity, certainty, modality, scope,
                explicit_date, inferred_date, date_source, date_anchor,
                page_number, line_number, answer_end_page, answer_end_line,
                raw_quote, normalized_subject, normalized_object, event_id,
                created_at
            FROM claims
            WHERE document_id = $1 AND id = $2
            """,
            document_id,
            claim_id
        )
        
        if not claim:
            raise HTTPException(status_code=404, detail="Claim not found")
        
        return {
            "id": str(claim["id"]),
            "document_id": str(claim["document_id"]),
            "qa_item_id": str(claim["qa_item_id"]) if claim["qa_item_id"] else None,
            "subject": claim["subject"],
            "predicate": claim["predicate"],
            "object": claim["object"],
            "time": claim["time"],
            "location": claim["location"],
            "polarity": claim["polarity"],
            "certainty": claim["certainty"],
            "modality": claim["modality"],
            "scope": claim["scope"],
            "explicit_date": claim["explicit_date"],
            "inferred_date": claim["inferred_date"],
            "date_source": claim["date_source"],
            "date_anchor": claim["date_anchor"],
            "page_number": claim["page_number"],
            "line_number": claim["line_number"],
            "answer_end_page": claim["answer_end_page"],
            "answer_end_line": claim["answer_end_line"],
            "raw_quote": claim["raw_quote"],
            "normalized_subject": claim["normalized_subject"],
            "normalized_object": claim["normalized_object"],
            "event_id": claim["event_id"],
            "created_at": claim["created_at"].isoformat() if claim["created_at"] else None
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve claim: {str(e)}")


@router.get("/api/documents/{document_id}/claims/by-event/{event_id}")
async def get_claims_by_event(
    document_id: UUID,
    event_id: str,
    current_user: dict = Depends(get_current_user)
) -> List[Dict]:
    """
    Get all claims for a specific event.
    
    Args:
        document_id: Document UUID
        event_id: Event identifier
        current_user: Authenticated user
        
    Returns:
        List of claim dictionaries
    """
    try:
        claims = await db_service.fetch(
            """
            SELECT 
                id, document_id, qa_item_id, subject, predicate, object,
                time, location, polarity, certainty, modality, scope,
                explicit_date, inferred_date, date_source, date_anchor,
                page_number, line_number, answer_end_page, answer_end_line,
                raw_quote, normalized_subject, normalized_object, event_id,
                created_at
            FROM claims
            WHERE document_id = $1 AND event_id = $2
            ORDER BY page_number, line_number
            """,
            document_id,
            event_id
        )
        
        return [
            {
                "id": str(claim["id"]),
                "document_id": str(claim["document_id"]),
                "qa_item_id": str(claim["qa_item_id"]) if claim["qa_item_id"] else None,
                "subject": claim["subject"],
                "predicate": claim["predicate"],
                "object": claim["object"],
                "time": claim["time"],
                "location": claim["location"],
                "polarity": claim["polarity"],
                "certainty": claim["certainty"],
                "modality": claim["modality"],
                "scope": claim["scope"],
                "explicit_date": claim["explicit_date"],
                "inferred_date": claim["inferred_date"],
                "date_source": claim["date_source"],
                "date_anchor": claim["date_anchor"],
                "page_number": claim["page_number"],
                "line_number": claim["line_number"],
                "answer_end_page": claim["answer_end_page"],
                "answer_end_line": claim["answer_end_line"],
                "raw_quote": claim["raw_quote"],
                "normalized_subject": claim["normalized_subject"],
                "normalized_object": claim["normalized_object"],
                "event_id": claim["event_id"],
                "created_at": claim["created_at"].isoformat() if claim["created_at"] else None
            }
            for claim in claims
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve claims: {str(e)}")

