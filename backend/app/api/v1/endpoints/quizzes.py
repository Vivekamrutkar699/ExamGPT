import uuid
import copy
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.schemas.quiz import QuizCreate, QuizOut, QuizSubmission, QuizGradeOut
from app.services.quiz import quiz_service
from app.repositories.quiz import quiz_repository
from app.models.user import User

router = APIRouter()


@router.post("/", response_model=QuizOut, status_code=status.HTTP_201_CREATED)
async def generate_mock_quiz(
    quiz_in: QuizCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Generate and save a dynamic quiz worksheet matching course syllabus nodes.
    """
    # Verify Course Subject exists
    from app.models.subject import Subject
    subject = await db.get(Subject, quiz_in.subject_id)
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The referenced Course Subject ID does not exist."
        )

    return await quiz_service.generate_quiz(
        db=db,
        subject_id=quiz_in.subject_id,
        title=quiz_in.title,
        quiz_type=quiz_in.quiz_type,
        unit_tag=quiz_in.unit_tag
    )


@router.get("/subject/{subject_id}", response_model=List[QuizOut])
async def list_subject_quizzes(
    subject_id: uuid.UUID,
    db: AsyncSession = Depends(deps.get_db)
):
    """
    List all quizzes generated for a subject. Hides grading answers keys from listings.
    """
    from app.models.subject import Subject
    subject = await db.get(Subject, subject_id)
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The referenced Course Subject ID does not exist."
        )

    quizzes = await quiz_repository.list_by_subject(db=db, subject_id=subject_id)
    
    # Strip correct answers to prevent cheating in frontend previews
    sanitized_quizzes = []
    for qz in quizzes:
        qz_copy = copy.copy(qz)
        q_list = []
        for q in qz.questions_data.get("questions", []):
            q_copy = copy.deepcopy(q)
            q_copy.pop("correct_answer", None)
            q_copy.pop("explanation", None)
            q_copy.pop("ideal_keywords", None)
            q_list.append(q_copy)
        qz_copy.questions_data = {"questions": q_list}
        sanitized_quizzes.append(qz_copy)
        
    return sanitized_quizzes


@router.get("/{quiz_id}", response_model=QuizOut)
async def get_quiz_by_id(
    quiz_id: uuid.UUID,
    db: AsyncSession = Depends(deps.get_db)
):
    """
    Retrieve details of a single quiz. Strips correct answers, explanations,
    and keyword requirements from response data payload.
    """
    quiz = await quiz_repository.get_by_id(db=db, quiz_id=quiz_id)
    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz worksheet not found."
        )

    # Sanitize questions data to prevent cheating
    quiz_copy = copy.copy(quiz)
    sanitized_questions = []
    
    for q in quiz.questions_data.get("questions", []):
        q_copy = copy.deepcopy(q)
        q_copy.pop("correct_answer", None)
        q_copy.pop("explanation", None)
        q_copy.pop("ideal_keywords", None)
        sanitized_questions.append(q_copy)

    quiz_copy.questions_data = {"questions": sanitized_questions}
    return quiz_copy


@router.post("/{quiz_id}/submit", response_model=QuizGradeOut)
async def submit_and_grade_quiz(
    quiz_id: uuid.UUID,
    submission: QuizSubmission,
    db: AsyncSession = Depends(deps.get_db)
):
    """
    Submit options/answers for grading and obtain detailed feedback comparisons.
    """
    return await quiz_service.grade_quiz(
        db=db,
        quiz_id=quiz_id,
        submission=submission
    )


@router.delete("/{quiz_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_quiz(
    quiz_id: uuid.UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Delete a quiz. Requires administrator privileges or equivalent.
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only course administrators can delete quiz worksheets."
        )
        
    quiz = await quiz_repository.get_by_id(db=db, quiz_id=quiz_id)
    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz worksheet not found."
        )

    await quiz_repository.delete_quiz(db=db, quiz_id=quiz_id)
