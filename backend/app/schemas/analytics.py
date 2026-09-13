import uuid
from typing import List, Optional

from pydantic import BaseModel


class SubjectAnalyticsOut(BaseModel):
    subject_id: uuid.UUID
    study_progress: float
    total_quizzes_taken: int
    average_quiz_score: float
    total_essays_evaluated: int
    average_essay_score: float
    weak_units: List[str]
    total_materials_uploaded: int
    total_chunks_indexed: int

    class Config:
        from_attributes = True


class ExamPriorityItem(BaseModel):
    question_id: uuid.UUID
    topic: str

    pyq_occurrences: int
    marks_weight: int

    frequency_score: float
    marks_score: float

    student_mastery: Optional[float] = None
    weakness_score: Optional[float] = None

    priority_score: float
    priority: str


class ExamPriorityOut(BaseModel):
    subject_id: uuid.UUID
    total_topics: int
    topics: List[ExamPriorityItem]