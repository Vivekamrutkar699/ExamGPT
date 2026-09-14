import math
import uuid
from dataclasses import dataclass
from typing import Optional, Sequence, List

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.topic_performance import (
    StudentTopicPerformanceOut,
    SubjectTopicPerformanceOut,
)


@dataclass(frozen=True)
class StudentTopicPerformance:
    """
    Explicit domain representation of a student's performance and mastery on a topic.
    """
    student_id: uuid.UUID
    subject_id: uuid.UUID
    topic_id: uuid.UUID
    canonical_label: str
    unit_tag: Optional[str]
    evaluation_count: int
    mastery: Optional[float]
    weakness: Optional[float]
    has_student_data: bool


def calculate_score_ratio(estimated_marks: float, max_marks: float) -> Optional[float]:
    """
    Deterministically computes and clamps the performance ratio for a single attempt.

    Rules:
    - max_marks must be finite and > 0.0
    - estimated_marks must be finite
    - clamped to [0.0, 1.0] (e.g. negative marks -> 0.0, marks > max_marks -> 1.0)
    - returns None if marks are invalid or non-positive max_marks
    """
    try:
        if not math.isfinite(max_marks) or max_marks <= 0.0:
            return None
        if not math.isfinite(estimated_marks):
            return None
        raw_ratio = estimated_marks / max_marks
        return max(0.0, min(1.0, float(raw_ratio)))
    except (TypeError, ValueError, ZeroDivisionError, OverflowError):
        return None


def calculate_topic_mastery(attempt_ratios: Sequence[float]) -> Optional[float]:
    """
    Calculates deterministic topic mastery from a sequence of attempt ratios.

    Rules:
    - Empty sequence -> None (distinguishes no-data from 0.0 mastery)
    - Filters out any non-finite values
    - Clamps each ratio to [0.0, 1.0]
    - Computes arithmetic mean across attempts
    - Rounded to 4 decimal places
    """
    if not attempt_ratios:
        return None
    valid = [r for r in attempt_ratios if r is not None and math.isfinite(r)]
    if not valid:
        return None
    clamped = [max(0.0, min(1.0, float(r))) for r in valid]
    return round(sum(clamped) / len(clamped), 4)


def calculate_topic_weakness(mastery: Optional[float]) -> Optional[float]:
    """
    Calculates student weakness from mastery.

    Rules:
    - If mastery is None -> None (no data -> no weakness)
    - If mastery is finite -> round(1.0 - clamped_mastery, 4)
    """
    if mastery is None or not math.isfinite(mastery):
        return None
    clamped = max(0.0, min(1.0, float(mastery)))
    return round(1.0 - clamped, 4)


class StudentPerformanceService:
    """
    Assembles topic-level student performance and mastery across canonical topics.
    """

    async def get_subject_topic_performance(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        subject_id: uuid.UUID,
    ) -> SubjectTopicPerformanceOut:
        """
        Retrieves all canonical topics for a subject along with the student's
        evaluated attempts, producing an explicit topic performance breakdown.
        """
        from app.repositories.topic_mastery import topic_mastery_repository

        # 1. Fetch raw evaluation records and canonical topics (efficient queries, no N+1)
        topic_records, raw_attempts_by_topic, unresolved_count = (
            await topic_mastery_repository.get_topic_performance_raw_data(
                db=db,
                user_id=user_id,
                subject_id=subject_id,
            )
        )

        topic_outputs: List[StudentTopicPerformanceOut] = []
        evaluated_topics_count = 0

        for topic in topic_records:
            topic_id = topic.id
            attempts = raw_attempts_by_topic.get(topic_id, [])

            if attempts:
                mastery = calculate_topic_mastery(attempts)
                weakness = calculate_topic_weakness(mastery)
                eval_count = len(attempts)
                has_data = True
                evaluated_topics_count += 1
            else:
                mastery = None
                weakness = None
                eval_count = 0
                has_data = False

            topic_outputs.append(
                StudentTopicPerformanceOut(
                    student_id=user_id,
                    subject_id=subject_id,
                    topic_id=topic_id,
                    canonical_label=topic.canonical_label,
                    unit_tag=topic.unit_tag,
                    evaluation_count=eval_count,
                    mastery=mastery,
                    weakness=weakness,
                    has_student_data=has_data,
                )
            )

        has_any_data = evaluated_topics_count > 0 or unresolved_count > 0

        return SubjectTopicPerformanceOut(
            subject_id=subject_id,
            student_id=user_id,
            total_topics=len(topic_records),
            evaluated_topics_count=evaluated_topics_count,
            unresolved_evaluations_count=unresolved_count,
            has_student_data=has_any_data,
            topics=topic_outputs,
        )


student_performance_service = StudentPerformanceService()
