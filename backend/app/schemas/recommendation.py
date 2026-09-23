import uuid
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class RecommendationAction(str, Enum):
    """
    Controlled vocabulary of deterministic learning recommendations.
    """
    PRACTICE = "PRACTICE"  # High/Med priority with demonstrated weakness (< 0.50)
    QUIZ = "QUIZ"          # High priority with partial mastery [0.50, 0.75)
    ASSESS = "ASSESS"      # High/Med priority without student performance data
    REVIEW = "REVIEW"      # Low priority or Med partial mastery
    MAINTAIN = "MAINTAIN"  # High/Med strong mastery (>= 0.75) or Low adequate mastery


class TopicRecommendationOut(BaseModel):
    """
    Pydantic schema representing a deterministic recommendation for a canonical topic.
    """
    topic_id: uuid.UUID
    canonical_label: str
    unit_tag: Optional[str] = None
    priority_score: float
    priority_label: str
    student_mastery: Optional[float] = None
    weakness_score: Optional[float] = None
    evaluation_count: int
    recommended_action: RecommendationAction
    recommendation_reason: str
    action_priority: int
    action_endpoint: Optional[str] = None

    class Config:
        from_attributes = True


class SubjectRecommendationsOut(BaseModel):
    """
    Pydantic schema for the subject-level learning recommendations response.
    """
    subject_id: uuid.UUID
    has_student_data: bool
    total_recommendations: int
    recommendations: List[TopicRecommendationOut]

    class Config:
        from_attributes = True


# =====================================================================
# Phase 7D: Action Execution Schemas
# =====================================================================


class PracticeResourceOut(BaseModel):
    """
    Specific practice question resource linked to the canonical topic.
    Submissions route directly to the evaluation service.
    """
    question_id: uuid.UUID
    text: str
    marks_weight: int
    unit_tag: Optional[str] = None
    source_scope: str = "topic"  # "topic" or "unit"
    submission_endpoint: str = "/api/v1/evaluations/"

    class Config:
        from_attributes = True


class QuizActionOut(BaseModel):
    """
    Topic-focused or diagnostic quiz worksheet generated via existing quiz infrastructure.
    """
    quiz_id: uuid.UUID
    title: str
    quiz_type: str
    total_questions: int
    questions: List[Dict[str, Any]]
    submission_endpoint: str

    class Config:
        from_attributes = True


class ReviewChunkOut(BaseModel):
    """
    Grounded document context chunk for topic review.
    """
    chunk_id: str
    document_name: str
    page: Optional[int] = None
    content: str
    unit_tag: Optional[str] = None

    class Config:
        from_attributes = True


class ReviewActionOut(BaseModel):
    """
    Syllabus notes and document-grounded review material for concept consolidation.
    """
    summary: str
    key_concepts: List[str]
    supporting_chunks: List[ReviewChunkOut]

    class Config:
        from_attributes = True


class MaintainActionOut(BaseModel):
    """
    Lightweight revision takeaways and refresher sample for strong-mastery topics.
    """
    key_takeaways: List[str]
    quick_revision_notes: List[str]
    sample_question: Optional[PracticeResourceOut] = None

    class Config:
        from_attributes = True


class TopicActionResponse(BaseModel):
    """
    Concrete learning action payload resolving a deterministic recommendation.
    """
    subject_id: uuid.UUID
    topic_id: uuid.UUID
    canonical_label: str
    unit_tag: Optional[str] = None
    action: RecommendationAction
    action_priority: int
    reason: str
    practice_data: Optional[List[PracticeResourceOut]] = None
    quiz_data: Optional[QuizActionOut] = None
    review_data: Optional[ReviewActionOut] = None
    maintain_data: Optional[MaintainActionOut] = None

    class Config:
        from_attributes = True
