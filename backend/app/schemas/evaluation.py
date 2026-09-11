import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class EvaluationCreate(BaseModel):
    question_id: uuid.UUID
    user_submitted_answer: str = Field(..., min_length=10)


class EvaluationOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    question_id: uuid.UUID
    user_submitted_answer: str
    feedback: str
    estimated_marks: float
    max_marks: float
    improvement_points: Dict[str, Any]
    evaluated_at: datetime

    class Config:
        from_attributes = True
