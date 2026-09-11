import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.api import deps
from app.schemas.study_plan import StudyPlanCreate, StudyPlanOut, StudyPlanUpdate
from app.services.study_plan import study_plan_service
from app.repositories.study_plan import study_plan_repository
from app.models.user import User

router = APIRouter()


class CheckpointUpdateInput(BaseModel):
    item_id: str
    completed: bool


@router.post("/", response_model=StudyPlanOut, status_code=status.HTTP_201_CREATED)
async def create_study_plan(
    plan_in: StudyPlanCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Generate and save a customized study schedule for a subject.
    """
    # Verify Course Subject exists
    from app.models.subject import Subject
    subject = await db.get(Subject, plan_in.subject_id)
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The referenced Course Subject ID does not exist."
        )

    return await study_plan_service.generate_study_plan(
        db=db,
        user_id=current_user.id,
        subject_id=plan_in.subject_id,
        days_duration=plan_in.days_duration
    )


@router.get("/subject/{subject_id}", response_model=StudyPlanOut)
async def get_active_subject_study_plan(
    subject_id: uuid.UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Fetch the active study plan for a subject.
    """
    plan = await study_plan_repository.get_active_by_user_subject(
        db=db,
        user_id=current_user.id,
        subject_id=subject_id
    )
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active study plan found for this course subject."
        )
    return plan


@router.get("/{plan_id}", response_model=StudyPlanOut)
async def get_study_plan_by_id(
    plan_id: uuid.UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Retrieve details of a specific study plan.
    """
    plan = await study_plan_repository.get_by_id(db=db, plan_id=plan_id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Study plan not found."
        )
        
    if plan.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this study plan."
        )
        
    return plan


@router.put("/{plan_id}/checkpoint", response_model=StudyPlanOut)
async def toggle_study_plan_checkpoint(
    plan_id: uuid.UUID,
    chk_in: CheckpointUpdateInput,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Toggle a day/week study checkbox item to update checkpoint completions
    and recalculate overall progress percent values.
    """
    return await study_plan_service.update_checkpoint(
        db=db,
        plan_id=plan_id,
        user_id=current_user.id,
        item_id=chk_in.item_id,
        completed=chk_in.completed
    )


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_study_plan(
    plan_id: uuid.UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Delete a study plan.
    """
    plan = await study_plan_repository.get_by_id(db=db, plan_id=plan_id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Study plan not found."
        )
        
    if plan.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this study plan."
        )
        
    await study_plan_repository.delete_plan(db=db, plan_id=plan_id)
