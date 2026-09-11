import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.schemas.evaluation import EvaluationCreate, EvaluationOut
from app.services.evaluation import evaluation_service
from app.repositories.evaluation import evaluation_repository
from app.models.user import User

router = APIRouter()


@router.post("/", response_model=EvaluationOut, status_code=status.HTTP_201_CREATED)
async def evaluate_essay_answer(
    eval_in: EvaluationCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Submit a long-form essay answer for scoring and detailed revision feedback.
    """
    return await evaluation_service.evaluate_student_answer(
        db=db,
        user_id=current_user.id,
        question_id=eval_in.question_id,
        user_submitted_answer=eval_in.user_submitted_answer
    )


@router.get("/subject/{subject_id}", response_model=List[EvaluationOut])
async def list_my_essay_evaluations(
    subject_id: uuid.UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    List all essay evaluations completed by the logged-in student for a subject.
    """
    # Verify Subject exists
    from app.models.subject import Subject
    subject = await db.get(Subject, subject_id)
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The referenced Course Subject ID does not exist."
        )

    return await evaluation_repository.list_by_user_subject(
        db=db,
        user_id=current_user.id,
        subject_id=subject_id
    )


@router.get("/{evaluation_id}", response_model=EvaluationOut)
async def get_essay_evaluation_by_id(
    evaluation_id: uuid.UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Retrieve grading details and structural feedback for a specific evaluation.
    """
    db_eval = await evaluation_repository.get_by_id(db=db, eval_id=evaluation_id)
    if not db_eval:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation record not found."
        )
        
    if db_eval.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this evaluation record."
        )
        
    return db_eval


@router.delete("/{evaluation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_essay_evaluation(
    evaluation_id: uuid.UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Delete an evaluation record.
    """
    db_eval = await evaluation_repository.get_by_id(db=db, eval_id=evaluation_id)
    if not db_eval:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation record not found."
        )
        
    if db_eval.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this evaluation record."
        )

    await evaluation_repository.delete_evaluation(db=db, eval_id=evaluation_id)
