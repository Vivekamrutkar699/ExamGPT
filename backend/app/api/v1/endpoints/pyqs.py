import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.api import deps
from app.schemas.question import QuestionOut, PYQAnalyticsOut
from app.services.pyq import pyq_service
from app.repositories.question import question_repository
from app.models.user import User

router = APIRouter()


class PYQTextInput(BaseModel):
    paper_text: str
    paper_title: Optional[str] = None
    exam_year: Optional[int] = None
    exam_session: Optional[str] = None
    source_filename: Optional[str] = None
    source_reference: Optional[str] = None


@router.post("/subjects/{subject_id}/upload", response_model=List[QuestionOut], status_code=status.HTTP_201_CREATED)
async def upload_pyq_paper_text(
    subject_id: uuid.UUID,
    input_data: PYQTextInput,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Ingest questions from a raw exam paper text stream, parse their properties,
    and update occurrences semantic metrics.
    """
    # Verify Subject exists
    from app.models.subject import Subject
    subject = await db.get(Subject, subject_id)
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The referenced Course Subject ID does not exist."
        )

    return await pyq_service.ingest_pyq_text(
        db=db,
        subject_id=subject_id,
        text=input_data.paper_text,
        paper_metadata=input_data.model_dump(exclude={"paper_text"}, exclude_none=True),
    )


@router.get("/subjects/{subject_id}/analytics", response_model=PYQAnalyticsOut)
async def get_pyq_subject_analytics(
    subject_id: uuid.UUID,
    db: AsyncSession = Depends(deps.get_db)
):
    """
    Retrieve marks distribution and recurring topic counts for a subject.
    """
    # Verify Subject exists
    from app.models.subject import Subject
    subject = await db.get(Subject, subject_id)
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The referenced Course Subject ID does not exist."
        )

    return await pyq_service.get_subject_analytics(db=db, subject_id=subject_id)


@router.get("/subjects/{subject_id}/list", response_model=List[QuestionOut])
async def list_subject_questions(
    subject_id: uuid.UUID,
    db: AsyncSession = Depends(deps.get_db)
):
    """
    List all questions indexed for a subject.
    """
    # Verify Subject exists
    from app.models.subject import Subject
    subject = await db.get(Subject, subject_id)
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The referenced Course Subject ID does not exist."
        )

    return await question_repository.get_by_subject(db=db, subject_id=subject_id)
