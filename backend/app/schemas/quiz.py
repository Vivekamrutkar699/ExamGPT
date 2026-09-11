import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class QuizCreate(BaseModel):
    subject_id: uuid.UUID
    title: str = Field(..., min_length=1, max_length=255)
    quiz_type: str = Field("MCQ", pattern="^(MCQ|Short|Long)$")
    unit_tag: Optional[str] = Field(None, max_length=100)


class QuizSubmission(BaseModel):
    answers: Dict[str, str]  # maps question_id to selected option (e.g. "A") or answer text


class QuizGradeOut(BaseModel):
    quiz_id: uuid.UUID
    total_questions: int
    correct_answers: int
    score_percent: float
    feedback: List[Dict[str, Any]]  # detailed feedback for each question


class QuizOut(BaseModel):
    id: uuid.UUID
    subject_id: uuid.UUID
    title: str
    quiz_type: str
    questions_data: Dict[str, Any]  # carries list of questions and choices, but strips answers key
    created_at: datetime

    class Config:
        from_attributes = True
