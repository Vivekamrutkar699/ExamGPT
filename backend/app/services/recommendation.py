import math
import uuid
from dataclasses import dataclass
from typing import Any, Optional, Sequence
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.recommendation import (
    RecommendationAction,
    TopicRecommendationOut,
    SubjectRecommendationsOut,
)
from app.services.analytics import analytics_service


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
            )
            for rec in sorted_recommendations
        ]

        return SubjectRecommendationsOut(
            subject_id=subject_id,
            has_student_data=report.has_student_data,
            total_recommendations=len(recommendation_outs),
            recommendations=recommendation_outs,
        )


# Singleton recommendation service instance
recommendation_service = RecommendationService()
