import uuid
from typing import List, Optional
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


class TopicEvidenceOut(BaseModel):
    frequency_rationale: str
    marks_rationale: str
    mastery_rationale: str
    recommendation: str

    class Config:
        from_attributes = True


class ExamPriorityTopicOut(BaseModel):
    topic_id: uuid.UUID
    canonical_label: str
    unit_tag: Optional[str] = None
    total_occurrences: int
    distinct_papers: int
    avg_marks: float
    max_marks: int
    frequency_score: float
    marks_score: float
    student_mastery: Optional[float] = None
    weakness_score: Optional[float] = None
    priority_score: float
    priority_label: str
    evaluation_count: int
    has_student_data: bool
    evidence: TopicEvidenceOut
    recommendation: str

    class Config:
        from_attributes = True


class SubjectExamPriorityOut(BaseModel):
    subject_id: uuid.UUID
    has_student_data: bool
    total_topics: int
    unresolved_occurrences_count: int
    topics: List[ExamPriorityTopicOut]

    class Config:
        from_attributes = True
