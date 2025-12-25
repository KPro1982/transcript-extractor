"""Learning feedback API endpoints."""
import logging
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from uuid import UUID

from api.auth import get_current_user, require_admin, User
from services.db_service import persistent_db_service

logger = logging.getLogger(__name__)

router = APIRouter()


class LearningFeedbackCreate(BaseModel):
    """Learning feedback creation model."""
    question: str
    answer: str
    ai_summary: str
    user_summary: str
    notes: Optional[str] = None
    document_filename: Optional[str] = None
    page_citation: Optional[str] = None


class LearningFeedback(BaseModel):
    """Learning feedback model."""
    id: str
    user_id: str
    user_name: str
    user_email: str
    question: str
    answer: str
    ai_summary: str
    user_summary: str
    notes: Optional[str]
    document_filename: Optional[str]
    page_citation: Optional[str]
    status: str
    reviewed_by: Optional[str]
    reviewed_at: Optional[datetime]
    created_at: datetime


@router.post("/learning-feedback", response_model=LearningFeedback)
async def create_learning_feedback(
    feedback: LearningFeedbackCreate,
    user: User = Depends(get_current_user)
):
    """Submit learning feedback for AI summary improvement."""
    try:
        result = await persistent_db_service.fetchrow(
            """
            INSERT INTO learning_feedback (
                user_id, question, answer, ai_summary, user_summary, notes,
                document_filename, page_citation, status
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'pending')
            RETURNING id, user_id, question, answer, ai_summary, user_summary, notes,
                      document_filename, page_citation, status, reviewed_by, reviewed_at, created_at
            """,
            user.id, feedback.question, feedback.answer, feedback.ai_summary,
            feedback.user_summary, feedback.notes, feedback.document_filename,
            feedback.page_citation
        )
        
        logger.info(f"Learning feedback submitted: {result['id']} by {user.email}")
        
        return LearningFeedback(
            id=str(result['id']),
            user_id=str(result['user_id']),
            user_name=user.name or user.email,
            user_email=user.email,
            question=result['question'],
            answer=result['answer'],
            ai_summary=result['ai_summary'],
            user_summary=result['user_summary'],
            notes=result['notes'],
            document_filename=result['document_filename'],
            page_citation=result['page_citation'],
            status=result['status'],
            reviewed_by=None,
            reviewed_at=None,
            created_at=result['created_at']
        )
    
    except Exception as e:
        logger.error(f"Failed to create learning feedback: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to submit feedback")


@router.get("/learning-feedback", response_model=List[LearningFeedback])
async def list_learning_feedback(
    status: Optional[str] = None,
    user: User = Depends(get_current_user)
):
    """List learning feedback. Admin sees all, users see only their own."""
    try:
        if user.is_admin:
            # Admin sees all feedback
            query = """
                SELECT 
                    lf.id, lf.user_id, lf.question, lf.answer, lf.ai_summary, lf.user_summary,
                    lf.notes, lf.document_filename, lf.page_citation, lf.status,
                    lf.reviewed_by, lf.reviewed_at, lf.created_at,
                    u.name as user_name, u.email as user_email
                FROM learning_feedback lf
                JOIN users u ON lf.user_id = u.id
            """
            params = []
            if status:
                query += " WHERE lf.status = $1"
                params.append(status)
            query += " ORDER BY lf.created_at DESC"
            
            feedback_list = await persistent_db_service.fetch(query, *params)
        else:
            # Users see only their feedback
            query = """
                SELECT 
                    lf.id, lf.user_id, lf.question, lf.answer, lf.ai_summary, lf.user_summary,
                    lf.notes, lf.document_filename, lf.page_citation, lf.status,
                    lf.reviewed_by, lf.reviewed_at, lf.created_at,
                    u.name as user_name, u.email as user_email
                FROM learning_feedback lf
                JOIN users u ON lf.user_id = u.id
                WHERE lf.user_id = $1
            """
            params = [user.id]
            if status:
                query += " AND lf.status = $2"
                params.append(status)
            query += " ORDER BY lf.created_at DESC"
            
            feedback_list = await persistent_db_service.fetch(query, *params)
        
        return [
            LearningFeedback(
                id=str(f['id']),
                user_id=str(f['user_id']),
                user_name=f['user_name'] or f['user_email'],
                user_email=f['user_email'],
                question=f['question'],
                answer=f['answer'],
                ai_summary=f['ai_summary'],
                user_summary=f['user_summary'],
                notes=f['notes'],
                document_filename=f['document_filename'],
                page_citation=f['page_citation'],
                status=f['status'],
                reviewed_by=str(f['reviewed_by']) if f['reviewed_by'] else None,
                reviewed_at=f['reviewed_at'],
                created_at=f['created_at']
            )
            for f in feedback_list
        ]
    
    except Exception as e:
        logger.error(f"Failed to list learning feedback: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list feedback")


@router.get("/learning-feedback/{feedback_id}", response_model=LearningFeedback)
async def get_learning_feedback(
    feedback_id: str,
    user: User = Depends(get_current_user)
):
    """Get specific learning feedback."""
    try:
        feedback = await persistent_db_service.fetchrow(
            """
            SELECT 
                lf.*, u.name as user_name, u.email as user_email
            FROM learning_feedback lf
            JOIN users u ON lf.user_id = u.id
            WHERE lf.id = $1
            """,
            feedback_id
        )
        
        if not feedback:
            raise HTTPException(status_code=404, detail="Feedback not found")
        
        # Check access permissions
        if not user.is_admin and str(feedback['user_id']) != user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        return LearningFeedback(
            id=str(feedback['id']),
            user_id=str(feedback['user_id']),
            user_name=feedback['user_name'] or feedback['user_email'],
            user_email=feedback['user_email'],
            question=feedback['question'],
            answer=feedback['answer'],
            ai_summary=feedback['ai_summary'],
            user_summary=feedback['user_summary'],
            notes=feedback['notes'],
            document_filename=feedback['document_filename'],
            page_citation=feedback['page_citation'],
            status=feedback['status'],
            reviewed_by=str(feedback['reviewed_by']) if feedback['reviewed_by'] else None,
            reviewed_at=feedback['reviewed_at'],
            created_at=feedback['created_at']
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get learning feedback: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get feedback")


@router.patch("/learning-feedback/{feedback_id}/status")
async def update_feedback_status(
    feedback_id: str,
    status: str,
    admin: User = Depends(require_admin)
):
    """Update learning feedback status (admin only)."""
    try:
        await persistent_db_service.execute(
            """
            UPDATE learning_feedback 
            SET status = $2, reviewed_by = $3, reviewed_at = NOW()
            WHERE id = $1
            """,
            feedback_id, status, admin.id
        )
        
        logger.info(f"Learning feedback {feedback_id} updated to {status} by {admin.email}")
        return {"message": "Status updated successfully"}
    
    except Exception as e:
        logger.error(f"Failed to update feedback status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update status")






