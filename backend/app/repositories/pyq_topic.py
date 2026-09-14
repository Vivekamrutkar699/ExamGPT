import uuid
from dataclasses import dataclass
from typing import Optional, Sequence

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pyq_topic import (
    CanonicalTopic,
    PYQPaper,
    PYQQuestionOccurrence,
    QuestionVariant,
    TopicResolution,
)


@dataclass(frozen=True)
class TopicAggregate:
    topic_id: uuid.UUID
    canonical_label: str
    normalized_label: str
    unit_tag: Optional[str]
    total_occurrences: int
    distinct_papers: int
    avg_marks: float
    max_marks: int


class PYQTopicRepository:
    async def paper_by_hash(self, db: AsyncSession, subject_id: uuid.UUID, content_hash: str):
        return (await db.execute(select(PYQPaper).where(PYQPaper.subject_id == subject_id, PYQPaper.content_hash == content_hash))).scalar_one_or_none()

    async def variant_by_hash(self, db: AsyncSession, subject_id: uuid.UUID, normalized_hash: str):
        return (await db.execute(select(QuestionVariant).where(QuestionVariant.subject_id == subject_id, QuestionVariant.normalized_hash == normalized_hash))).scalar_one_or_none()

    async def embedded_variants(self, db: AsyncSession, subject_id: uuid.UUID, model_version: str) -> list[QuestionVariant]:
        result = await db.execute(select(QuestionVariant).where(
            QuestionVariant.subject_id == subject_id,
            QuestionVariant.topic_id.is_not(None),
            QuestionVariant.embedding_json.is_not(None),
            QuestionVariant.embedding_model_version == model_version,
        ))
        return list(result.scalars().all())

    async def occurrences_for_paper(self, db: AsyncSession, paper_id: uuid.UUID) -> list[PYQQuestionOccurrence]:
        return list((await db.execute(select(PYQQuestionOccurrence).where(PYQQuestionOccurrence.paper_id == paper_id).order_by(PYQQuestionOccurrence.created_at))).scalars().all())

    async def get_topic_aggregates(
        self, db: AsyncSession, subject_id: uuid.UUID
    ) -> list[TopicAggregate]:
        stmt = (
            select(
                CanonicalTopic.id.label("topic_id"),
                CanonicalTopic.canonical_label,
                CanonicalTopic.normalized_label,
                CanonicalTopic.unit_tag,
                func.count(PYQQuestionOccurrence.id).label("total_occurrences"),
                func.count(func.distinct(PYQPaper.id)).label("distinct_papers"),
                func.avg(PYQQuestionOccurrence.marks_weight).label("avg_marks"),
                func.max(PYQQuestionOccurrence.marks_weight).label("max_marks"),
            )
            .outerjoin(
                QuestionVariant,
                and_(
                    QuestionVariant.topic_id == CanonicalTopic.id,
                    QuestionVariant.subject_id == subject_id,
                ),
            )
            .outerjoin(
                PYQQuestionOccurrence,
                PYQQuestionOccurrence.variant_id == QuestionVariant.id,
            )
            .outerjoin(
                PYQPaper,
                and_(
                    PYQPaper.id == PYQQuestionOccurrence.paper_id,
                    PYQPaper.subject_id == subject_id,
                ),
            )
            .where(CanonicalTopic.subject_id == subject_id)
            .group_by(
                CanonicalTopic.id,
                CanonicalTopic.canonical_label,
                CanonicalTopic.normalized_label,
                CanonicalTopic.unit_tag,
            )
            .order_by(
                func.count(PYQQuestionOccurrence.id).desc(),
                CanonicalTopic.canonical_label.asc(),
            )
        )
        result = await db.execute(stmt)
        aggregates: list[TopicAggregate] = []
        for row in result.all():
            aggregates.append(
                TopicAggregate(
                    topic_id=row.topic_id,
                    canonical_label=row.canonical_label,
                    normalized_label=row.normalized_label,
                    unit_tag=row.unit_tag,
                    total_occurrences=int(row.total_occurrences or 0),
                    distinct_papers=int(row.distinct_papers or 0),
                    avg_marks=float(row.avg_marks) if row.avg_marks is not None else 0.0,
                    max_marks=int(row.max_marks) if row.max_marks is not None else 0,
                )
            )
        return aggregates

    async def get_unresolved_variants(
        self, db: AsyncSession, subject_id: uuid.UUID
    ) -> list[QuestionVariant]:
        stmt = (
            select(QuestionVariant)
            .where(
                QuestionVariant.subject_id == subject_id,
                QuestionVariant.topic_id.is_(None),
            )
            .order_by(QuestionVariant.created_at.asc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())


pyq_topic_repository = PYQTopicRepository()
