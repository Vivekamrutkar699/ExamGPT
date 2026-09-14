import asyncio
import sys
import unittest
import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from fastapi import HTTPException
import app.database.base  # noqa: F401
from app.api.v1.endpoints.analytics import get_subject_topic_performance
from app.database.session import SessionLocal
from app.models.answers_evaluation import AnswersEvaluation
from app.models.pyq_topic import (
    CanonicalTopic,
    PYQPaper,
    PYQQuestionOccurrence,
    QuestionVariant,
)
from app.models.question import Question
from app.models.subject import Subject
from app.models.user import User
from app.schemas.topic_performance import (
    StudentTopicPerformanceOut,
    SubjectTopicPerformanceOut,
)
from app.services.student_performance import (
    calculate_score_ratio,
    calculate_topic_mastery,
    calculate_topic_weakness,
    student_performance_service,
)
from app.services.analytics import analytics_service


class StudentTopicPerformanceTests(unittest.TestCase):
    """
    Phase 7A Test Suite: Student Performance / Topic Mastery Foundation.
    Tests cover:
    1. Pure calculation functions (score clamping, arithmetic mean, weakness, no-data None)
    2. Integration repository & service behavior:
       - No student data (mastery = None)
       - Single performance result
       - Multiple attempts arithmetic mean
       - Bounds clamping ([0.0, 1.0])
       - Unresolved topic exclusion & count
       - Multi-student isolation
       - Multi-topic isolation
       - Multi-subject isolation
    3. API endpoint get_subject_topic_performance behavior
    4. Preservation of existing Exam Intelligence behavior
    """

    def setUp(self) -> None:
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self) -> None:
        self.loop.close()

    # -------------------------------------------------------------------------
    # Unit Tests for Pure Calculation Functions
    # -------------------------------------------------------------------------

    def test_pure_calculate_score_ratio_bounds_and_safety(self) -> None:
        """Verify clamping [0.0, 1.0] and edge cases for single attempt ratio."""
        # Normal valid cases
        self.assertEqual(calculate_score_ratio(5.0, 10.0), 0.5)
        self.assertEqual(calculate_score_ratio(0.0, 10.0), 0.0)
        self.assertEqual(calculate_score_ratio(10.0, 10.0), 1.0)

        # Clamping lower bound
        self.assertEqual(calculate_score_ratio(-2.0, 10.0), 0.0)

        # Clamping upper bound (e.g. bonus points / erroneous marks)
        self.assertEqual(calculate_score_ratio(12.0, 10.0), 1.0)

        # Invalid/Zero max_marks
        self.assertIsNone(calculate_score_ratio(5.0, 0.0))
        self.assertIsNone(calculate_score_ratio(5.0, -10.0))
        self.assertIsNone(calculate_score_ratio(float("nan"), 10.0))
        self.assertIsNone(calculate_score_ratio(5.0, float("nan")))

    def test_pure_calculate_topic_mastery_arithmetic_mean(self) -> None:
        """Verify arithmetic mean aggregation across multiple attempts and empty case."""
        # No attempts -> None (distinguishing no-data from 0.0)
        self.assertIsNone(calculate_topic_mastery([]))

        # Single attempt
        self.assertEqual(calculate_topic_mastery([0.75]), 0.75)

        # Multiple attempts: 0.40, 0.60, 0.80 -> mean = 0.60
        self.assertEqual(calculate_topic_mastery([0.40, 0.60, 0.80]), 0.60)

        # Multiple attempts with clamping: [-0.1, 0.5, 1.2] -> [0.0, 0.5, 1.0] -> 0.50
        self.assertEqual(calculate_topic_mastery([-0.1, 0.5, 1.2]), 0.50)

    def test_pure_calculate_topic_weakness(self) -> None:
        """Verify weakness = 1.0 - mastery and handling of None."""
        self.assertIsNone(calculate_topic_weakness(None))
        self.assertEqual(calculate_topic_weakness(0.60), 0.40)
        self.assertEqual(calculate_topic_weakness(1.0), 0.0)
        self.assertEqual(calculate_topic_weakness(0.0), 1.0)

    # -------------------------------------------------------------------------
    # Database Integration Tests
    # -------------------------------------------------------------------------

    def test_01_no_student_data_mastery_is_null(self) -> None:
        """Verify that when a student has no evaluations, mastery is null (None), not 0.0."""
        async def _run():
            async with SessionLocal() as db:
                user = User(
                    email=f"stu_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="hashed_password",
                    full_name="No Data Student",
                    role="student",
                )
                subject = Subject(
                    code=f"NODATA-{uuid.uuid4().hex[:4]}",
                    name="No Data Subject",
                    semester=6,
                    branch="Computer Engineering",
                )
                db.add_all([user, subject])
                await db.commit()
                await db.refresh(user)
                await db.refresh(subject)

                t1 = CanonicalTopic(
                    subject_id=subject.id,
                    canonical_label="Virtual Memory",
                    normalized_label="virtual memory",
                    unit_tag="Unit 4",
                )
                db.add(t1)
                await db.commit()

                report = await student_performance_service.get_subject_topic_performance(
                    db=db, user_id=user.id, subject_id=subject.id
                )

                self.assertIsInstance(report, SubjectTopicPerformanceOut)
                self.assertEqual(report.total_topics, 1)
                self.assertEqual(report.evaluated_topics_count, 0)
                self.assertFalse(report.has_student_data)
                self.assertEqual(len(report.topics), 1)

                top = report.topics[0]
                self.assertEqual(top.topic_id, t1.id)
                self.assertEqual(top.canonical_label, "Virtual Memory")
                self.assertEqual(top.evaluation_count, 0)
                self.assertIsNone(top.mastery)
                self.assertIsNone(top.weakness)
                self.assertFalse(top.has_student_data)

        self.loop.run_until_complete(_run())

    def test_02_single_performance_result_matches_normalized_value(self) -> None:
        """Verify single evaluation maps correctly and sets normalized mastery and weakness."""
        async def _run():
            async with SessionLocal() as db:
                user = User(
                    email=f"stu_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="hashed_password",
                    full_name="Single Eval Student",
                    role="student",
                )
                subject = Subject(
                    code=f"SINGLE-{uuid.uuid4().hex[:4]}",
                    name="Single Eval Subject",
                    semester=6,
                    branch="Computer Engineering",
                )
                db.add_all([user, subject])
                await db.commit()
                await db.refresh(user)
                await db.refresh(subject)

                t1 = CanonicalTopic(
                    subject_id=subject.id,
                    canonical_label="CPU Scheduling",
                    normalized_label="cpu scheduling",
                    unit_tag="Unit 2",
                )
                db.add(t1)
                await db.flush()

                q1 = Question(
                    subject_id=subject.id,
                    text="Explain Round Robin Scheduling.",
                    marks_weight=10,
                    unit_tag="Unit 2",
                )
                db.add(q1)
                await db.flush()

                v1 = QuestionVariant(
                    subject_id=subject.id,
                    topic_id=t1.id,
                    legacy_question_id=q1.id,
                    text=q1.text,
                    normalized_text="explain round robin scheduling",
                    normalized_hash=uuid.uuid4().hex,
                    resolution_type="exact_match",
                )
                db.add(v1)
                await db.flush()

                # Score: 7.5 / 10.0 = 0.75
                eval1 = AnswersEvaluation(
                    user_id=user.id,
                    question_id=q1.id,
                    user_submitted_answer="Round Robin uses a time quantum.",
                    feedback="Good explanation.",
                    estimated_marks=7.5,
                    max_marks=10.0,
                )
                db.add(eval1)
                await db.commit()

                report = await student_performance_service.get_subject_topic_performance(
                    db=db, user_id=user.id, subject_id=subject.id
                )

                self.assertTrue(report.has_student_data)
                self.assertEqual(report.evaluated_topics_count, 1)
                self.assertEqual(len(report.topics), 1)

                top = report.topics[0]
                self.assertEqual(top.topic_id, t1.id)
                self.assertEqual(top.evaluation_count, 1)
                self.assertEqual(top.mastery, 0.75)
                self.assertEqual(top.weakness, 0.25)
                self.assertTrue(top.has_student_data)

        self.loop.run_until_complete(_run())

    def test_03_multiple_attempts_arithmetic_mean(self) -> None:
        """Verify multiple attempts on the same topic produce deterministic arithmetic mean."""
        async def _run():
            async with SessionLocal() as db:
                user = User(
                    email=f"stu_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="hashed_password",
                    full_name="Multi Attempt Student",
                    role="student",
                )
                subject = Subject(
                    code=f"MULTI-{uuid.uuid4().hex[:4]}",
                    name="Multi Attempt Subject",
                    semester=6,
                    branch="Computer Engineering",
                )
                db.add_all([user, subject])
                await db.commit()
                await db.refresh(user)
                await db.refresh(subject)

                t1 = CanonicalTopic(
                    subject_id=subject.id,
                    canonical_label="Deadlock Detection",
                    normalized_label="deadlock detection",
                    unit_tag="Unit 3",
                )
                db.add(t1)
                await db.flush()

                q1 = Question(
                    subject_id=subject.id,
                    text="Explain Banker's Algorithm.",
                    marks_weight=10,
                )
                q2 = Question(
                    subject_id=subject.id,
                    text="Describe Resource Allocation Graph.",
                    marks_weight=5,
                )
                db.add_all([q1, q2])
                await db.flush()

                v1 = QuestionVariant(
                    subject_id=subject.id,
                    topic_id=t1.id,
                    legacy_question_id=q1.id,
                    text=q1.text,
                    normalized_text="explain bankers algorithm",
                    normalized_hash=uuid.uuid4().hex,
                )
                v2 = QuestionVariant(
                    subject_id=subject.id,
                    topic_id=t1.id,
                    legacy_question_id=q2.id,
                    text=q2.text,
                    normalized_text="describe resource allocation graph",
                    normalized_hash=uuid.uuid4().hex,
                )
                db.add_all([v1, v2])
                await db.flush()

                # Attempt 1: 4.0 / 10.0 = 0.40
                # Attempt 2: 8.0 / 10.0 = 0.80
                # Attempt 3: 3.0 / 5.0  = 0.60
                # Expected mean = (0.40 + 0.80 + 0.60) / 3 = 0.6000
                e1 = AnswersEvaluation(
                    user_id=user.id, question_id=q1.id, user_submitted_answer="A1",
                    feedback="F1", estimated_marks=4.0, max_marks=10.0,
                )
                e2 = AnswersEvaluation(
                    user_id=user.id, question_id=q1.id, user_submitted_answer="A2",
                    feedback="F2", estimated_marks=8.0, max_marks=10.0,
                )
                e3 = AnswersEvaluation(
                    user_id=user.id, question_id=q2.id, user_submitted_answer="A3",
                    feedback="F3", estimated_marks=3.0, max_marks=5.0,
                )
                db.add_all([e1, e2, e3])
                await db.commit()

                report = await student_performance_service.get_subject_topic_performance(
                    db=db, user_id=user.id, subject_id=subject.id
                )

                self.assertEqual(report.evaluated_topics_count, 1)
                top = report.topics[0]
                self.assertEqual(top.evaluation_count, 3)
                self.assertEqual(top.mastery, 0.6000)
                self.assertEqual(top.weakness, 0.4000)

        self.loop.run_until_complete(_run())

    def test_04_mastery_bounds_cannot_fall_below_zero_or_exceed_one(self) -> None:
        """Verify lower and upper bound clamping [0.0, 1.0]."""
        async def _run():
            async with SessionLocal() as db:
                user = User(
                    email=f"stu_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="hashed_password",
                    full_name="Clamping Student",
                    role="student",
                )
                subject = Subject(
                    code=f"CLAMP-{uuid.uuid4().hex[:4]}",
                    name="Clamping Subject",
                    semester=6,
                    branch="Computer Engineering",
                )
                db.add_all([user, subject])
                await db.commit()
                await db.refresh(user)
                await db.refresh(subject)

                t1 = CanonicalTopic(
                    subject_id=subject.id,
                    canonical_label="Bounds Topic",
                    normalized_label="bounds topic",
                )
                db.add(t1)
                await db.flush()

                q1 = Question(subject_id=subject.id, text="Q1", marks_weight=10)
                q2 = Question(subject_id=subject.id, text="Q2", marks_weight=10)
                db.add_all([q1, q2])
                await db.flush()

                v1 = QuestionVariant(
                    subject_id=subject.id, topic_id=t1.id, legacy_question_id=q1.id,
                    text="Q1", normalized_text="q1", normalized_hash=uuid.uuid4().hex,
                )
                v2 = QuestionVariant(
                    subject_id=subject.id, topic_id=t1.id, legacy_question_id=q2.id,
                    text="Q2", normalized_text="q2", normalized_hash=uuid.uuid4().hex,
                )
                db.add_all([v1, v2])
                await db.flush()

                # e1: negative marks (-5.0 / 10.0 -> clamped to 0.0)
                # e2: excessive marks (15.0 / 10.0 -> clamped to 1.0)
                e1 = AnswersEvaluation(
                    user_id=user.id, question_id=q1.id, user_submitted_answer="A1",
                    feedback="F1", estimated_marks=-5.0, max_marks=10.0,
                )
                e2 = AnswersEvaluation(
                    user_id=user.id, question_id=q2.id, user_submitted_answer="A2",
                    feedback="F2", estimated_marks=15.0, max_marks=10.0,
                )
                db.add_all([e1, e2])
                await db.commit()

                report = await student_performance_service.get_subject_topic_performance(
                    db=db, user_id=user.id, subject_id=subject.id
                )
                top = report.topics[0]
                # (0.0 + 1.0) / 2 = 0.5000
                self.assertEqual(top.mastery, 0.5000)
                self.assertGreaterEqual(top.mastery, 0.0)
                self.assertLessEqual(top.mastery, 1.0)

        self.loop.run_until_complete(_run())

    def test_05_unresolved_topic_excluded_from_topic_mastery(self) -> None:
        """Verify evaluations not mapped to any canonical topic are excluded and counted."""
        async def _run():
            async with SessionLocal() as db:
                user = User(
                    email=f"stu_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="hashed_password",
                    full_name="Unresolved Student",
                    role="student",
                )
                subject = Subject(
                    code=f"UNRES-{uuid.uuid4().hex[:4]}",
                    name="Unresolved Subject",
                    semester=6,
                    branch="Computer Engineering",
                )
                db.add_all([user, subject])
                await db.commit()
                await db.refresh(user)
                await db.refresh(subject)

                t1 = CanonicalTopic(
                    subject_id=subject.id,
                    canonical_label="Known Topic",
                    normalized_label="known topic",
                )
                db.add(t1)
                await db.flush()

                # Q_unresolved has no variant and no compatibility link
                q_unresolved = Question(
                    subject_id=subject.id, text="Mystery Question", marks_weight=10
                )
                db.add(q_unresolved)
                await db.flush()

                eval_unresolved = AnswersEvaluation(
                    user_id=user.id,
                    question_id=q_unresolved.id,
                    user_submitted_answer="Answer to unlinked question",
                    feedback="Unlinked feedback",
                    estimated_marks=8.0,
                    max_marks=10.0,
                )
                db.add(eval_unresolved)
                await db.commit()

                report = await student_performance_service.get_subject_topic_performance(
                    db=db, user_id=user.id, subject_id=subject.id
                )

                # Known topic should have NO evaluations
                top = report.topics[0]
                self.assertEqual(top.evaluation_count, 0)
                self.assertIsNone(top.mastery)
                self.assertFalse(top.has_student_data)

                # Unresolved count must be 1
                self.assertEqual(report.unresolved_evaluations_count, 1)

        self.loop.run_until_complete(_run())

    def test_06_multi_student_isolation(self) -> None:
        """Verify Student A's evaluations do not leak into Student B's performance."""
        async def _run():
            async with SessionLocal() as db:
                user_a = User(
                    email=f"stu_a_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="h", full_name="Student A", role="student",
                )
                user_b = User(
                    email=f"stu_b_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="h", full_name="Student B", role="student",
                )
                subject = Subject(
                    code=f"ISOL-{uuid.uuid4().hex[:4]}",
                    name="Isolation Subject", semester=6, branch="Comp",
                )
                db.add_all([user_a, user_b, subject])
                await db.commit()
                await db.refresh(user_a)
                await db.refresh(user_b)
                await db.refresh(subject)

                t1 = CanonicalTopic(
                    subject_id=subject.id, canonical_label="Topic Isolation", normalized_label="topic isolation"
                )
                db.add(t1)
                await db.flush()

                q1 = Question(subject_id=subject.id, text="Q1", marks_weight=10)
                db.add(q1)
                await db.flush()

                v1 = QuestionVariant(
                    subject_id=subject.id, topic_id=t1.id, legacy_question_id=q1.id,
                    text="Q1", normalized_text="q1", normalized_hash=uuid.uuid4().hex,
                )
                db.add(v1)
                await db.flush()

                # User A has an evaluation: 9.0 / 10.0 = 0.90
                e_a = AnswersEvaluation(
                    user_id=user_a.id, question_id=q1.id, user_submitted_answer="A",
                    feedback="FA", estimated_marks=9.0, max_marks=10.0,
                )
                db.add(e_a)
                await db.commit()

                # Fetch report for User B (has NO evaluations)
                rep_b = await student_performance_service.get_subject_topic_performance(
                    db=db, user_id=user_b.id, subject_id=subject.id
                )
                self.assertFalse(rep_b.has_student_data)
                self.assertIsNone(rep_b.topics[0].mastery)
                self.assertEqual(rep_b.topics[0].evaluation_count, 0)

                # Fetch report for User A (has evaluation)
                rep_a = await student_performance_service.get_subject_topic_performance(
                    db=db, user_id=user_a.id, subject_id=subject.id
                )
                self.assertTrue(rep_a.has_student_data)
                self.assertEqual(rep_a.topics[0].mastery, 0.9000)
                self.assertEqual(rep_a.topics[0].evaluation_count, 1)

        self.loop.run_until_complete(_run())

    def test_07_multi_topic_isolation(self) -> None:
        """Verify evaluations on Topic A do not bleed into Topic B."""
        async def _run():
            async with SessionLocal() as db:
                user = User(
                    email=f"stu_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="h", full_name="Topic Isol Student", role="student",
                )
                subject = Subject(
                    code=f"TOPISOL-{uuid.uuid4().hex[:4]}",
                    name="Topic Isol Subject", semester=6, branch="Comp",
                )
                db.add_all([user, subject])
                await db.commit()
                await db.refresh(user)
                await db.refresh(subject)

                t1 = CanonicalTopic(subject_id=subject.id, canonical_label="Topic Alpha", normalized_label="topic alpha")
                t2 = CanonicalTopic(subject_id=subject.id, canonical_label="Topic Beta", normalized_label="topic beta")
                db.add_all([t1, t2])
                await db.flush()

                q1 = Question(subject_id=subject.id, text="Q Alpha", marks_weight=10)
                db.add(q1)
                await db.flush()

                v1 = QuestionVariant(
                    subject_id=subject.id, topic_id=t1.id, legacy_question_id=q1.id,
                    text="Q Alpha", normalized_text="q alpha", normalized_hash=uuid.uuid4().hex,
                )
                db.add(v1)
                await db.flush()

                # User evaluated only on Topic Alpha: 3.0 / 10.0 = 0.30
                e1 = AnswersEvaluation(
                    user_id=user.id, question_id=q1.id, user_submitted_answer="Ans",
                    feedback="Fb", estimated_marks=3.0, max_marks=10.0,
                )
                db.add(e1)
                await db.commit()

                report = await student_performance_service.get_subject_topic_performance(
                    db=db, user_id=user.id, subject_id=subject.id
                )

                t_map = {t.canonical_label: t for t in report.topics}
                alpha = t_map["Topic Alpha"]
                beta = t_map["Topic Beta"]

                self.assertEqual(alpha.evaluation_count, 1)
                self.assertEqual(alpha.mastery, 0.3000)
                self.assertTrue(alpha.has_student_data)

                self.assertEqual(beta.evaluation_count, 0)
                self.assertIsNone(beta.mastery)
                self.assertFalse(beta.has_student_data)

        self.loop.run_until_complete(_run())

    def test_08_subject_isolation(self) -> None:
        """Verify performance from another subject does not leak into the requested subject."""
        async def _run():
            async with SessionLocal() as db:
                user = User(
                    email=f"stu_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="h", full_name="Subj Isol Student", role="student",
                )
                subj1 = Subject(code=f"SUBJ1-{uuid.uuid4().hex[:4]}", name="Subject 1", semester=5, branch="Comp")
                subj2 = Subject(code=f"SUBJ2-{uuid.uuid4().hex[:4]}", name="Subject 2", semester=6, branch="Comp")
                db.add_all([user, subj1, subj2])
                await db.commit()
                await db.refresh(user)
                await db.refresh(subj1)
                await db.refresh(subj2)

                t_s1 = CanonicalTopic(subject_id=subj1.id, canonical_label="Topic In S1", normalized_label="topic in s1")
                t_s2 = CanonicalTopic(subject_id=subj2.id, canonical_label="Topic In S2", normalized_label="topic in s2")
                db.add_all([t_s1, t_s2])
                await db.flush()

                q_s1 = Question(subject_id=subj1.id, text="Q S1", marks_weight=10)
                db.add(q_s1)
                await db.flush()

                v_s1 = QuestionVariant(
                    subject_id=subj1.id, topic_id=t_s1.id, legacy_question_id=q_s1.id,
                    text="Q S1", normalized_text="q s1", normalized_hash=uuid.uuid4().hex,
                )
                db.add(v_s1)
                await db.flush()

                # User evaluated in Subject 1
                e_s1 = AnswersEvaluation(
                    user_id=user.id, question_id=q_s1.id, user_submitted_answer="Ans",
                    feedback="Fb", estimated_marks=8.0, max_marks=10.0,
                )
                db.add(e_s1)
                await db.commit()

                # Query Subject 2: must have zero evaluations
                rep_s2 = await student_performance_service.get_subject_topic_performance(
                    db=db, user_id=user.id, subject_id=subj2.id
                )
                self.assertFalse(rep_s2.has_student_data)
                self.assertEqual(len(rep_s2.topics), 1)
                self.assertIsNone(rep_s2.topics[0].mastery)
                self.assertEqual(rep_s2.topics[0].evaluation_count, 0)

        self.loop.run_until_complete(_run())

    def test_09_api_endpoint_topic_performance(self) -> None:
        """Verify the GET /api/v1/analytics/subjects/{id}/topic-performance endpoint returns 200."""
        async def _run():
            async with SessionLocal() as db:
                user = User(
                    email=f"api_stu_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="h", full_name="API Student", role="student",
                )
                subject = Subject(
                    code=f"APISUBJ-{uuid.uuid4().hex[:4]}",
                    name="API Subject", semester=6, branch="Comp",
                )
                db.add_all([user, subject])
                await db.commit()
                await db.refresh(user)
                await db.refresh(subject)

                t1 = CanonicalTopic(
                    subject_id=subject.id, canonical_label="API Topic", normalized_label="api topic"
                )
                db.add(t1)
                await db.commit()

                # 1. Successful call
                res = await get_subject_topic_performance(
                    subject_id=subject.id, db=db, current_user=user
                )
                self.assertIsInstance(res, SubjectTopicPerformanceOut)
                self.assertEqual(res.subject_id, subject.id)
                self.assertEqual(res.student_id, user.id)
                self.assertEqual(len(res.topics), 1)

                # 2. Non-existent subject raises 404
                fake_id = uuid.uuid4()
                with self.assertRaises(HTTPException) as ctx:
                    await get_subject_topic_performance(
                        subject_id=fake_id, db=db, current_user=user
                    )
                self.assertEqual(ctx.exception.status_code, 404)

        self.loop.run_until_complete(_run())

    def test_10_exam_priority_backward_compatibility(self) -> None:
        """Verify that existing Exam Priority calculations remain 100% compatible."""
        async def _run():
            async with SessionLocal() as db:
                user = User(
                    email=f"ep_stu_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="h", full_name="EP Student", role="student",
                )
                subject = Subject(
                    code=f"EPSUBJ-{uuid.uuid4().hex[:4]}",
                    name="EP Subject", semester=6, branch="Comp",
                )
                db.add_all([user, subject])
                await db.commit()
                await db.refresh(user)
                await db.refresh(subject)

                t1 = CanonicalTopic(
                    subject_id=subject.id, canonical_label="EP Topic", normalized_label="ep topic"
                )
                db.add(t1)
                await db.flush()

                q1 = Question(
                    subject_id=subject.id, text="EP Q", marks_weight=10, is_pyq=True, occurrences=2
                )
                db.add(q1)
                await db.flush()

                v1 = QuestionVariant(
                    subject_id=subject.id, topic_id=t1.id, legacy_question_id=q1.id,
                    text="EP Q", normalized_text="ep q", normalized_hash=uuid.uuid4().hex,
                )
                db.add(v1)
                await db.flush()

                paper = PYQPaper(subject_id=subject.id, title="EP Paper 2023", exam_year=2023)
                db.add(paper)
                await db.flush()

                occ = PYQQuestionOccurrence(
                    paper_id=paper.id, variant_id=v1.id, marks_weight=10, source_text=v1.text
                )
                db.add(occ)
                await db.flush()

                # User evaluated: 5.0 / 10.0 = 0.50 -> weakness = 0.50
                e1 = AnswersEvaluation(
                    user_id=user.id, question_id=q1.id, user_submitted_answer="Ans",
                    feedback="Fb", estimated_marks=5.0, max_marks=10.0,
                )
                db.add(e1)
                await db.commit()

                report = await analytics_service.get_exam_priority_report(
                    db=db, user_id=user.id, subject_id=subject.id
                )
                self.assertTrue(report.has_student_data)
                self.assertEqual(len(report.topics), 1)
                top = report.topics[0]
                self.assertEqual(top.student_mastery, 0.5)
                self.assertEqual(top.weakness_score, 0.5)
                # Mode A: 0.40 * 1.0 + 0.30 * 1.0 + 0.30 * 0.5 = 0.40 + 0.30 + 0.15 = 0.850
                self.assertEqual(top.priority_score, 0.850)

        self.loop.run_until_complete(_run())


if __name__ == "__main__":
    unittest.main()
