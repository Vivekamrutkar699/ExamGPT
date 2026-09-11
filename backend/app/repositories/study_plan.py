import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.study_plan import StudyPlan


class StudyPlanRepository:
    """
    Manages database operations for generating, retrieving, and updating StudyPlans.
    """

    async def create_plan(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        subject_id: uuid.UUID,
        schedule: dict,
        start_date: datetime,
        end_date: datetime
    ) -> StudyPlan:
        """Create a new StudyPlan entity."""
        db_plan = StudyPlan(
            user_id=user_id,
            subject_id=subject_id,
            schedule=schedule,
            start_date=start_date,
            end_date=end_date
        )
        db.add(db_plan)
        await db.commit()
        await db.refresh(db_plan)
        return db_plan

    async def get_by_id(
        self, 
        db: AsyncSession, 
        plan_id: uuid.UUID
    ) -> Optional[StudyPlan]:
        """Retrieve a specific StudyPlan details."""
        result = await db.execute(select(StudyPlan).where(StudyPlan.id == plan_id))
        return result.scalars().first()

    async def get_active_by_user_subject(
        self, 
        db: AsyncSession, 
        user_id: uuid.UUID, 
        subject_id: uuid.UUID
    ) -> Optional[StudyPlan]:
        """Fetch the active StudyPlan for a student and subject."""
        result = await db.execute(
            select(StudyPlan)
            .where(StudyPlan.user_id == user_id, StudyPlan.subject_id == subject_id)
            .order_by(StudyPlan.start_date.desc())
        )
        return result.scalars().first()

    async def update_plan(
        self, 
        db: AsyncSession, 
        db_plan: StudyPlan, 
        schedule: dict
    ) -> StudyPlan:
        """Update the JSON schedule structure and committed progression checkpoints."""
        db_plan.schedule = schedule
        db.add(db_plan)
        await db.commit()
        await db.refresh(db_plan)
        return db_plan

    async def delete_plan(
        self, 
        db: AsyncSession, 
        plan_id: uuid.UUID
    ) -> Optional[StudyPlan]:
        """Remove a study plan from database."""
        db_plan = await self.get_by_id(db, plan_id=plan_id)
        if db_plan:
            await db.delete(db_plan)
            await db.commit()
            return db_plan
        return None


# Singleton repository instance
study_plan_repository = StudyPlanRepository()
