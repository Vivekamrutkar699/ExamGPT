import uuid
from typing import List, Optional
from pydantic import BaseModel, Field


class StudentTopicPerformanceOut(BaseModel):
    """
    Explicit schema for a student's performance on a canonical topic.
    """
    student_id: uuid.UUID = Field(..., description="ID of the authenticated student")
    subject_id: uuid.UUID = Field(..., description="ID of the course subject")
    topic_id: uuid.UUID = Field(..., description="ID of the canonical topic")
    canonical_label: str = Field(..., description="Display label of the canonical topic")
    unit_tag: Optional[str] = Field(None, description="Syllabus unit tag if available")
    evaluation_count: int = Field(..., ge=0, description="Total number of evaluated answers on this topic")
    mastery: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Normalized mastery score [0.0, 1.0]. None if no student evaluation data exists."
    )
    weakness: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Weakness score (1.0 - mastery). None if no student evaluation data exists."
    )
    has_student_data: bool = Field(..., description="True if student has at least one valid evaluation")

    class Config:
        from_attributes = True


class SubjectTopicPerformanceOut(BaseModel):
    """
    Complete subject-level topic performance report for an authenticated student.
    """
    subject_id: uuid.UUID
    student_id: uuid.UUID
    total_topics: int = Field(..., ge=0, description="Total canonical topics defined for the subject")
    evaluated_topics_count: int = Field(..., ge=0, description="Number of topics with at least one evaluation")
    unresolved_evaluations_count: int = Field(
        0, ge=0, description="Evaluations that could not be mapped to a canonical topic"
    )
    has_student_data: bool = Field(..., description="True if student has any valid evaluations in this subject")
    topics: List[StudentTopicPerformanceOut] = Field(default_factory=list)

    class Config:
        from_attributes = True
