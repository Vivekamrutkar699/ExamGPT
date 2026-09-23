import copy
import math
import uuid
from dataclasses import dataclass
from typing import Any, Optional, Sequence
from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pyq_topic import CanonicalTopic, QuestionVariant
from app.models.question import Question
from app.schemas.recommendation import (
    MaintainActionOut,
    PracticeResourceOut,
    QuizActionOut,
    RecommendationAction,
    ReviewActionOut,
    ReviewChunkOut,
    SubjectRecommendationsOut,
    TopicActionResponse,
    TopicRecommendationOut,
)
from app.services.analytics import analytics_service
from app.services.quiz import quiz_service
from app.rag.hybrid_search import hybrid_searcher


@dataclass(frozen=True)
class TopicRecommendation:
    """
    Pure domain model representing an evidence-based, explainable recommendation.
    """
    topic_id: Any
    canonical_label: str
    unit_tag: Optional[str]
    priority_score: float
    priority_label: str
    student_mastery: Optional[float]
    weakness_score: Optional[float]
    evaluation_count: int
    recommended_action: RecommendationAction
    recommendation_reason: str
    action_priority: int
    total_occurrences: int = 0


def _safe_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    try:
        f = float(val)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError, OverflowError):
        return None


def derive_topic_recommendation(topic: Any) -> TopicRecommendation:
    """
    Pure deterministic decision function converting topic-level exam priority
    and student mastery evidence into a recommended next learning action.

    Decision Rules:
    - CASE 1: No student data (mastery is None)
      - High / Very High priority -> ASSESS (Rank 3)
      - Medium priority           -> ASSESS (Rank 5)
      - Low priority              -> REVIEW (Rank 6)
    - CASE 2: High / Very High priority + Low mastery (< 0.50)
      -> PRACTICE (Rank 1)
    - CASE 3: High / Very High priority + Moderate mastery [0.50, 0.75)
      -> QUIZ (Rank 2)
    - CASE 4: High / Very High priority + Strong mastery (>= 0.75)
      -> MAINTAIN (Rank 7)
    - CASE 5: Medium priority
      - Low mastery (< 0.50)               -> PRACTICE (Rank 4)
      - Moderate mastery [0.50, 0.75)      -> REVIEW (Rank 6)
      - Strong mastery (>= 0.75)           -> MAINTAIN (Rank 7)
    - CASE 6: Low priority
      - Low mastery (< 0.50)               -> REVIEW (Rank 6)
      - Adequate / Strong mastery (>= 0.50) -> MAINTAIN (Rank 7)
    """
    topic_id = getattr(topic, "topic_id", None)
    canonical_label = getattr(topic, "canonical_label", "Unknown Topic")
    unit_tag = getattr(topic, "unit_tag", None)
    total_occurrences = getattr(topic, "total_occurrences", 0)

    # Safe priority score
    raw_p_score = getattr(topic, "priority_score", 0.0)
    safe_p_score = _safe_float(raw_p_score)
    priority_score = safe_p_score if safe_p_score is not None else 0.0
    priority_score = max(0.0, min(1.0, priority_score))

    priority_label = getattr(topic, "priority_label", "Low")
    if priority_label not in ("Very High", "High", "Medium", "Low"):
        if priority_score >= 0.75:
            priority_label = "Very High"
        elif priority_score >= 0.55:
            priority_label = "High"
        elif priority_score >= 0.35:
            priority_label = "Medium"
        else:
            priority_label = "Low"

    # Safe mastery & weakness
    raw_mastery = getattr(topic, "student_mastery", None)
    safe_mastery = _safe_float(raw_mastery)
    if safe_mastery is not None:
        safe_mastery = max(0.0, min(1.0, safe_mastery))

    raw_weakness = getattr(topic, "weakness_score", None)
    safe_weakness = _safe_float(raw_weakness)
    if safe_weakness is not None:
        safe_weakness = max(0.0, min(1.0, safe_weakness))
    elif safe_mastery is not None:
        safe_weakness = round(1.0 - safe_mastery, 3)

    eval_count = getattr(topic, "evaluation_count", 0)
    if not isinstance(eval_count, int) or eval_count < 0:
        eval_count = 0

    is_high_priority = priority_label in ("Very High", "High")

    # --- CASE 1: NO STUDENT DATA ---
    if safe_mastery is None:
        if is_high_priority:
            action = RecommendationAction.ASSESS
            action_priority = 3
            reason = (
                "High exam relevance but insufficient student performance data; "
                "assess mastery before targeted revision."
            )
        elif priority_label == "Medium":
            action = RecommendationAction.ASSESS
            action_priority = 5
            reason = (
                "Moderate exam relevance with no student performance data; "
                "assess mastery before targeted revision."
            )
        else:
            action = RecommendationAction.REVIEW
            action_priority = 6
            reason = (
                "Lower exam priority with no student performance data; "
                "review concepts during comprehensive syllabus coverage."
            )

    # --- CASES 2, 3, 4: VERY HIGH / HIGH PRIORITY ---
    elif is_high_priority:
        if safe_mastery < 0.50:
            # Case 2: High priority + weak
            action = RecommendationAction.PRACTICE
            action_priority = 1
            reason = "High exam relevance combined with low demonstrated mastery."
        elif safe_mastery < 0.75:
            # Case 3: High priority + moderate
            action = RecommendationAction.QUIZ
            action_priority = 2
            reason = (
                "High exam relevance with partial mastery; "
                "validate understanding with another practice quiz."
            )
        else:
            # Case 4: High priority + strong
            action = RecommendationAction.MAINTAIN
            action_priority = 7
            reason = (
                "High exam relevance but strong demonstrated mastery; "
                "maintain with periodic revision."
            )

    # --- CASE 5: MEDIUM PRIORITY ---
    elif priority_label == "Medium":
        if safe_mastery < 0.50:
            action = RecommendationAction.PRACTICE
            action_priority = 4
            reason = (
                "Moderate exam relevance with demonstrated weakness; "
                "practice key questions to build mastery."
            )
        elif safe_mastery < 0.75:
            action = RecommendationAction.REVIEW
            action_priority = 6
            reason = (
                "Moderate exam relevance with partial mastery; "
                "review core principles to solidify understanding."
            )
        else:
            action = RecommendationAction.MAINTAIN
            action_priority = 7
            reason = (
                "Moderate exam relevance with solid mastery; "
                "maintain with periodic revision."
            )

    # --- CASE 6: LOW PRIORITY ---
    else:
        if safe_mastery < 0.50:
            action = RecommendationAction.REVIEW
            action_priority = 6
            reason = (
                "Demonstrated weakness exists, but the topic has lower exam priority; "
                "defer until higher-impact topics are addressed."
            )
        else:
            action = RecommendationAction.MAINTAIN
            action_priority = 7
            reason = "Lower exam priority with satisfactory mastery; maintain readiness."

    return TopicRecommendation(
        topic_id=topic_id,
        canonical_label=canonical_label,
        unit_tag=unit_tag,
        priority_score=priority_score,
        priority_label=priority_label,
        student_mastery=safe_mastery,
        weakness_score=safe_weakness,
        evaluation_count=eval_count,
        recommended_action=action,
        recommendation_reason=reason,
        action_priority=action_priority,
        total_occurrences=total_occurrences,
    )


