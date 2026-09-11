import uuid
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.quiz import Quiz


class QuizRepository:
    """
    Manages database CRUD transactions for Quiz worksheets.
    """

    async def create_quiz(
        self,
        db: AsyncSession,
        subject_id: uuid.UUID,
        title: str,
        quiz_type: str,
        questions_data: dict
    ) -> Quiz:
        """Create a new Quiz record."""
        db_quiz = Quiz(
            subject_id=subject_id,
            title=title,
            quiz_type=quiz_type,
            questions_data=questions_data
        )
        db.add(db_quiz)
        await db.commit()
        await db.refresh(db_quiz)
        return db_quiz

    async def get_by_id(
        self, 
        db: AsyncSession, 
        quiz_id: uuid.UUID
    ) -> Optional[Quiz]:
        """Fetch details of a single quiz."""
        result = await db.execute(select(Quiz).where(Quiz.id == quiz_id))
        return result.scalars().first()

    async def list_by_subject(
        self, 
        db: AsyncSession, 
        subject_id: uuid.UUID
    ) -> List[Quiz]:
        """List all generated quizzes linked to a subject."""
        result = await db.execute(
            select(Quiz)
            .where(Quiz.subject_id == subject_id)
            .order_by(Quiz.created_at.desc())
        )
        return list(result.scalars().all())

    async def delete_quiz(
        self, 
        db: AsyncSession, 
        quiz_id: uuid.UUID
    ) -> Optional[Quiz]:
        """Delete a quiz from database."""
        db_quiz = await self.get_by_id(db, quiz_id=quiz_id)
        if db_quiz:
            await db.delete(db_quiz)
            await db.commit()
            return db_quiz
        return None


# Singleton repository instance
quiz_repository = QuizRepository()
