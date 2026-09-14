import math
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence


@dataclass(frozen=True)
class TopicMetricsInput:
    """Pure domain input representing aggregated topic metrics for exam focus analysis."""

    topic_id: Any
    canonical_label: str
    unit_tag: Optional[str] = None
    total_occurrences: int = 0
    distinct_papers: int = 0
    avg_marks: float = 0.0
    max_marks: int = 0
    normalized_label: Optional[str] = None


@dataclass(frozen=True)
class StudentTopicMasteryInput:
    """Optional verified student evaluation metrics for a specific canonical topic."""

    evaluation_count: int = 0
    mastery: Optional[float] = None


@dataclass(frozen=True)
class TopicEvidence:
    """Deterministic, explainable rationale and action recommendations."""

    frequency_rationale: str
    marks_rationale: str
    mastery_rationale: str
    recommendation: str


@dataclass(frozen=True)
class ExamPriorityTopic:
    """Calculated evidence-based exam priority record for a topic."""

    topic_id: Any
    canonical_label: str
    unit_tag: Optional[str]
    total_occurrences: int
    distinct_papers: int
    avg_marks: float
    max_marks: int
    frequency_score: float
    marks_score: float
    student_mastery: Optional[float]
    weakness_score: Optional[float]
    priority_score: float
    priority_label: str
    evaluation_count: int
    evidence: TopicEvidence

    @property
    def frequency_rationale(self) -> str:
        return self.evidence.frequency_rationale

    @property
    def marks_rationale(self) -> str:
        return self.evidence.marks_rationale

    @property
    def mastery_rationale(self) -> str:
        return self.evidence.mastery_rationale

    @property
    def recommendation(self) -> str:
        return self.evidence.recommendation


def _safe_finite_float(val: Any, default: float = 0.0) -> float:
    try:
        if val is None:
            return default
        f = float(val)
        return f if math.isfinite(f) else default
    except (TypeError, ValueError, OverflowError):
        return default


def _safe_finite_int(val: Any, default: int = 0) -> int:
    try:
        if val is None:
            return default
        f = float(val)
        return int(f) if math.isfinite(f) else default
    except (TypeError, ValueError, OverflowError):
        return default


