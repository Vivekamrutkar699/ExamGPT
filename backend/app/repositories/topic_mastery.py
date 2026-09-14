import math
import uuid

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.answers_evaluation import AnswersEvaluation
from app.models.pyq_topic import CanonicalTopic, QuestionVariant
from app.models.question import Question
from app.services.exam_intelligence import StudentTopicMasteryInput


class TopicMasteryRepository:
    """
    Aggregates student answer evaluations mapped to canonical topics.
    Safely resolves AnswersEvaluation.question_id to CanonicalTopic via:
    1. QuestionVariant.legacy_question_id (for resolved variants where topic_id is set)
    2. CanonicalTopic.compatibility_question_id (legacy compatibility bridge)
    """

    async def get_student_topic_mastery(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        subject_id: uuid.UUID,
    ) -> dict[uuid.UUID, StudentTopicMasteryInput]:
        """
        Retrieves all valid answer evaluations by user_id for subject_id,
        maps each evaluation to its CanonicalTopic, and computes the arithmetic mean
        of clamped individual mastery ratios [0, 1].

        Evaluations that cannot be safely mapped to a CanonicalTopic or have
        invalid/non-positive max_marks are excluded.
        """
        stmt = (
            select(
                AnswersEvaluation.id.label("evaluation_id"),
                func.coalesce(QuestionVariant.topic_id, CanonicalTopic.id).label("topic_id"),
                AnswersEvaluation.estimated_marks,
                AnswersEvaluation.max_marks,
            )
            .select_from(AnswersEvaluation)
            .join(Question, AnswersEvaluation.question_id == Question.id)
            .outerjoin(
                QuestionVariant,
                and_(
                    QuestionVariant.legacy_question_id == Question.id,
                    QuestionVariant.subject_id == subject_id,
                    QuestionVariant.topic_id.is_not(None),
                ),
            )
            .outerjoin(
                CanonicalTopic,
                and_(
                    CanonicalTopic.compatibility_question_id == Question.id,
                    CanonicalTopic.subject_id == subject_id,
                ),
            )
            .where(
                AnswersEvaluation.user_id == user_id,
                Question.subject_id == subject_id,
                AnswersEvaluation.max_marks > 0,
                AnswersEvaluation.estimated_marks.is_not(None),
                or_(
                    QuestionVariant.topic_id.is_not(None),
                    CanonicalTopic.id.is_not(None),
                ),
            )
        )

        result = await db.execute(stmt)
        rows = result.all()

        topic_ratios: dict[uuid.UUID, list[float]] = {}
        seen_eval_ids: set[uuid.UUID] = set()

        for row in rows:
            eval_id = row.evaluation_id
            if eval_id in seen_eval_ids:
                continue
            seen_eval_ids.add(eval_id)

            target_topic_id = row.topic_id
            if not target_topic_id:
                continue

            max_m = float(row.max_marks or 0.0)
            est_m = float(row.estimated_marks or 0.0)

            if not math.isfinite(max_m) or max_m <= 0.0:
                continue
            if not math.isfinite(est_m):
                continue

            clamped_ratio = max(0.0, min(1.0, est_m / max_m))
            topic_ratios.setdefault(target_topic_id, []).append(clamped_ratio)

        mastery_by_topic: dict[uuid.UUID, StudentTopicMasteryInput] = {}
        for topic_id, ratios in topic_ratios.items():
            if not ratios:
                continue
            mean_mastery = sum(ratios) / len(ratios)
            mastery_by_topic[topic_id] = StudentTopicMasteryInput(
                evaluation_count=len(ratios),
                mastery=mean_mastery,
            )

        return mastery_by_topic

    async def get_topic_performance_raw_data(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        subject_id: uuid.UUID,
    ) -> tuple[list[CanonicalTopic], dict[uuid.UUID, list[float]], int]:
        """
        Retrieves:
        1. All CanonicalTopics for the subject (ordered by canonical_label)
        2. Clamped score ratios for all valid evaluations by the student mapped to their CanonicalTopic
        3. Count of unresolved evaluations (evaluations whose questions cannot be linked to any CanonicalTopic)
        """
        # 1. Fetch all canonical topics for the subject
        topics_stmt = (
            select(CanonicalTopic)
            .where(CanonicalTopic.subject_id == subject_id)
            .order_by(CanonicalTopic.canonical_label.asc())
        )
        topics_res = await db.execute(topics_stmt)
        topics = list(topics_res.scalars().all())

        # 2. Fetch all valid evaluated attempts mapped to CanonicalTopic
        stmt = (
            select(
                AnswersEvaluation.id.label("evaluation_id"),
                func.coalesce(QuestionVariant.topic_id, CanonicalTopic.id).label("topic_id"),
                AnswersEvaluation.estimated_marks,
                AnswersEvaluation.max_marks,
            )
            .select_from(AnswersEvaluation)
            .join(Question, AnswersEvaluation.question_id == Question.id)
            .outerjoin(
                QuestionVariant,
                and_(
                    QuestionVariant.legacy_question_id == Question.id,
                    QuestionVariant.subject_id == subject_id,
                    QuestionVariant.topic_id.is_not(None),
                ),
            )
            .outerjoin(
                CanonicalTopic,
                and_(
                    CanonicalTopic.compatibility_question_id == Question.id,
                    CanonicalTopic.subject_id == subject_id,
                ),
            )
            .where(
                AnswersEvaluation.user_id == user_id,
                Question.subject_id == subject_id,
                AnswersEvaluation.max_marks > 0,
                AnswersEvaluation.estimated_marks.is_not(None),
                or_(
                    QuestionVariant.topic_id.is_not(None),
                    CanonicalTopic.id.is_not(None),
                ),
            )
        )
        result = await db.execute(stmt)
        rows = result.all()

        topic_ratios: dict[uuid.UUID, list[float]] = {}
        seen_eval_ids: set[uuid.UUID] = set()

        for row in rows:
            eval_id = row.evaluation_id
            if eval_id in seen_eval_ids:
                continue
            seen_eval_ids.add(eval_id)

            target_topic_id = row.topic_id
            if not target_topic_id:
                continue

            max_m = float(row.max_marks or 0.0)
            est_m = float(row.estimated_marks or 0.0)

            if not math.isfinite(max_m) or max_m <= 0.0:
                continue
            if not math.isfinite(est_m):
                continue

            clamped_ratio = max(0.0, min(1.0, est_m / max_m))
            topic_ratios.setdefault(target_topic_id, []).append(clamped_ratio)

        # 3. Count unresolved evaluations for the student in this subject
        unresolved_stmt = (
            select(func.count(func.distinct(AnswersEvaluation.id)))
            .select_from(AnswersEvaluation)
            .join(Question, AnswersEvaluation.question_id == Question.id)
            .outerjoin(
                QuestionVariant,
                and_(
                    QuestionVariant.legacy_question_id == Question.id,
                    QuestionVariant.subject_id == subject_id,
                    QuestionVariant.topic_id.is_not(None),
                ),
            )
            .outerjoin(
                CanonicalTopic,
                and_(
                    CanonicalTopic.compatibility_question_id == Question.id,
                    CanonicalTopic.subject_id == subject_id,
                ),
            )
            .where(
                AnswersEvaluation.user_id == user_id,
                Question.subject_id == subject_id,
                QuestionVariant.topic_id.is_(None),
                CanonicalTopic.id.is_(None),
            )
        )
        unresolved_res = await db.execute(unresolved_stmt)
        unresolved_count = int(unresolved_res.scalar() or 0)

        return topics, topic_ratios, unresolved_count


topic_mastery_repository = TopicMasteryRepository()
