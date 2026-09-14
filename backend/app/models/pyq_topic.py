import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base_class import Base


class PYQPaper(Base):
    """A real uploaded examination paper that contains PYQ occurrences."""

    __tablename__ = "pyq_paper"
    __table_args__ = (UniqueConstraint("subject_id", "content_hash", name="uq_pyq_paper_subject_hash"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subject.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    exam_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    exam_session: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    source_filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_reference: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )


class CanonicalTopic(Base):
    """A subject-scoped concept with a deterministic, reviewable label."""

    __tablename__ = "canonical_topic"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subject.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    canonical_label: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_label: Mapped[str] = mapped_column(String(255), nullable=False)
    label_source: Mapped[str] = mapped_column(
        String(50), default="auto_normalized", nullable=False
    )
    is_label_reviewed: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    unit_tag: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    compatibility_question_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("question.id", ondelete="SET NULL"), nullable=True, unique=True
    )
    embedding_json: Mapped[Optional[list[float]]] = mapped_column(JSON, nullable=True)
    embedding_model_version: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )


class QuestionVariant(Base):
    """One wording of a topic, including an auditable future match decision."""

    __tablename__ = "question_variant"

    __table_args__ = (
        UniqueConstraint(
            "subject_id", "normalized_hash", name="uq_question_variant_subject_hash"
        ),
        Index("ix_question_variant_topic_id", "topic_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subject.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    topic_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canonical_topic.id", ondelete="SET NULL"),
        nullable=True,
    )
    legacy_question_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("question.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding_json: Mapped[Optional[list[float]]] = mapped_column(JSON, nullable=True)
    embedding_model_version: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    similarity_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    matcher_version: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    resolution_type: Mapped[str] = mapped_column(
        String(50), default="unresolved", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )


class PYQQuestionOccurrence(Base):
    """One question variant as it appeared in one real PYQ paper."""

    __tablename__ = "pyq_question_occurrence"

    __table_args__ = (
        Index("ix_pyq_question_occurrence_paper_variant", "paper_id", "variant_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    paper_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pyq_paper.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("question_variant.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    marks_weight: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_tag: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    chapter: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )


class TopicResolution(Base):
    """Immutable evidence for a non-exact topic-resolution decision."""

    __tablename__ = "topic_resolution"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("question_variant.id", ondelete="CASCADE"), nullable=False, index=True
    )
    best_topic_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("canonical_topic.id", ondelete="SET NULL"), nullable=True
    )
    second_topic_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("canonical_topic.id", ondelete="SET NULL"), nullable=True
    )
    best_similarity_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    second_similarity_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    similarity_threshold: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ambiguity_margin: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    matcher_version: Mapped[str] = mapped_column(String(100), nullable=False)
    resolution_type: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
