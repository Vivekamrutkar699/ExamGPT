import uuid
from typing import List
from pydantic import BaseModel


class SubjectAnalyticsOut(BaseModel):
    subject_id: uuid.UUID
    study_progress: float  # completion rate of StudyPlan checkpoints
    total_quizzes_taken: int
    average_quiz_score: float
    total_essays_evaluated: int
    average_essay_score: float
    weak_units: List[str]  # syllabus units scoring less than 60%
    total_materials_uploaded: int
    total_chunks_indexed: int

    class Config:
        from_attributes = True
