"""Reports API endpoints for people, chronological, page/line, and topic reports."""
import logging
from typing import List, Dict
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status

from api.auth import get_current_user, User
from services.db_service import db_service
from services.people_extraction_service import people_extraction_service

router = APIRouter(prefix="/api/documents", tags=["reports"])
logger = logging.getLogger(__name__)


@router.get("/{document_id}/reports/people")
async def get_people_report(
    document_id: UUID,
    current_user: User = Depends(get_current_user)
):
    """
    Get people report: all summaries mentioning each person.
    
    Returns a list of people with their associated Q&A items.
    """
    try:
        # Get all people mentioned in document
        people = await people_extraction_service.get_people_for_document(document_id)
        
        if not people:
            return {"people": []}
        
        # For each person, get their Q&A items
        result = []
        for person in people:
            person_id = UUID(person["id"])
            qa_items = await people_extraction_service.get_qa_items_for_person(
                document_id,
                person_id
            )
            
            result.append({
                "person": person,
                "qa_items": qa_items,
                "count": len(qa_items)
            })
        
        # Sort by count (most mentions first)
        result.sort(key=lambda x: x["count"], reverse=True)
        
        return {"people": result}
        
    except Exception as e:
        logger.error(f"Failed to get people report for document {document_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate people report: {str(e)}"
        )


@router.get("/{document_id}/reports/chronological")
async def get_chronological_report(
    document_id: UUID,
    current_user: User = Depends(get_current_user)
):
    """
    Get chronological report: summaries with event dates, sorted chronologically.
    
    Returns Q&A items that have event dates, ordered by date.
    """
    try:
        rows = await db_service.fetch(
            """
            SELECT 
                id,
                page_number,
                line_number,
                question,
                answer,
                summary,
                topic,
                event_date
            FROM final_qa_items
            WHERE document_id = $1 AND event_date IS NOT NULL AND event_date != ''
            ORDER BY event_date, page_number, line_number
            """,
            document_id
        )
        
        items = [
            {
                "id": str(row["id"]),
                "page": row["page_number"],
                "line": row["line_number"],
                "question": row["question"],
                "answer": row["answer"],
                "summary": row["summary"],
                "topic": row["topic"],
                "event_date": row["event_date"]
            }
            for row in rows
        ]
        
        return {"items": items, "total": len(items)}
        
    except Exception as e:
        logger.error(f"Failed to get chronological report for document {document_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate chronological report: {str(e)}"
        )


@router.get("/{document_id}/reports/page-line")
async def get_page_line_report(
    document_id: UUID,
    current_user: User = Depends(get_current_user)
):
    """
    Get page/line report: three-column format (page/line, summary, topic).
    
    Returns all Q&A items ordered by page and line number.
    """
    try:
        rows = await db_service.fetch(
            """
            SELECT 
                id,
                page_number,
                line_number,
                answer_end_page,
                answer_end_line,
                question,
                answer,
                summary,
                topic,
                event_date
            FROM final_qa_items
            WHERE document_id = $1
            ORDER BY page_number, line_number
            """,
            document_id
        )
        
        items = [
            {
                "id": str(row["id"]),
                "page": row["page_number"],
                "line": row["line_number"],
                "answer_end_page": row["answer_end_page"],
                "answer_end_line": row["answer_end_line"],
                "page_line_ref": format_page_line_reference(
                    row["page_number"],
                    row["line_number"],
                    row["answer_end_page"],
                    row["answer_end_line"]
                ),
                "question": row["question"],
                "answer": row["answer"],
                "summary": row["summary"],
                "topic": row["topic"],
                "event_date": row["event_date"]
            }
            for row in rows
        ]
        
        return {"items": items, "total": len(items)}
        
    except Exception as e:
        logger.error(f"Failed to get page/line report for document {document_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate page/line report: {str(e)}"
        )


@router.get("/{document_id}/reports/topics")
async def get_topics_report(
    document_id: UUID,
    current_user: User = Depends(get_current_user)
):
    """
    Get topics report: Q&A items grouped by topic.
    
    Returns topics with their associated Q&A items and counts.
    """
    try:
        # Get all Q&A items grouped by topic
        rows = await db_service.fetch(
            """
            SELECT 
                topic,
                COUNT(*) as count
            FROM final_qa_items
            WHERE document_id = $1
            GROUP BY topic
            ORDER BY count DESC, topic
            """,
            document_id
        )
        
        topics_list = []
        for row in rows:
            topic = row["topic"]
            count = row["count"]
            
            # Get Q&A items for this topic
            qa_rows = await db_service.fetch(
                """
                SELECT 
                    id,
                    page_number,
                    line_number,
                    answer_end_page,
                    answer_end_line,
                    question,
                    answer,
                    summary,
                    event_date
                FROM final_qa_items
                WHERE document_id = $1 AND topic = $2
                ORDER BY page_number, line_number
                """,
                document_id,
                topic
            )
            
            qa_items = [
                {
                    "id": str(qa_row["id"]),
                    "page": qa_row["page_number"],
                    "line": qa_row["line_number"],
                    "answer_end_page": qa_row["answer_end_page"],
                    "answer_end_line": qa_row["answer_end_line"],
                    "page_line_ref": format_page_line_reference(
                        qa_row["page_number"],
                        qa_row["line_number"],
                        qa_row["answer_end_page"],
                        qa_row["answer_end_line"]
                    ),
                    "question": qa_row["question"],
                    "answer": qa_row["answer"],
                    "summary": qa_row["summary"],
                    "event_date": qa_row["event_date"]
                }
                for qa_row in qa_rows
            ]
            
            topics_list.append({
                "topic": topic,
                "count": count,
                "qa_items": qa_items
            })
        
        return {"topics": topics_list, "total": len(topics_list)}
        
    except Exception as e:
        logger.error(f"Failed to get topics report for document {document_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate topics report: {str(e)}"
        )


def format_page_line_reference(
    page: int,
    line: int,
    answer_end_page: int = None,
    answer_end_line: int = None
) -> str:
    """
    Format page/line reference for display.
    
    Examples:
    - "Page 45, Line 12"
    - "Page 45, Lines 12-18"
    - "Page 45, Line 12 - Page 46, Line 5"
    """
    if answer_end_page and answer_end_page != page:
        return f"Page {page}, Line {line} - Page {answer_end_page}, Line {answer_end_line}"
    elif answer_end_line and answer_end_line != line:
        return f"Page {page}, Lines {line}-{answer_end_line}"
    else:
        return f"Page {page}, Line {line}"

