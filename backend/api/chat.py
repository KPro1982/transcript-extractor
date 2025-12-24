"""Chat API endpoints for chat-with-depo feature."""
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import JSONResponse

from api.auth import get_current_user
from services.db_service import persistent_db_service, db_service
from services.chat_service import chat_service
from models.chat_models import (
    ChatSessionCreate,
    ChatSessionResponse,
    ChatSessionListItem,
    ChatSessionsListResponse,
    ChatSessionUpdate,
    ChatMessageRequest,
    ChatMessageResponse,
    ChatSessionWithMessages,
    ChatMessage,
    Citation
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


@router.post("/sessions", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_chat_session(
    request: ChatSessionCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new chat session for a document.
    
    Args:
        request: ChatSessionCreate with document_id
        current_user: Authenticated user from JWT
        
    Returns:
        ChatSessionResponse with session details
    """
    try:
        user_id = UUID(current_user["user_id"])
        
        # Verify document exists in ephemeral DB
        doc = await db_service.fetchrow(
            "SELECT id FROM documents WHERE id = $1",
            request.document_id
        )
        
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        # Create chat session
        session = await persistent_db_service.fetchrow(
            """
            INSERT INTO chat_sessions (user_id, document_id, title)
            VALUES ($1, $2, $3)
            RETURNING id, user_id, document_id, title, created_at, updated_at
            """,
            user_id,
            request.document_id,
            "New Chat"
        )
        
        logger.info(f"Created chat session {session['id']} for user {user_id}")
        
        return ChatSessionResponse(
            session_id=session["id"],
            document_id=session["document_id"],
            title=session["title"],
            created_at=session["created_at"],
            updated_at=session["updated_at"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create chat session: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/sessions", response_model=ChatSessionsListResponse)
async def list_chat_sessions(
    document_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """
    Get all chat sessions for a document (for current user).
    
    Args:
        document_id: UUID of document
        current_user: Authenticated user from JWT
        
    Returns:
        ChatSessionsListResponse with list of sessions
    """
    try:
        user_id = UUID(current_user["user_id"])
        
        # Get sessions with message counts
        rows = await persistent_db_service.fetch(
            """
            SELECT 
                cs.id as session_id,
                cs.title,
                cs.created_at,
                cs.updated_at,
                COUNT(dcm.id) as message_count
            FROM chat_sessions cs
            LEFT JOIN depo_chat_messages dcm ON cs.id = dcm.session_id
            WHERE cs.user_id = $1 AND cs.document_id = $2
            GROUP BY cs.id, cs.title, cs.created_at, cs.updated_at
            ORDER BY cs.updated_at DESC
            LIMIT 20
            """,
            user_id,
            document_id
        )
        
        sessions = [
            ChatSessionListItem(
                session_id=row["session_id"],
                title=row["title"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                message_count=row["message_count"]
            )
            for row in rows
        ]
        
        return ChatSessionsListResponse(sessions=sessions)
        
    except Exception as e:
        logger.error(f"Failed to list chat sessions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/sessions/{session_id}", response_model=ChatSessionWithMessages)
async def get_chat_session(
    session_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """
    Get a specific chat session with all messages.
    
    Args:
        session_id: UUID of the session
        current_user: Authenticated user from JWT
        
    Returns:
        ChatSessionWithMessages with full message history
    """
    try:
        user_id = UUID(current_user["user_id"])
        
        # Get session
        session = await persistent_db_service.fetchrow(
            """
            SELECT id, user_id, document_id, title, created_at, updated_at
            FROM chat_sessions
            WHERE id = $1 AND user_id = $2
            """,
            session_id,
            user_id
        )
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat session not found or access denied"
            )
        
        # Get messages
        msg_rows = await persistent_db_service.fetch(
            """
            SELECT id, role, content, citations, created_at
            FROM depo_chat_messages
            WHERE session_id = $1
            ORDER BY created_at ASC
            """,
            session_id
        )
        
        messages = []
        for row in msg_rows:
            citations = None
            if row["citations"]:
                import json
                citation_data = json.loads(row["citations"]) if isinstance(row["citations"], str) else row["citations"]
                citations = [Citation(**c) for c in citation_data]
            
            messages.append(
                ChatMessage(
                    id=row["id"],
                    role=row["role"],
                    content=row["content"],
                    citations=citations,
                    created_at=row["created_at"]
                )
            )
        
        return ChatSessionWithMessages(
            session_id=session["id"],
            document_id=session["document_id"],
            title=session["title"],
            created_at=session["created_at"],
            updated_at=session["updated_at"],
            messages=messages
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get chat session: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.patch("/sessions/{session_id}", response_model=ChatSessionResponse)
async def update_chat_session(
    session_id: UUID,
    update: ChatSessionUpdate,
    current_user: dict = Depends(get_current_user)
):
    """
    Update chat session metadata (title).
    
    Args:
        session_id: UUID of the session
        update: ChatSessionUpdate with fields to update
        current_user: Authenticated user from JWT
        
    Returns:
        Updated ChatSessionResponse
    """
    try:
        user_id = UUID(current_user["user_id"])
        
        # Verify ownership
        session = await persistent_db_service.fetchrow(
            """
            SELECT id, user_id, document_id
            FROM chat_sessions
            WHERE id = $1 AND user_id = $2
            """,
            session_id,
            user_id
        )
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat session not found or access denied"
            )
        
        # Update title if provided
        if update.title is not None:
            await persistent_db_service.execute(
                """
                UPDATE chat_sessions
                SET title = $1, updated_at = NOW()
                WHERE id = $2
                """,
                update.title,
                session_id
            )
        
        # Fetch updated session
        updated_session = await persistent_db_service.fetchrow(
            """
            SELECT id, user_id, document_id, title, created_at, updated_at
            FROM chat_sessions
            WHERE id = $1
            """,
            session_id
        )
        
        return ChatSessionResponse(
            session_id=updated_session["id"],
            document_id=updated_session["document_id"],
            title=updated_session["title"],
            created_at=updated_session["created_at"],
            updated_at=updated_session["updated_at"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update chat session: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat_session(
    session_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """
    Delete a chat session and all its messages.
    
    Args:
        session_id: UUID of the session
        current_user: Authenticated user from JWT
    """
    try:
        user_id = UUID(current_user["user_id"])
        
        # Delete session (messages will cascade)
        result = await persistent_db_service.execute(
            """
            DELETE FROM chat_sessions
            WHERE id = $1 AND user_id = $2
            """,
            session_id,
            user_id
        )
        
        if result == "DELETE 0":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat session not found or access denied"
            )
        
        logger.info(f"Deleted chat session {session_id}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete chat session: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/sessions/{session_id}/messages", response_model=ChatMessageResponse)
async def send_chat_message(
    session_id: UUID,
    request: ChatMessageRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Send a message and get AI response.
    
    Args:
        session_id: UUID of the session
        request: ChatMessageRequest with user message
        current_user: Authenticated user from JWT
        
    Returns:
        ChatMessageResponse with AI response and citations
    """
    try:
        user_id = UUID(current_user["user_id"])
        
        # Verify session ownership
        session = await persistent_db_service.fetchrow(
            """
            SELECT id, user_id, document_id
            FROM chat_sessions
            WHERE id = $1 AND user_id = $2
            """,
            session_id,
            user_id
        )
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat session not found or access denied"
            )
        
        # Generate AI response
        response = await chat_service.generate_response(
            session_id,
            request.message,
            stream=request.stream
        )
        
        # Convert citations to Citation models
        citations = [Citation(**c) for c in response["citations"]]
        
        return ChatMessageResponse(
            message_id=response["message_id"],
            role=response["role"],
            content=response["content"],
            citations=citations,
            created_at=response["created_at"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to send chat message: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessage])
async def get_chat_messages(
    session_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """
    Get all messages for a session.
    
    Args:
        session_id: UUID of the session
        current_user: Authenticated user from JWT
        
    Returns:
        List of ChatMessage objects
    """
    try:
        user_id = UUID(current_user["user_id"])
        
        # Verify session ownership
        session = await persistent_db_service.fetchrow(
            """
            SELECT id FROM chat_sessions
            WHERE id = $1 AND user_id = $2
            """,
            session_id,
            user_id
        )
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat session not found or access denied"
            )
        
        # Get messages
        rows = await persistent_db_service.fetch(
            """
            SELECT id, role, content, citations, created_at
            FROM depo_chat_messages
            WHERE session_id = $1
            ORDER BY created_at ASC
            """,
            session_id
        )
        
        messages = []
        for row in rows:
            citations = None
            if row["citations"]:
                import json
                citation_data = json.loads(row["citations"]) if isinstance(row["citations"], str) else row["citations"]
                citations = [Citation(**c) for c in citation_data]
            
            messages.append(
                ChatMessage(
                    id=row["id"],
                    role=row["role"],
                    content=row["content"],
                    citations=citations,
                    created_at=row["created_at"]
                )
            )
        
        return messages
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get chat messages: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

