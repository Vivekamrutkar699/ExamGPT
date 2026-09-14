import uuid
from typing import List, Dict
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.chunk import Chunk
from app.models.answers_evaluation import AnswersEvaluation
from app.models.question import Question
from app.models.pyq_topic import PYQQuestionOccurrence, QuestionVariant
from app.schemas.analytics import (
    ExamPriorityTopicOut,
    SubjectAnalyticsOut,
    SubjectExamPriorityOut,
    TopicEvidenceOut,
)
from app.repositories.study_plan import study_plan_repository
from app.repositories.evaluation import evaluation_repository
from app.repositories.pyq_topic import pyq_topic_repository
from app.repositories.topic_mastery import topic_mastery_repository
from app.services.exam_intelligence import exam_intelligence_service


class AnalyticsService:
    """
    Assembles metrics across materials databases, schedules checkpoints, 
    and grades logs to flag weak syllabus areas.
    """

    async def get_subject_analytics_report(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        subject_id: uuid.UUID
    ) -> SubjectAnalyticsOut:
        """
        Aggregate and build the performance metrics report card for a student subject.
        """
        # 1. Overall study plan progress rate
        active_plan = await study_plan_repository.get_active_by_user_subject(
            db=db,
            user_id=user_id,
            subject_id=subject_id
        )
        study_progress = 0.0
        if active_plan and isinstance(active_plan.schedule, dict):
            study_progress = float(active_plan.schedule.get("progress_percent", 0.0))

        # 2. Total study materials uploaded and indexed chunks counts
        doc_count_stmt = select(func.count(Document.id)).where(Document.subject_id == subject_id)
        doc_count_res = await db.execute(doc_count_stmt)
        total_materials = doc_count_res.scalar() or 0

        chunk_count_stmt = (
            select(func.count(Chunk.id))
            .join(Document, Chunk.document_id == Document.id)
            .where(Document.subject_id == subject_id)
        )
        chunk_count_res = await db.execute(chunk_count_stmt)
        total_chunks = chunk_count_res.scalar() or 0

        # 3. Retrieve essay answer evaluations histories
        evaluations = await evaluation_repository.list_by_user_subject(
            db=db,
            user_id=user_id,
            subject_id=subject_id
        )
        
        total_essays = len(evaluations)
        essay_avg = 0.0
        
        unit_scores: Dict[str, List[float]] = {}

        if total_essays > 0:
            total_ratio = 0.0
            for ev in evaluations:
                ratio = float(ev.estimated_marks / ev.max_marks) if ev.max_marks > 0 else 0.0
                total_ratio += ratio
                
                # Fetch question unit tag to isolate weak categories
                stmt = select(Question.unit_tag).where(Question.id == ev.question_id)
                res = await db.execute(stmt)
                unit_tag = res.scalar()
                
                if unit_tag:
                    unit_scores.setdefault(unit_tag, []).append(ratio * 100.0)
                    
            essay_avg = round((total_ratio / total_essays) * 100.0, 1)

        # 4. Mock Quiz database aggregations
        # In a full release, quiz entries are linked to quizzes history records
        # Here we mock quiz history metrics
        total_quizzes = 1 if total_essays > 0 else 0
        quiz_avg = 75.0 if total_essays > 0 else 0.0
        
        if total_quizzes > 0:
            unit_scores.setdefault("Unit 1", []).append(75.0)

        # 5. Weak syllabus areas detection
        # Average score under 60% flags a unit as weak
        weak_units = []
        for unit, scores in unit_scores.items():
            avg_unit_score = sum(scores) / len(scores)
            if avg_unit_score < 60.0:
                weak_units.append(unit)

        return SubjectAnalyticsOut(
            subject_id=subject_id,
            study_progress=study_progress,
            total_quizzes_taken=total_quizzes,
            average_quiz_score=quiz_avg,
            total_essays_evaluated=total_essays,
            average_essay_score=essay_avg,
            weak_units=sorted(weak_units),
            total_materials_uploaded=total_materials,
            total_chunks_indexed=total_chunks
        )

    async def get_exam_priority_report(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        subject_id: uuid.UUID,
    ) -> SubjectExamPriorityOut:
        """
        Calculates explainable Exam Priority scores and revision focus across
        canonical topics for a given student and subject.

        Query flow (avoids N+1):
        1. Topic-level PYQ aggregates (pyq_topic_repository)
        2. Student answer evaluation mastery aggregated by topic (topic_mastery_repository)
        3. Count occurrences of unresolved variants
        4. Pure calculation via ExamIntelligenceService
        """
        # 1. Topic-level PYQ aggregates across the subject (Query 1)
        topic_aggregates = await pyq_topic_repository.get_topic_aggregates(db, subject_id)

        # 2. Student evaluation mastery aggregated by canonical topic (Query 2)
        mastery_map = await topic_mastery_repository.get_student_topic_mastery(
            db, user_id=user_id, subject_id=subject_id
        )

        # 3. Unresolved PYQ occurrences count (Query 3)
        unresolved_stmt = (
            select(func.count(PYQQuestionOccurrence.id))
            .select_from(PYQQuestionOccurrence)
            .join(QuestionVariant, PYQQuestionOccurrence.variant_id == QuestionVariant.id)
            .where(
                QuestionVariant.subject_id == subject_id,
                QuestionVariant.topic_id.is_(None),
            )
        )
        unresolved_count_res = await db.execute(unresolved_stmt)
        unresolved_count = unresolved_count_res.scalar() or 0

        # 4. Pure calculation engine
        prioritized_topics = exam_intelligence_service.calculate_topic_priorities(
            topics=topic_aggregates,
            student_mastery=mastery_map,
        )

        has_any_student_data = len(mastery_map) > 0

        topic_outs: list[ExamPriorityTopicOut] = []
        for item in prioritized_topics:
            topic_outs.append(
                ExamPriorityTopicOut(
                    topic_id=item.topic_id,
                    canonical_label=item.canonical_label,
                    unit_tag=item.unit_tag,
                    total_occurrences=item.total_occurrences,
                    distinct_papers=item.distinct_papers,
                    avg_marks=item.avg_marks,
                    max_marks=item.max_marks,
                    frequency_score=item.frequency_score,
                    marks_score=item.marks_score,
                    student_mastery=item.student_mastery,
                    weakness_score=item.weakness_score,
                    priority_score=item.priority_score,
                    priority_label=item.priority_label,
                    evaluation_count=item.evaluation_count,
                    has_student_data=(item.student_mastery is not None),
                    evidence=TopicEvidenceOut(
                        frequency_rationale=item.evidence.frequency_rationale,
                        marks_rationale=item.evidence.marks_rationale,
                        mastery_rationale=item.evidence.mastery_rationale,
                        recommendation=item.evidence.recommendation,
                    ),
                    recommendation=item.recommendation,
                )
            )

        return SubjectExamPriorityOut(
            subject_id=subject_id,
            has_student_data=has_any_student_data,
            total_topics=len(topic_outs),
            unresolved_occurrences_count=unresolved_count,
            topics=topic_outs,
        )


# Singleton service instance
analytics_service = AnalyticsService()
