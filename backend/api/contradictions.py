"""API endpoints for contradictions."""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Dict, Optional
from uuid import UUID

from services.db_service import db_service
from api.auth import get_current_user

router = APIRouter()


@router.get("/api/documents/{document_id}/contradictions")
async def get_contradictions(
    document_id: UUID,
    current_user: dict = Depends(get_current_user)
) -> List[Dict]:
    """
    Get all contradictions for a document.
    
    Args:
        document_id: Document UUID
        current_user: Authenticated user
        
    Returns:
        List of contradiction dictionaries with claim details
    """
    try:
        contradictions = await db_service.fetch(
            """
            SELECT 
                c.id, c.document_id, c.claim_a_id, c.claim_b_id,
                c.contradiction_type, c.severity, c.confidence,
                c.explanation, c.requires_human_review, c.suggested_followups,
                c.created_at,
                ca.subject as claim_a_subject, ca.predicate as claim_a_predicate,
                ca.object as claim_a_object, ca.page_number as claim_a_page,
                ca.line_number as claim_a_line, ca.raw_quote as claim_a_quote,
                cb.subject as claim_b_subject, cb.predicate as claim_b_predicate,
                cb.object as claim_b_object, cb.page_number as claim_b_page,
                cb.line_number as claim_b_line, cb.raw_quote as claim_b_quote
            FROM contradictions c
            JOIN claims ca ON c.claim_a_id = ca.id
            JOIN claims cb ON c.claim_b_id = cb.id
            WHERE c.document_id = $1
            ORDER BY c.severity DESC, c.created_at
            """,
            document_id
        )
        
        return [
            {
                "id": str(contr["id"]),
                "document_id": str(contr["document_id"]),
                "contradiction_type": contr["contradiction_type"],
                "severity": contr["severity"],
                "confidence": contr["confidence"],
                "explanation": contr["explanation"],
                "requires_human_review": contr["requires_human_review"],
                "suggested_followups": contr["suggested_followups"] or [],
                "created_at": contr["created_at"].isoformat() if contr["created_at"] else None,
                "claim_a": {
                    "id": str(contr["claim_a_id"]),
                    "subject": contr["claim_a_subject"],
                    "predicate": contr["claim_a_predicate"],
                    "object": contr["claim_a_object"],
                    "page": contr["claim_a_page"],
                    "line": contr["claim_a_line"],
                    "quote": contr["claim_a_quote"]
                },
                "claim_b": {
                    "id": str(contr["claim_b_id"]),
                    "subject": contr["claim_b_subject"],
                    "predicate": contr["claim_b_predicate"],
                    "object": contr["claim_b_object"],
                    "page": contr["claim_b_page"],
                    "line": contr["claim_b_line"],
                    "quote": contr["claim_b_quote"]
                }
            }
            for contr in contradictions
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve contradictions: {str(e)}")


@router.get("/api/documents/{document_id}/contradictions/by-type/{contradiction_type}")
async def get_contradictions_by_type(
    document_id: UUID,
    contradiction_type: str,
    current_user: dict = Depends(get_current_user)
) -> List[Dict]:
    """
    Get contradictions filtered by type.
    
    Args:
        document_id: Document UUID
        contradiction_type: Type of contradiction (direct_negation, mutually_exclusive, etc.)
        current_user: Authenticated user
        
    Returns:
        List of contradiction dictionaries
    """
    try:
        contradictions = await db_service.fetch(
            """
            SELECT 
                c.id, c.document_id, c.claim_a_id, c.claim_b_id,
                c.contradiction_type, c.severity, c.confidence,
                c.explanation, c.requires_human_review, c.suggested_followups,
                c.created_at,
                ca.subject as claim_a_subject, ca.predicate as claim_a_predicate,
                ca.object as claim_a_object, ca.page_number as claim_a_page,
                ca.line_number as claim_a_line, ca.raw_quote as claim_a_quote,
                cb.subject as claim_b_subject, cb.predicate as claim_b_predicate,
                cb.object as claim_b_object, cb.page_number as claim_b_page,
                cb.line_number as claim_b_line, cb.raw_quote as claim_b_quote
            FROM contradictions c
            JOIN claims ca ON c.claim_a_id = ca.id
            JOIN claims cb ON c.claim_b_id = cb.id
            WHERE c.document_id = $1 AND c.contradiction_type = $2
            ORDER BY c.severity DESC, c.created_at
            """,
            document_id,
            contradiction_type
        )
        
        return [
            {
                "id": str(contr["id"]),
                "document_id": str(contr["document_id"]),
                "contradiction_type": contr["contradiction_type"],
                "severity": contr["severity"],
                "confidence": contr["confidence"],
                "explanation": contr["explanation"],
                "requires_human_review": contr["requires_human_review"],
                "suggested_followups": contr["suggested_followups"] or [],
                "created_at": contr["created_at"].isoformat() if contr["created_at"] else None,
                "claim_a": {
                    "id": str(contr["claim_a_id"]),
                    "subject": contr["claim_a_subject"],
                    "predicate": contr["claim_a_predicate"],
                    "object": contr["claim_a_object"],
                    "page": contr["claim_a_page"],
                    "line": contr["claim_a_line"],
                    "quote": contr["claim_a_quote"]
                },
                "claim_b": {
                    "id": str(contr["claim_b_id"]),
                    "subject": contr["claim_b_subject"],
                    "predicate": contr["claim_b_predicate"],
                    "object": contr["claim_b_object"],
                    "page": contr["claim_b_page"],
                    "line": contr["claim_b_line"],
                    "quote": contr["claim_b_quote"]
                }
            }
            for contr in contradictions
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve contradictions: {str(e)}")


@router.get("/api/documents/{document_id}/contradictions/top")
async def get_top_contradictions(
    document_id: UUID,
    limit: int = Query(default=10, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
) -> List[Dict]:
    """
    Get top N contradictions by severity.
    
    Args:
        document_id: Document UUID
        limit: Maximum number of results (default 10, max 100)
        current_user: Authenticated user
        
    Returns:
        List of contradiction dictionaries sorted by severity
    """
    try:
        contradictions = await db_service.fetch(
            """
            SELECT 
                c.id, c.document_id, c.claim_a_id, c.claim_b_id,
                c.contradiction_type, c.severity, c.confidence,
                c.explanation, c.requires_human_review, c.suggested_followups,
                c.created_at,
                ca.subject as claim_a_subject, ca.predicate as claim_a_predicate,
                ca.object as claim_a_object, ca.page_number as claim_a_page,
                ca.line_number as claim_a_line, ca.raw_quote as claim_a_quote,
                cb.subject as claim_b_subject, cb.predicate as claim_b_predicate,
                cb.object as claim_b_object, cb.page_number as claim_b_page,
                cb.line_number as claim_b_line, cb.raw_quote as claim_b_quote
            FROM contradictions c
            JOIN claims ca ON c.claim_a_id = ca.id
            JOIN claims cb ON c.claim_b_id = cb.id
            WHERE c.document_id = $1
            ORDER BY c.severity DESC, c.confidence DESC
            LIMIT $2
            """,
            document_id,
            limit
        )
        
        return [
            {
                "id": str(contr["id"]),
                "document_id": str(contr["document_id"]),
                "contradiction_type": contr["contradiction_type"],
                "severity": contr["severity"],
                "confidence": contr["confidence"],
                "explanation": contr["explanation"],
                "requires_human_review": contr["requires_human_review"],
                "suggested_followups": contr["suggested_followups"] or [],
                "created_at": contr["created_at"].isoformat() if contr["created_at"] else None,
                "claim_a": {
                    "id": str(contr["claim_a_id"]),
                    "subject": contr["claim_a_subject"],
                    "predicate": contr["claim_a_predicate"],
                    "object": contr["claim_a_object"],
                    "page": contr["claim_a_page"],
                    "line": contr["claim_a_line"],
                    "quote": contr["claim_a_quote"]
                },
                "claim_b": {
                    "id": str(contr["claim_b_id"]),
                    "subject": contr["claim_b_subject"],
                    "predicate": contr["claim_b_predicate"],
                    "object": contr["claim_b_object"],
                    "page": contr["claim_b_page"],
                    "line": contr["claim_b_line"],
                    "quote": contr["claim_b_quote"]
                }
            }
            for contr in contradictions
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve top contradictions: {str(e)}")


@router.get("/api/documents/{document_id}/contradictions/by-topic")
async def get_contradictions_by_topic(
    document_id: UUID,
    topic: Optional[str] = Query(default=None),
    current_user: dict = Depends(get_current_user)
) -> List[Dict]:
    """
    Get contradictions related to a specific topic.
    
    This joins with final_qa_items to get topic information.
    
    Args:
        document_id: Document UUID
        topic: Optional topic filter
        current_user: Authenticated user
        
    Returns:
        List of contradiction dictionaries
    """
    try:
        if topic:
            contradictions = await db_service.fetch(
                """
                SELECT DISTINCT
                    c.id, c.document_id, c.claim_a_id, c.claim_b_id,
                    c.contradiction_type, c.severity, c.confidence,
                    c.explanation, c.requires_human_review, c.suggested_followups,
                    c.created_at,
                    ca.subject as claim_a_subject, ca.predicate as claim_a_predicate,
                    ca.object as claim_a_object, ca.page_number as claim_a_page,
                    ca.line_number as claim_a_line, ca.raw_quote as claim_a_quote,
                    cb.subject as claim_b_subject, cb.predicate as claim_b_predicate,
                    cb.object as claim_b_object, cb.page_number as claim_b_page,
                    cb.line_number as claim_b_line, cb.raw_quote as claim_b_quote
                FROM contradictions c
                JOIN claims ca ON c.claim_a_id = ca.id
                JOIN claims cb ON c.claim_b_id = cb.id
                LEFT JOIN final_qa_items qa_a ON ca.qa_item_id = qa_a.id
                LEFT JOIN final_qa_items qa_b ON cb.qa_item_id = qa_b.id
                WHERE c.document_id = $1
                  AND ($2 = ANY(qa_a.topics) OR $2 = ANY(qa_b.topics))
                ORDER BY c.severity DESC, c.created_at
                """,
                document_id,
                topic
            )
        else:
            # No topic filter, return all contradictions
            contradictions = await db_service.fetch(
                """
                SELECT 
                    c.id, c.document_id, c.claim_a_id, c.claim_b_id,
                    c.contradiction_type, c.severity, c.confidence,
                    c.explanation, c.requires_human_review, c.suggested_followups,
                    c.created_at,
                    ca.subject as claim_a_subject, ca.predicate as claim_a_predicate,
                    ca.object as claim_a_object, ca.page_number as claim_a_page,
                    ca.line_number as claim_a_line, ca.raw_quote as claim_a_quote,
                    cb.subject as claim_b_subject, cb.predicate as claim_b_predicate,
                    cb.object as claim_b_object, cb.page_number as claim_b_page,
                    cb.line_number as claim_b_line, cb.raw_quote as claim_b_quote
                FROM contradictions c
                JOIN claims ca ON c.claim_a_id = ca.id
                JOIN claims cb ON c.claim_b_id = cb.id
                WHERE c.document_id = $1
                ORDER BY c.severity DESC, c.created_at
                """,
                document_id
            )
        
        return [
            {
                "id": str(contr["id"]),
                "document_id": str(contr["document_id"]),
                "contradiction_type": contr["contradiction_type"],
                "severity": contr["severity"],
                "confidence": contr["confidence"],
                "explanation": contr["explanation"],
                "requires_human_review": contr["requires_human_review"],
                "suggested_followups": contr["suggested_followups"] or [],
                "created_at": contr["created_at"].isoformat() if contr["created_at"] else None,
                "claim_a": {
                    "id": str(contr["claim_a_id"]),
                    "subject": contr["claim_a_subject"],
                    "predicate": contr["claim_a_predicate"],
                    "object": contr["claim_a_object"],
                    "page": contr["claim_a_page"],
                    "line": contr["claim_a_line"],
                    "quote": contr["claim_a_quote"]
                },
                "claim_b": {
                    "id": str(contr["claim_b_id"]),
                    "subject": contr["claim_b_subject"],
                    "predicate": contr["claim_b_predicate"],
                    "object": contr["claim_b_object"],
                    "page": contr["claim_b_page"],
                    "line": contr["claim_b_line"],
                    "quote": contr["claim_b_quote"]
                }
            }
            for contr in contradictions
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve contradictions by topic: {str(e)}")

