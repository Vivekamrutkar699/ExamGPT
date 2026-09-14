import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.schemas.analytics import SubjectAnalyticsOut, SubjectExamPriorityOut
from app.schemas.topic_performance import SubjectTopicPerformanceOut
from app.schemas.recommendation import SubjectRecommendationsOut
from app.services.analytics import analytics_service
from app.services.student_performance import student_performance_service
from app.services.recommendation import recommendation_service
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


@router.get("/subjects/{subject_id}/exam-priority", response_model=SubjectExamPriorityOut)
async def get_subject_exam_priority(
    subject_id: uuid.UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    """
    Retrieve evidence-based Exam Priority and revision recommendations across
    canonical topics for a course subject.
    """
    from app.models.subject import Subject
    subject = await db.get(Subject, subject_id)
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The referenced Course Subject ID does not exist.",
        )

    return await analytics_service.get_exam_priority_report(
        db=db,
        user_id=current_user.id,
        subject_id=subject_id,
    )


@router.get("/subjects/{subject_id}/topic-performance", response_model=SubjectTopicPerformanceOut)
async def get_subject_topic_performance(
    subject_id: uuid.UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    """
    Retrieve topic-level student performance and mastery metrics for a course subject.
    Distinguishes topics with no student evaluations (mastery = null) from poor performance (mastery = 0.0).
    """
    from app.models.subject import Subject
    subject = await db.get(Subject, subject_id)
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The referenced Course Subject ID does not exist.",
        )

    return await student_performance_service.get_subject_topic_performance(
        db=db,
        user_id=current_user.id,
        subject_id=subject_id,
    )


@router.get("/subjects/{subject_id}/recommendations", response_model=SubjectRecommendationsOut)
async def get_subject_recommendations(
    subject_id: uuid.UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    """
    Retrieve personalized, deterministic next learning action recommendations
    across canonical topics for a course subject.
    """
    from app.models.subject import Subject
    subject = await db.get(Subject, subject_id)
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The referenced Course Subject ID does not exist.",
        )

    return await recommendation_service.get_subject_recommendations(
        db=db,
        user_id=current_user.id,
        subject_id=subject_id,
    )
