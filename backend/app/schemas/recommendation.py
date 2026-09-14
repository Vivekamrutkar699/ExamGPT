import uuid
from enum import Enum
from typing import List, Optional
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
