"""Document data models."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
from uuid import UUID


class DocumentBase(BaseModel):
    """Base document model."""
    filename: str
    total_pages: int


class DocumentCreate(DocumentBase):
    """Document creation model."""
    file_hash: str
    s3_key: str


class Document(DocumentBase):
    """Complete document model."""
    id: UUID
    file_hash: str
    s3_key: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class DocumentResponse(BaseModel):
    """Document API response."""
    document_id: str
    filename: str
    total_pages: int
    file_hash: str
    case_name: Optional[str] = None
    case_number: Optional[str] = None
    deposition_date: Optional[str] = None
    attorneys: Optional[List[str]] = None
    witness_name: Optional[str] = None
    created_at: Optional[str] = None