def sort_recommendations(
    recommendations: Sequence[TopicRecommendation],
) -> list[TopicRecommendation]:
    """
    Deterministically sorts recommendations using action priority tiers:
    1. action_priority ascending (1: High Practice -> 2: High Quiz -> 3: High Assess -> 4: Med Practice -> 5: Med Assess -> 6: Review -> 7: Maintain)
    2. priority_score descending (higher exam priority first)
    3. total_occurrences descending (more frequent PYQs first)
    4. canonical_label ascending (alphabetical tie-breaker)
    """
    sorted_items = list(recommendations)
    sorted_items.sort(
        key=lambda item: (
            item.action_priority,
            -item.priority_score,
            -item.total_occurrences,
            str(item.canonical_label).lower(),
        )
    )
    return sorted_items


class RecommendationService:
    """
    Service orchestrating evidence-based, deterministic recommendations for students.
    Consumes already-computed Exam Priority and verified Student Topic Mastery.
    """

    async def get_subject_recommendations(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        subject_id: uuid.UUID,
    ) -> SubjectRecommendationsOut:
        """
        Derives personalized, deterministic recommendations for all canonical topics in a subject.
        """
        # 1. Reuse existing Exam Intelligence calculations
        report = await analytics_service.get_exam_priority_report(
            db=db,
            user_id=user_id,
            subject_id=subject_id,
        )

        # 2. Derive recommendations purely without LLM or database mutations
        raw_recommendations = [
            derive_topic_recommendation(topic) for topic in report.topics
        ]

        # 3. Deterministic sort
        sorted_recommendations = sort_recommendations(raw_recommendations)

        # 4. Assemble response models
        recommendation_outs = [
            TopicRecommendationOut(
                topic_id=rec.topic_id,
                canonical_label=rec.canonical_label,
                unit_tag=rec.unit_tag,
                priority_score=rec.priority_score,
                priority_label=rec.priority_label,
                student_mastery=rec.student_mastery,
                weakness_score=rec.weakness_score,
                evaluation_count=rec.evaluation_count,
                recommended_action=rec.recommended_action,
                recommendation_reason=rec.recommendation_reason,
                action_priority=rec.action_priority,
                action_endpoint=f"/api/v1/analytics/subjects/{subject_id}/topics/{rec.topic_id}/action",
            )
            for rec in sorted_recommendations
        ]

        return SubjectRecommendationsOut(
            subject_id=subject_id,
            has_student_data=report.has_student_data,
            total_recommendations=len(recommendation_outs),
            recommendations=recommendation_outs,
        )

    async def execute_topic_action(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        subject_id: uuid.UUID,
        topic_id: uuid.UUID,
    ) -> TopicActionResponse:
        """
        Executes the personalized learning action for a canonical topic.
        Maintains student isolation and uses existing project infrastructure:
        - PRACTICE: returns topic-linked questions with marks & evaluation submission endpoint.
        - QUIZ: generates and saves a topic quiz worksheet via quiz_service.
        - ASSESS: generates a diagnostic baseline assessment quiz via quiz_service.
        - REVIEW: retrieves syllabus notes and grounded document chunks via hybrid_searcher.
        - MAINTAIN: provides key takeaways, high-yield revision notes, and a refresher question.
        """
        # 1. Verify CanonicalTopic exists and belongs to subject_id
        canonical_topic = await db.get(CanonicalTopic, topic_id)
        if not canonical_topic or canonical_topic.subject_id != subject_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="The referenced Canonical Topic ID does not exist for this course subject.",
            )

        # 2. Get user's current Exam Priority report to deterministically resolve recommendation
        report = await analytics_service.get_exam_priority_report(
            db=db,
            user_id=user_id,
            subject_id=subject_id,
        )

        matching_topic = next((t for t in report.topics if t.topic_id == topic_id), None)
        if matching_topic:
            rec = derive_topic_recommendation(matching_topic)
        else:
            rec = derive_topic_recommendation(canonical_topic)

        # 3. Action-specific execution
        practice_data: Optional[list[PracticeResourceOut]] = None
        quiz_data: Optional[QuizActionOut] = None
        review_data: Optional[ReviewActionOut] = None
        maintain_data: Optional[MaintainActionOut] = None
        action_reason = rec.recommendation_reason

        if rec.recommended_action == RecommendationAction.PRACTICE:
            questions, scope = await self._get_topic_practice_questions(db, subject_id, canonical_topic)
            if questions:
                practice_data = [
                    PracticeResourceOut(
                        question_id=q.id,
                        text=q.text,
                        marks_weight=q.marks_weight,
                        unit_tag=q.unit_tag,
                        source_scope=scope,
                        submission_endpoint="/api/v1/evaluations/",
                    )
                    for q in questions
                ]
            else:
                practice_data = []
                action_reason = (
                    f"{rec.recommendation_reason} "
                    f"(No practice questions are currently available for this topic in the repository.)"
                )

        elif rec.recommended_action in (RecommendationAction.QUIZ, RecommendationAction.ASSESS):
            title_prefix = "Topic Quiz" if rec.recommended_action == RecommendationAction.QUIZ else "Diagnostic Assessment"
            quiz = await quiz_service.generate_quiz(
                db=db,
                subject_id=subject_id,
                title=f"{title_prefix}: {canonical_topic.canonical_label}",
                quiz_type="MCQ",
                unit_tag=canonical_topic.unit_tag,
                topic_id=canonical_topic.id,
            )
            # Sanitize questions data to prevent exposing correct answers
            sanitized_questions = []
            for q in quiz.questions_data.get("questions", []):
                q_copy = copy.deepcopy(q)
                q_copy.pop("correct_answer", None)
                q_copy.pop("explanation", None)
                q_copy.pop("ideal_keywords", None)
                sanitized_questions.append(q_copy)

            quiz_data = QuizActionOut(
                quiz_id=quiz.id,
                title=quiz.title,
                quiz_type=quiz.quiz_type,
                total_questions=len(sanitized_questions),
                questions=sanitized_questions,
                submission_endpoint=f"/api/v1/quizzes/{quiz.id}/submit",
            )

        elif rec.recommended_action == RecommendationAction.REVIEW:
            chunks = await self._get_review_chunks(db, subject_id, canonical_topic)
            if chunks:
                summary = (
                    f"Retrieved {len(chunks)} grounded study context chunks for topic "
                    f"'{canonical_topic.canonical_label}' from subject study materials."
                )
            else:
                summary = (
                    f"No uploaded document chunks found matching topic '{canonical_topic.canonical_label}' in this subject."
                )
            review_data = ReviewActionOut(
                summary=summary,
                key_concepts=[],
                supporting_chunks=chunks,
            )

        elif rec.recommended_action == RecommendationAction.MAINTAIN:
            questions, scope = await self._get_topic_practice_questions(db, subject_id, canonical_topic)
            sample_q = (
                PracticeResourceOut(
                    question_id=questions[0].id,
                    text=questions[0].text,
                    marks_weight=questions[0].marks_weight,
                    unit_tag=questions[0].unit_tag,
                    source_scope=scope,
                    submission_endpoint="/api/v1/evaluations/",
                )
                if questions
                else None
            )
            mastery_pct = round(rec.student_mastery * 100) if rec.student_mastery is not None else 100
            maintain_data = MaintainActionOut(
                key_takeaways=[
                    f"Demonstrated mastery on '{canonical_topic.canonical_label}' is {mastery_pct}%.",
                    "Maintain current proficiency through periodic review intervals.",
                ],
                quick_revision_notes=[
                    f"Topic: {canonical_topic.canonical_label}",
                    f"Unit: {canonical_topic.unit_tag or 'Unassigned'}",
                    "Status: Retain readiness; focus intensive practice on lower-mastery topics.",
                ],
                sample_question=sample_q,
            )

        return TopicActionResponse(
            subject_id=subject_id,
            topic_id=topic_id,
            canonical_label=canonical_topic.canonical_label,
            unit_tag=canonical_topic.unit_tag,
            action=rec.recommended_action,
            action_priority=rec.action_priority,
            reason=action_reason,
            practice_data=practice_data,
            quiz_data=quiz_data,
            review_data=review_data,
            maintain_data=maintain_data,
        )

    async def _get_topic_practice_questions(
        self,
        db: AsyncSession,
        subject_id: uuid.UUID,
        topic: CanonicalTopic,
    ) -> tuple[list[Question], str]:
        """
        Retrieves real practice questions linked to this canonical topic.
        - First checks topic-linked questions (scope="topic").
        - If none, checks unit-level questions (scope="unit").
        - If none, returns ([], "none"). Never creates or persists synthetic questions.
        """
        stmt = (
            select(Question)
            .outerjoin(
                QuestionVariant,
                QuestionVariant.legacy_question_id == Question.id,
            )
            .where(
                Question.subject_id == subject_id,
                or_(
                    QuestionVariant.topic_id == topic.id,
                    Question.id == topic.compatibility_question_id,
                ),
            )
            .order_by(Question.occurrences.desc())
        )
        res = await db.execute(stmt)
        questions = list(res.scalars().unique().all())

        if questions:
            return questions, "topic"

        if topic.unit_tag:
            stmt_unit = (
                select(Question)
                .where(
                    Question.subject_id == subject_id,
                    Question.unit_tag == topic.unit_tag,
                )
                .order_by(Question.occurrences.desc())
            )
            res_unit = await db.execute(stmt_unit)
            unit_questions = list(res_unit.scalars().all())
            if unit_questions:
                return unit_questions, "unit"

        return [], "none"

    async def _get_review_chunks(
        self,
        db: AsyncSession,
        subject_id: uuid.UUID,
        topic: CanonicalTopic,
    ) -> list[ReviewChunkOut]:
        """
        Retrieves grounded notes and study chunks for topic review.
        """
        raw_chunks = await hybrid_searcher.sparse_search(
            db=db,
            query=topic.canonical_label,
            subject_id=subject_id,
            unit_tag=topic.unit_tag,
            limit=4,
        )
        review_chunks: list[ReviewChunkOut] = []
        for c in raw_chunks:
            meta = c.get("metadata", {})
            doc_cat = c.get("category", "study")
            review_chunks.append(
                ReviewChunkOut(
                    chunk_id=str(c.get("chunk_id", "")),
                    document_name=f"{doc_cat.capitalize()} Notes",
                    page=meta.get("page") if isinstance(meta, dict) else 1,
                    content=c.get("content", ""),
                    unit_tag=c.get("unit_tag") or topic.unit_tag,
                )
            )
        return review_chunks


# Singleton recommendation service instance
recommendation_service = RecommendationService()
