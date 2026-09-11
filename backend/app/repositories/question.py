import uuid
import numpy as np
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.question import Question
from app.schemas.question import QuestionCreate
from app.document_processing.chunking import get_embedding_model


class QuestionRepository:
    """
    CRUD repository for Question entities, providing semantic similarity
    duplicate checking on SPPU past papers.
    """

    async def get_by_subject(
        self, 
        db: AsyncSession, 
        subject_id: uuid.UUID
    ) -> List[Question]:
        """Fetch all indexed questions for a given subject."""
        result = await db.execute(
            select(Question)
            .where(Question.subject_id == subject_id)
            .order_by(Question.occurrences.desc())
        )
        return list(result.scalars().all())

    async def find_similar(
        self,
        db: AsyncSession,
        subject_id: uuid.UUID,
        text: str,
        threshold: float = 0.78
    ) -> Optional[Question]:
        """
        Queries all existing questions in the subject vault, computes cosine
        similarities using SentenceTransformer, and returns the match if above threshold.
        """
        existing_qs = await self.get_by_subject(db, subject_id=subject_id)
        if not existing_qs:
            return None

        # Encode new query text
        model = get_embedding_model()
        query_emb = model.encode(text)

        # Encode existing questions
        texts = [q.text for q in existing_qs]
        embs = model.encode(texts)

        best_score = -1.0
        best_match = None

        for idx, emb in enumerate(embs):
            # Calculate Cosine similarity
            dot = np.dot(query_emb, emb)
            norm_q = np.linalg.norm(query_emb)
            norm_e = np.linalg.norm(emb)
            score = float(dot / (norm_q * norm_e)) if norm_q > 0 and norm_e > 0 else 0.0

            if score > best_score:
                best_score = score
                best_match = existing_qs[idx]

        if best_score >= threshold:
            return best_match
        return None

    async def create(
        self, 
        db: AsyncSession, 
        obj_in: QuestionCreate
    ) -> Question:
        """Insert a new question record into database."""
        db_question = Question(
            subject_id=obj_in.subject_id,
            text=obj_in.text,
            marks_weight=obj_in.marks_weight,
            unit_tag=obj_in.unit_tag,
            is_pyq=obj_in.is_pyq,
            occurrences=obj_in.occurrences
        )
        db.add(db_question)
        await db.commit()
        await db.refresh(db_question)
        return db_question


# Singleton repository instance
question_repository = QuestionRepository()
