"""Pydantic models for chat-with-depo feature."""
from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class Citation(BaseModel):
    """Citation reference to a Q&A item."""
    qa_item_id: UUID
    page: int
    line: int
    text_snippet: str = Field(..., max_length=500)


class ChatSessionCreate(BaseModel):
    """Request to create a new chat session."""
    document_id: UUID


class ChatSessionResponse(BaseModel):
    """Response with chat session details."""
    session_id: UUID
    document_id: UUID
    title: str
    created_at: datetime
    updated_at: datetime


class ChatSessionListItem(BaseModel):
    """Brief chat session info for list view."""
    session_id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int


class ChatSessionUpdate(BaseModel):
    """Request to update chat session metadata."""
    title: Optional[str] = None


class ChatMessageRequest(BaseModel):
    """Request to send a chat message."""
    message: str = Field(..., min_length=1, max_length=5000)
    stream: bool = False


class ChatMessageResponse(BaseModel):
    """Response with assistant message."""
    message_id: UUID
    role: str = "assistant"
    content: str
    citations: List[Citation] = []
    created_at: datetime


class ChatMessage(BaseModel):
    """Chat message with full details."""
    id: UUID
    role: str  # 'user' or 'assistant'
    content: str
    citations: Optional[List[Citation]] = None
    created_at: datetime


class ChatSessionWithMessages(BaseModel):
    """Full chat session with message history."""
    session_id: UUID
    document_id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    messages: List[ChatMessage] = []


class ChatSessionsListResponse(BaseModel):
    """Response with list of chat sessions."""
    sessions: List[ChatSessionListItem] = []

