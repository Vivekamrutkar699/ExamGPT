import uuid
from typing import Any

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.document_processing.metadata import metadata_extractor
from app.models.pyq_topic import CanonicalTopic, PYQPaper, PYQQuestionOccurrence, QuestionVariant, TopicResolution
from app.models.question import Question
from app.repositories.pyq_topic import pyq_topic_repository
from app.services.pyq_topic_resolution import (
    EmbeddingEncoder, QuestionNormalizer, SentenceTransformerEmbeddingEncoder,
    TopicCandidate, TopicMatchPolicy, cosine_similarity,
)


class PYQTopicIngestionService:
    def __init__(self, encoder: EmbeddingEncoder | None = None):
        self.encoder = encoder or SentenceTransformerEmbeddingEncoder()
        self.normalizer = QuestionNormalizer()
        self.policy = TopicMatchPolicy()

    async def _compatibility_question(self, db: AsyncSession, variant: QuestionVariant) -> Question | None:
        if variant.topic_id:
            topic = await db.get(CanonicalTopic, variant.topic_id)
            if topic and topic.compatibility_question_id:
                return await db.get(Question, topic.compatibility_question_id)
        return await db.get(Question, variant.legacy_question_id) if variant.legacy_question_id else None

    async def _create_topic(self, db: AsyncSession, subject_id: uuid.UUID, text: str, normalized: str, vector: list[float], unit_tag: str, marks: int):
        compatibility = Question(subject_id=subject_id, text=text, marks_weight=marks, unit_tag=unit_tag, is_pyq=True, occurrences=0)
        db.add(compatibility)
        await db.flush()
        topic = CanonicalTopic(subject_id=subject_id, canonical_label=normalized[:255], normalized_label=normalized[:255], unit_tag=unit_tag, compatibility_question_id=compatibility.id, embedding_json=vector, embedding_model_version=self.encoder.model_version)
        db.add(topic)
        await db.flush()
        return topic, compatibility

    async def resolve(self, db: AsyncSession, subject_id: uuid.UUID, text: str, marks: int, question_number: str | None) -> tuple[QuestionVariant, Question]:
        normalized = self.normalizer.normalize(text)
        digest = self.normalizer.digest(normalized)
        existing = await pyq_topic_repository.variant_by_hash(db, subject_id, digest)
        if existing:
            question = await self._compatibility_question(db, existing)
            if question is None:
                question = Question(subject_id=subject_id, text=text, marks_weight=marks, unit_tag="General/Unmapped", is_pyq=True, occurrences=0)
                db.add(question); await db.flush(); existing.legacy_question_id = question.id
            return existing, question

        vector = self.encoder.encode([normalized])[0]
        meta = metadata_extractor.extract_metadata(text)
        unit_tag = meta["unit_tag"] or "General/Unmapped"
        topic_scores: dict[uuid.UUID, float] = {}
        for candidate in await pyq_topic_repository.embedded_variants(db, subject_id, self.encoder.model_version):
            score = cosine_similarity(vector, candidate.embedding_json or [])
            topic_scores[candidate.topic_id] = max(topic_scores.get(candidate.topic_id, -1.0), score)
        candidates = [TopicCandidate(topic_id=topic_id, score=score) for topic_id, score in topic_scores.items()]
        candidates.sort(key=lambda item: item.score, reverse=True)
        decision = self.policy.decide(candidates)
        if decision.resolution_type == "semantic_match":
            topic = await db.get(CanonicalTopic, decision.topic_id)
            question = await db.get(Question, topic.compatibility_question_id)
            topic_id = topic.id
        elif decision.resolution_type == "new_topic":
            topic, question = await self._create_topic(db, subject_id, text, normalized, vector, unit_tag, marks)
            topic_id = topic.id
        else:
            topic_id = None
            question = Question(subject_id=subject_id, text=text, marks_weight=marks, unit_tag=unit_tag, is_pyq=True, occurrences=0)
            db.add(question); await db.flush()
        variant = QuestionVariant(subject_id=subject_id, topic_id=topic_id, legacy_question_id=question.id if topic_id is None else None, text=text, normalized_text=normalized, normalized_hash=digest, embedding_json=vector, embedding_model_version=self.encoder.model_version, similarity_score=decision.best.score if decision.best else None, matcher_version=settings.PYQ_TOPIC_MATCHER_VERSION, resolution_type=decision.resolution_type)
        db.add(variant); await db.flush()
        db.add(TopicResolution(variant_id=variant.id, best_topic_id=decision.best.topic_id if decision.best else None, second_topic_id=decision.second.topic_id if decision.second else None, best_similarity_score=decision.best.score if decision.best else None, second_similarity_score=decision.second.score if decision.second else None, similarity_threshold=settings.PYQ_TOPIC_MATCH_THRESHOLD, ambiguity_margin=settings.PYQ_TOPIC_AMBIGUITY_MARGIN, matcher_version=settings.PYQ_TOPIC_MATCHER_VERSION, resolution_type=decision.resolution_type))
        return variant, question

    async def ingest(self, db: AsyncSession, subject_id: uuid.UUID, parsed: list[dict[str, Any]], paper_text: str, metadata: dict[str, Any] | None = None) -> list[Question]:
        content_hash = self.normalizer.paper_digest(paper_text)
        existing_paper = await pyq_topic_repository.paper_by_hash(db, subject_id, content_hash)
        if existing_paper:
            return await self._questions_for_paper(db, existing_paper)
        metadata = metadata or {}
        paper = PYQPaper(subject_id=subject_id, content_hash=content_hash, title=metadata.get("paper_title"), exam_year=metadata.get("exam_year"), exam_session=metadata.get("exam_session"), source_filename=metadata.get("source_filename"), source_reference=metadata.get("source_reference"))
        db.add(paper); await db.flush()
        questions: list[Question] = []
        for item in parsed:
            variant, question = await self.resolve(db, subject_id, item["text"], item["marks_weight"], item.get("question_number"))
            question.occurrences += 1
            db.add(PYQQuestionOccurrence(paper_id=paper.id, variant_id=variant.id, question_number=item.get("question_number"), source_text=item["text"], marks_weight=item["marks_weight"], unit_tag=question.unit_tag))
            questions.append(question)
        await db.commit()
        for question in questions: await db.refresh(question)
        return questions

    async def _questions_for_paper(self, db: AsyncSession, paper: PYQPaper) -> list[Question]:
        output: list[Question] = []
        for occurrence in await pyq_topic_repository.occurrences_for_paper(db, paper.id):
            variant = await db.get(QuestionVariant, occurrence.variant_id)
            question = await self._compatibility_question(db, variant)
            if question: output.append(question)
        return output


pyq_topic_ingestion_service = PYQTopicIngestionService()
