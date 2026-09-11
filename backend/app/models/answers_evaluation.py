import uuid
from datetime import datetime
from sqlalchemy import Text, Float, ForeignKey, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.database.base_class import Base


class AnswersEvaluation(Base):
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("question.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    user_submitted_answer: Mapped[str] = mapped_column(
        Text, 
        nullable=False
    )
    feedback: Mapped[str] = mapped_column(
        Text, 
        nullable=False
    )
    estimated_marks: Mapped[float] = mapped_column(
        Float, 
        nullable=False
    )
    max_marks: Mapped[float] = mapped_column(
        Float, 
        nullable=False
    )
    improvement_points: Mapped[dict] = mapped_column(
        JSON, 
        nullable=True  # JSON array of missing keywords and logic errors
    )
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        nullable=False
    )
