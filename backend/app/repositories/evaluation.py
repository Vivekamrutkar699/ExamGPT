import uuid
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.answers_evaluation import AnswersEvaluation
from app.models.question import Question


class EvaluationRepository:
    """
    Manages database transactions for student essay answer evaluations.
    """

    async def create_evaluation(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        question_id: uuid.UUID,
        user_submitted_answer: str,
        feedback: str,
        estimated_marks: float,
        max_marks: float,
        improvement_points: dict
    ) -> AnswersEvaluation:
        """Create and save a new AnswersEvaluation record."""
        db_eval = AnswersEvaluation(
            user_id=user_id,
            question_id=question_id,
            user_submitted_answer=user_submitted_answer,
            feedback=feedback,
            estimated_marks=estimated_marks,
            max_marks=max_marks,
            improvement_points=improvement_points
        )
        db.add(db_eval)
        await db.commit()
        await db.refresh(db_eval)
        return db_eval

    async def get_by_id(
        self, 
        db: AsyncSession, 
        eval_id: uuid.UUID
    ) -> Optional[AnswersEvaluation]:
        """Retrieve a specific evaluation details."""
        result = await db.execute(
            select(AnswersEvaluation).where(AnswersEvaluation.id == eval_id)
        )
        return result.scalars().first()

    async def list_by_user_subject(
        self, 
        db: AsyncSession, 
        user_id: uuid.UUID, 
        subject_id: uuid.UUID
    ) -> List[AnswersEvaluation]:
        """List all evaluations completed by a student for a subject."""
        result = await db.execute(
            select(AnswersEvaluation)
            .join(Question, AnswersEvaluation.question_id == Question.id)
            .where(AnswersEvaluation.user_id == user_id, Question.subject_id == subject_id)
            .order_by(AnswersEvaluation.evaluated_at.desc())
        )
        return list(result.scalars().all())

    async def delete_evaluation(
        self, 
        db: AsyncSession, 
        eval_id: uuid.UUID
    ) -> Optional[AnswersEvaluation]:
        """Delete an evaluation record."""
        db_eval = await self.get_by_id(db, eval_id=eval_id)
        if db_eval:
            await db.delete(db_eval)
            await db.commit()
            return db_eval
        return None


# Singleton repository instance
evaluation_repository = EvaluationRepository()
