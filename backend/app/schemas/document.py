import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class DocumentBase(BaseModel):
    name: str = Field(..., max_length=255)
    category: str = Field(..., description="Category: notes, pyq, book, lab")


class DocumentCreate(DocumentBase):
    subject_id: uuid.UUID
    storage_path: str = Field(..., max_length=500)
    file_type: str = Field(..., max_length=20)
    uploaded_by: Optional[uuid.UUID] = None


class DocumentUpdate(BaseModel):
    processing_status: Optional[str] = Field(None, description="pending, processing, completed, failed")
    name: Optional[str] = None
    category: Optional[str] = None


class DocumentOut(DocumentBase):
    id: uuid.UUID
    subject_id: uuid.UUID
    storage_path: str
    file_type: str
    processing_status: str
    uploaded_by: Optional[uuid.UUID]
    uploaded_at: datetime

    class Config:
        from_attributes = True
