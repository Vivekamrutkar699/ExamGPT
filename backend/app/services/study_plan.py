import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.study_plan import StudyPlan
from app.models.chunk import Chunk
from app.models.document import Document
from app.repositories.study_plan import study_plan_repository


class StudyPlanService:
    """
    Coordinates study planner logic: partitions durations over detected 
    syllabus units, generates schedules, and recalculates checkpoint progress.
    """

    async def generate_study_plan(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        subject_id: uuid.UUID,
        days_duration: int = 30
    ) -> StudyPlan:
        """
        Gathers distinct indexed syllabus units for a course subject,
        generates checkpoint schedules, and writes the new StudyPlan.
        """
        # 1. Fetch distinct syllabus unit tags indexed for this subject
        stmt = (
            select(Chunk.unit_tag)
            .join(Document, Chunk.document_id == Document.id)
            .where(Document.subject_id == subject_id)
            .where(Chunk.unit_tag != None)
            .distinct()
        )
        result = await db.execute(stmt)
        detected_units = sorted([u for u in result.scalars().all() if u])

        # Fallback to standard SPPU 6-unit structure if no materials are indexed yet
        if not detected_units:
            detected_units = ["Unit 1", "Unit 2", "Unit 3", "Unit 4", "Unit 5", "Unit 6"]

        # 2. Divide days_duration among units
        num_units = len(detected_units)
        days_per_unit = max(1, days_duration // num_units)
        
        checkpoints = []
        current_day = 1
        
        for idx, unit in enumerate(detected_units):
            # Calculate days boundaries
            start_day = current_day
            end_day = min(days_duration, current_day + days_per_unit - 1)
            # Make sure the last unit covers up to the final duration day
            if idx == num_units - 1:
                end_day = days_duration
                
            checkpoints.append({
                "id": f"unit_chk_{idx + 1}",
                "title": f"Study and Review {unit} core concepts",
                "unit_tag": unit,
                "days_range": f"Day {start_day} - Day {end_day}",
                "completed": False
            })
            
            current_day = end_day + 1

        schedule = {
            "progress_percent": 0.0,
            "checkpoints": checkpoints
        }

        # 3. Calculate start/end dates
        start_date = datetime.utcnow()
        end_date = start_date + timedelta(days=days_duration)

        # 4. Save and return plan
        return await study_plan_repository.create_plan(
            db=db,
            user_id=user_id,
            subject_id=subject_id,
            schedule=schedule,
            start_date=start_date,
            end_date=end_date
        )

    async def update_checkpoint(
        self,
        db: AsyncSession,
        plan_id: uuid.UUID,
        user_id: uuid.UUID,
        item_id: str,
        completed: bool
    ) -> StudyPlan:
        """
        Updates the completion status of a target checklist checkpoint,
        re-calculates the overall progress percent, and commits changes.
        """
        plan = await study_plan_repository.get_by_id(db, plan_id=plan_id)
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Study plan not found."
            )
            
        if plan.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this study plan."
            )

        schedule = dict(plan.schedule)
        checkpoints = schedule.get("checkpoints", [])
        
        found = False
        for chk in checkpoints:
            if chk["id"] == item_id:
                chk["completed"] = completed
                found = True
                break
                
        if not found:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Checkpoint item ID '{item_id}' not found in study plan schedule."
            )

        # Recalculate progress percentage
        completed_count = sum(1 for chk in checkpoints if chk.get("completed", False))
        total_count = len(checkpoints)
        progress = float(completed_count / total_count) * 100.0 if total_count > 0 else 0.0
        
        schedule["progress_percent"] = round(progress, 1)
        schedule["checkpoints"] = checkpoints

        return await study_plan_repository.update_plan(db, db_plan=plan, schedule=schedule)


# Singleton service instance
study_plan_service = StudyPlanService()
