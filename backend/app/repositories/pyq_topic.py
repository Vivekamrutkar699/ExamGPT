import uuid
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pyq_topic import CanonicalTopic, PYQPaper, PYQQuestionOccurrence, QuestionVariant, TopicResolution


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


pyq_topic_repository = PYQTopicRepository()