class ExamIntelligenceService:
    """
    Pure domain engine for calculating evidence-based Exam Priority.

    Calculates:
    1. Frequency score (normalized PYQ occurrences across the subject)
    2. Marks score (normalized average exam weight across the subject)
    3. Weakness score (1.0 - clamped student mastery, when evaluated answers exist)

    Does NOT predict exam appearances or compute probabilities.
    Does NOT access databases, HTTP, or LLM services.
    """

    def calculate_topic_priorities(
        self,
        topics: Sequence[Any],
        student_mastery: Optional[Mapping[Any, Any]] = None,
    ) -> list[ExamPriorityTopic]:
        """
        Calculates deterministic exam priority scores for a sequence of topics.

        Args:
            topics: Collection of topic metric records (TopicMetricsInput or TopicAggregate).
            student_mastery: Optional mapping from topic_id to student performance metrics.

        Returns:
            List of ExamPriorityTopic records sorted by:
            1. priority_score descending
            2. total_occurrences descending
            3. canonical_label ascending
        """
        if not topics:
            return []

        # 1. Subject-level normalization denominators (guard against non-finite values)
        max_occurrences = max(
            (_safe_finite_int(getattr(t, "total_occurrences", 0), 0) for t in topics),
            default=0,
        )
        max_occurrences = max(0, max_occurrences)

        max_avg_marks = max(
            (_safe_finite_float(getattr(t, "avg_marks", 0.0), 0.0) for t in topics),
            default=0.0,
        )
        max_avg_marks = max(0.0, max_avg_marks)

        scored_topics: list[ExamPriorityTopic] = []

        for topic in topics:
            topic_id = getattr(topic, "topic_id")
            canonical_label = str(getattr(topic, "canonical_label", "") or "")
            unit_tag = getattr(topic, "unit_tag", None)
            total_occ = max(0, _safe_finite_int(getattr(topic, "total_occurrences", 0), 0))
            distinct_papers = max(0, _safe_finite_int(getattr(topic, "distinct_papers", 0), 0))
            avg_marks = max(0.0, _safe_finite_float(getattr(topic, "avg_marks", 0.0), 0.0))
            max_marks = max(0, _safe_finite_int(getattr(topic, "max_marks", 0), 0))

            # 2. Normalize frequency signal
            if max_occurrences > 0:
                f_t = total_occ / max_occurrences
            else:
                f_t = 0.0

            # 3. Normalize marks signal
            if max_avg_marks > 0.0:
                m_t = avg_marks / max_avg_marks
            else:
                m_t = 0.0

            # 4. Resolve optional student performance
            eval_count = 0
            raw_mastery: Optional[float] = None

            if student_mastery and topic_id in student_mastery:
                perf = student_mastery[topic_id]
                if isinstance(perf, (int, float)):
                    m_val = _safe_finite_float(perf, default=float("nan"))
                    if math.isfinite(m_val):
                        raw_mastery = m_val
                        eval_count = 1
                elif isinstance(perf, tuple) and len(perf) >= 2:
                    c = _safe_finite_int(perf[0], 0)
                    m_val = (
                        _safe_finite_float(perf[1], default=float("nan"))
                        if perf[1] is not None
                        else float("nan")
                    )
                    if math.isfinite(m_val):
                        raw_mastery = m_val
                        eval_count = max(0, c)
                elif isinstance(perf, dict):
                    c = _safe_finite_int(perf.get("evaluation_count", 0), 0)
                    m_raw = perf.get("mastery")
                    m_val = (
                        _safe_finite_float(m_raw, default=float("nan"))
                        if m_raw is not None
                        else float("nan")
                    )
                    if math.isfinite(m_val):
                        raw_mastery = m_val
                        eval_count = max(0, c)
                else:
                    c = _safe_finite_int(getattr(perf, "evaluation_count", 0), 0)
                    m_raw = getattr(perf, "mastery", None)
                    m_val = (
                        _safe_finite_float(m_raw, default=float("nan"))
                        if m_raw is not None
                        else float("nan")
                    )
                    if math.isfinite(m_val):
                        raw_mastery = m_val
                        eval_count = max(0, c)

            # 5. Handle student mastery clamping and weakness calculation
            # Treat non-finite values (NaN, +inf, -inf) as unavailable rather than clamping
            if raw_mastery is not None and math.isfinite(raw_mastery):
                clamped_mastery = max(0.0, min(1.0, raw_mastery))
                w_t = 1.0 - clamped_mastery
                has_student_data = True
                mastery_out = round(clamped_mastery, 3)
                weakness_out = round(w_t, 3)
            else:
                clamped_mastery = None
                w_t = None
                has_student_data = False
                mastery_out = None
                weakness_out = None
                eval_count = 0

            # 6. Priority Calculation Modes
            if total_occ == 0:
                # Mode C — No PYQ history
                # Zero-PYQ topics cannot receive high priority merely due to weakness
                if has_student_data and w_t is not None:
                    raw_priority = 0.30 * w_t
                else:
                    raw_priority = 0.0
            elif has_student_data and w_t is not None:
                # Mode A — PYQ frequency + marks + student weakness
                raw_priority = (0.40 * f_t) + (0.30 * m_t) + (0.30 * w_t)
            else:
                # Mode B — PYQ frequency + marks only (no student performance data)
                raw_priority = (0.60 * f_t) + (0.40 * m_t)

            # Ensure safe numerical bounds [0.0, 1.0] and round final priority to 3 decimal places
            priority_score = round(max(0.0, min(1.0, raw_priority)), 3)

            # 7. Exact deterministic priority labels
            if priority_score >= 0.75:
                priority_label = "Very High"
            elif priority_score >= 0.55:
                priority_label = "High"
            elif priority_score >= 0.35:
                priority_label = "Medium"
            else:
                priority_label = "Low"

            # 8. Deterministic explainable evidence & recommendation
            evidence = self._generate_evidence(
                total_occurrences=total_occ,
                distinct_papers=distinct_papers,
                avg_marks=avg_marks,
                has_student_data=has_student_data,
                clamped_mastery=clamped_mastery,
                evaluation_count=eval_count,
                f_t=f_t,
            )

            scored_topics.append(
                ExamPriorityTopic(
                    topic_id=topic_id,
                    canonical_label=canonical_label,
                    unit_tag=unit_tag,
                    total_occurrences=total_occ,
                    distinct_papers=distinct_papers,
                    avg_marks=round(avg_marks, 2),
                    max_marks=max_marks,
                    frequency_score=round(f_t, 3),
                    marks_score=round(m_t, 3),
                    student_mastery=mastery_out,
                    weakness_score=weakness_out,
                    priority_score=priority_score,
                    priority_label=priority_label,
                    evaluation_count=eval_count,
                    evidence=evidence,
                )
            )

        # 9. Deterministic sorting:
        # - priority_score descending
        # - total_occurrences descending
        # - canonical_label ascending
        scored_topics.sort(
            key=lambda item: (-item.priority_score, -item.total_occurrences, item.canonical_label)
        )

        return scored_topics

    def _generate_evidence(
        self,
        total_occurrences: int,
        distinct_papers: int,
        avg_marks: float,
        has_student_data: bool,
        clamped_mastery: Optional[float],
        evaluation_count: int,
        f_t: float,
    ) -> TopicEvidence:
        # Frequency rationale
        if total_occurrences == 0:
            frequency_rationale = (
                "No previous-year question occurrence is currently recorded for this topic."
            )
        else:
            time_str = "time" if total_occurrences == 1 else "times"
            paper_str = "examination paper" if distinct_papers == 1 else "examination papers"
            frequency_rationale = (
                f"Appeared {total_occurrences} {time_str} across {distinct_papers} {paper_str}."
            )

        # Marks rationale
        if total_occurrences == 0:
            marks_rationale = "No previous-year exam marks history exists for this topic."
        else:
            marks_rationale = f"Average exam weight is {round(avg_marks, 1)} marks."

        # Mastery rationale
        if not has_student_data or clamped_mastery is None:
            mastery_rationale = (
                "Student mastery is unavailable because no evaluated answers exist for this topic."
            )
        else:
            ans_str = "evaluated answer" if evaluation_count == 1 else "evaluated answers"
            pct = round(clamped_mastery * 100)
            mastery_rationale = (
                f"Student mastery is {pct}% based on {evaluation_count} {ans_str}."
            )

        # Deterministic recommendation
        if total_occurrences == 0:
            recommendation = (
                "Treat this as syllabus study rather than PYQ-driven exam priority."
            )
        elif f_t >= 0.5:
            if has_student_data and clamped_mastery is not None:
                if (1.0 - clamped_mastery) >= 0.4:
                    recommendation = (
                        "Prioritize revision of this topic because it is frequently tested and "
                        "current mastery is low."
                    )
                else:
                    recommendation = (
                        "Maintain mastery of this high-frequency topic with periodic revision."
                    )
            else:
                recommendation = (
                    "Prioritize this topic based on its strong previous-year exam history."
                )
        else:
            if has_student_data and clamped_mastery is not None:
                if (1.0 - clamped_mastery) >= 0.4:
                    recommendation = "Review this topic after higher-impact PYQ topics."
                else:
                    recommendation = (
                        "Current mastery is adequate; focus on higher-frequency exam topics."
                    )
            else:
                recommendation = (
                    "Study this topic after covering higher-priority exam questions."
                )

        return TopicEvidence(
            frequency_rationale=frequency_rationale,
            marks_rationale=marks_rationale,
            mastery_rationale=mastery_rationale,
            recommendation=recommendation,
        )


# Singleton engine instance
exam_intelligence_service = ExamIntelligenceService()
