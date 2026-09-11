import uuid
from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, Field


class QuestionCreate(BaseModel):
    subject_id: uuid.UUID
    text: str = Field(..., min_length=5)
    marks_weight: int = Field(5, ge=1, le=20)
    unit_tag: Optional[str] = Field(None, max_length=50)
    is_pyq: bool = True
    occurrences: int = 1


class QuestionOut(BaseModel):
    id: uuid.UUID
    subject_id: uuid.UUID
    text: str
    marks_weight: int
    unit_tag: Optional[str]
    is_pyq: bool
    occurrences: int

    class Config:
        from_attributes = True


class PYQAnalyticsOut(BaseModel):
    total_pyqs: int
    unit_distribution: Dict[str, int]
    marks_distribution: Dict[str, int]
    top_repeated: List[QuestionOut]
