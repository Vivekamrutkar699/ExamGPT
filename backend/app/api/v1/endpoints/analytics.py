import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.schemas.analytics import SubjectAnalyticsOut
from app.services.analytics import analytics_service
from app.models.user import User

router = APIRouter()


@router.get("/subjects/{subject_id}", response_model=SubjectAnalyticsOut)
async def get_subject_analytics_report(
    subject_id: uuid.UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Retrieve aggregated analytics reports including study progresses, quiz frequencies,
    essay scores, and weakness flags for a course subject.
    """
    # Verify Course Subject exists
    from app.models.subject import Subject
    subject = await db.get(Subject, subject_id)
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The referenced Course Subject ID does not exist."
        )

    return await analytics_service.get_subject_analytics_report(
        db=db,
        user_id=current_user.id,
        subject_id=subject_id
    )
