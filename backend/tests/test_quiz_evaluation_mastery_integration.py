import asyncio
import sys
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

import app.database.base  # noqa: F401
from app.api.v1.endpoints.analytics import (
    get_subject_exam_priority,
    get_subject_topic_performance,
)
from app.api.v1.endpoints.evaluations import evaluate_essay_answer
from app.database.session import SessionLocal
from app.models.answers_evaluation import AnswersEvaluation
from app.models.document import Document
from app.models.pyq_topic import (
    CanonicalTopic,
    PYQPaper,
    PYQQuestionOccurrence,
    QuestionVariant,
)
from app.models.question import Question
from app.models.subject import Subject
from app.models.user import User
from app.schemas.evaluation import EvaluationCreate, EvaluationOut
from app.schemas.topic_performance import (
    StudentTopicPerformanceOut,
    SubjectTopicPerformanceOut,
)
from app.services.evaluation import evaluation_service
from app.services.processing import processing_service
from app.services.student_performance import student_performance_service
from app.services.analytics import analytics_service


class QuizEvaluationMasteryIntegrationTests(unittest.TestCase):
    """
    Phase 7B End-to-End Integration Test Suite:
    Connects the student evaluation workflow with Phase 7A Topic Mastery
    and the Exam Priority engine.

    Verifies:
    1. Answer evaluation flow produces topic performance records.
    2. Single evaluated attempt yields exact clamped mastery and weakness.
    3. Multiple evaluated attempts yield deterministic arithmetic-mean mastery.
    4. New evaluations dynamically recalculate mastery on-demand (no stale state).
    5. Student isolation: Student A's evaluation does not bleed into Student B.
    6. Subject isolation: Evaluations in Subject 1 do not leak into Subject 2.
    7. Unresolved question evaluations are excluded from topic mastery and counted.
    8. Multi-topic isolation: Evaluations on Topic 1 do not alter Topic 2.
    9. Exam Priority engine dynamically consumes student topic mastery.
    10. Full API route handler integration (POST evaluation -> GET topic-performance).
    """

    def setUp(self) -> None:
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self) -> None:
        self.loop.close()

    def test_01_evaluation_service_flow_produces_topic_performance(self) -> None:
        """
        Verify that evaluating a student answer via evaluation_service
        persists AnswersEvaluation and immediately reflects in get_subject_topic_performance.
        """
        async def _run():
            async with SessionLocal() as db:
                # 1. Setup Student and Subject
                user = User(
                    email=f"e2e_stu_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="hashed_pw",
                    full_name="E2E Student",
                    role="student",
                )
                subject = Subject(
                    code=f"CS7B-{uuid.uuid4().hex[:4].upper()}",
                    name="Phase 7B Integration Subject",
                    semester=6,
                    branch="Computer Engineering",
                )
                db.add_all([user, subject])
                await db.commit()
                await db.refresh(user)
                await db.refresh(subject)

                # 2. Setup Canonical Topic and Question linked via QuestionVariant
                topic = CanonicalTopic(
                    subject_id=subject.id,
                    canonical_label="Linkers and Loaders",
                    normalized_label="linkers and loaders",
                    unit_tag="Unit 1",
                )
                db.add(topic)
                await db.flush()

                question = Question(
                    subject_id=subject.id,
                    text="Explain the relocation function of loaders in detail.",
                    marks_weight=10,
                    unit_tag="Unit 1",
                )
                db.add(question)
                await db.flush()

                variant = QuestionVariant(
                    subject_id=subject.id,
                    topic_id=topic.id,
                    legacy_question_id=question.id,
                    text=question.text,
                    normalized_text="explain the relocation function of loaders in detail",
                    normalized_hash=uuid.uuid4().hex,
                    resolution_type="exact_match",
                )
                db.add(variant)
                await db.commit()

                # 3. Before evaluation: Topic Performance must report has_student_data=False and mastery=None
                initial_report = await student_performance_service.get_subject_topic_performance(
                    db=db, user_id=user.id, subject_id=subject.id
                )
                self.assertFalse(initial_report.has_student_data)
                self.assertEqual(initial_report.total_topics, 1)
                self.assertEqual(initial_report.evaluated_topics_count, 0)
                self.assertIsNone(initial_report.topics[0].mastery)
                self.assertEqual(initial_report.topics[0].evaluation_count, 0)

                # 4. Evaluate answer via evaluation_service (using fallback/grounded evaluation)
                student_answer = "Loaders perform relocation by adjusting program addresses to match assigned memory locations."
                eval_res = await evaluation_service.evaluate_student_answer(
                    db=db,
                    user_id=user.id,
                    question_id=question.id,
                    user_submitted_answer=student_answer,
                )
                self.assertIsInstance(eval_res, AnswersEvaluation)
                self.assertEqual(eval_res.user_id, user.id)
                self.assertEqual(eval_res.question_id, question.id)
                self.assertEqual(eval_res.max_marks, 10.0)
                self.assertGreater(eval_res.estimated_marks, 0.0)

                # 5. After evaluation: Topic Performance must now reflect the evaluated attempt
                updated_report = await student_performance_service.get_subject_topic_performance(
                    db=db, user_id=user.id, subject_id=subject.id
                )
                self.assertTrue(updated_report.has_student_data)
                self.assertEqual(updated_report.evaluated_topics_count, 1)
                top = updated_report.topics[0]
                self.assertEqual(top.topic_id, topic.id)
                self.assertEqual(top.canonical_label, "Linkers and Loaders")
                self.assertEqual(top.evaluation_count, 1)
                self.assertTrue(top.has_student_data)

                expected_ratio = round(eval_res.estimated_marks / 10.0, 4)
                self.assertEqual(top.mastery, expected_ratio)
                self.assertEqual(top.weakness, round(1.0 - expected_ratio, 4))

        self.loop.run_until_complete(_run())

    def test_02_single_evaluated_attempt_exact_mastery(self) -> None:
        """
        Verify single evaluated attempt with exact marks produces identical clamped mastery.
        """
        async def _run():
            async with SessionLocal() as db:
                user = User(
                    email=f"stu_single_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="h", full_name="Single Student", role="student",
                )
                subject = Subject(
                    code=f"SINGLE-{uuid.uuid4().hex[:4].upper()}",
                    name="Single Attempt Subject", semester=6, branch="Comp",
                )
                db.add_all([user, subject])
                await db.commit()
                await db.refresh(user)
                await db.refresh(subject)

                t = CanonicalTopic(
                    subject_id=subject.id,
                    canonical_label="Pipeline Hazards",
                    normalized_label="pipeline hazards",
                )
                db.add(t)
                await db.flush()

                q = Question(subject_id=subject.id, text="Q1", marks_weight=10)
                db.add(q)
                await db.flush()

                v = QuestionVariant(
                    subject_id=subject.id, topic_id=t.id, legacy_question_id=q.id,
                    text=q.text, normalized_text="q1", normalized_hash=uuid.uuid4().hex,
                )
                db.add(v)
                await db.flush()

                # Exactly 7.0 / 10.0 = 0.7000
                ev = AnswersEvaluation(
                    user_id=user.id, question_id=q.id, user_submitted_answer="Ans",
                    feedback="Good", estimated_marks=7.0, max_marks=10.0,
                )
                db.add(ev)
                await db.commit()

                report = await student_performance_service.get_subject_topic_performance(
                    db=db, user_id=user.id, subject_id=subject.id
                )
                self.assertEqual(report.topics[0].mastery, 0.7000)
                self.assertEqual(report.topics[0].weakness, 0.3000)
                self.assertEqual(report.topics[0].evaluation_count, 1)

        self.loop.run_until_complete(_run())

    def test_03_multiple_evaluated_attempts_arithmetic_mean(self) -> None:
        """
        Verify multiple evaluated attempts on a topic yield the exact arithmetic mean:
        Attempt 1 = 4/10 (0.40), Attempt 2 = 8/10 (0.80) -> mean = 0.6000.
        """
        async def _run():
            async with SessionLocal() as db:
                user = User(
                    email=f"stu_multi_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="h", full_name="Multi Student", role="student",
                )
                subject = Subject(
                    code=f"MULTI-{uuid.uuid4().hex[:4].upper()}",
                    name="Multi Attempt Subject", semester=6, branch="Comp",
                )
                db.add_all([user, subject])
                await db.commit()
                await db.refresh(user)
                await db.refresh(subject)

                t = CanonicalTopic(
                    subject_id=subject.id,
                    canonical_label="Cache Mapping",
                    normalized_label="cache mapping",
                )
                db.add(t)
                await db.flush()

                q = Question(subject_id=subject.id, text="Q Cache", marks_weight=10)
                db.add(q)
                await db.flush()

                v = QuestionVariant(
                    subject_id=subject.id, topic_id=t.id, legacy_question_id=q.id,
                    text=q.text, normalized_text="q cache", normalized_hash=uuid.uuid4().hex,
                )
                db.add(v)
                await db.flush()

                ev1 = AnswersEvaluation(
                    user_id=user.id, question_id=q.id, user_submitted_answer="A1",
                    feedback="Weak", estimated_marks=4.0, max_marks=10.0,
                )
                ev2 = AnswersEvaluation(
                    user_id=user.id, question_id=q.id, user_submitted_answer="A2",
                    feedback="Strong", estimated_marks=8.0, max_marks=10.0,
                )
                db.add_all([ev1, ev2])
                await db.commit()

                report = await student_performance_service.get_subject_topic_performance(
                    db=db, user_id=user.id, subject_id=subject.id
                )
                top = report.topics[0]
                self.assertEqual(top.evaluation_count, 2)
                self.assertEqual(top.mastery, 0.6000)
                self.assertEqual(top.weakness, 0.4000)

        self.loop.run_until_complete(_run())

    def test_04_subsequent_evaluation_dynamically_updates_mastery(self) -> None:
        """
        Verify mastery is computed on-demand from current evidence without stale caching:
        Initial -> None
        After eval 1 (0.40) -> 0.4000
        After eval 2 (0.80) -> 0.6000
        """
        async def _run():
            async with SessionLocal() as db:
                user = User(
                    email=f"stu_dyn_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="h", full_name="Dynamic Student", role="student",
                )
                subject = Subject(
                    code=f"DYN-{uuid.uuid4().hex[:4].upper()}",
                    name="Dynamic Subject", semester=6, branch="Comp",
                )
                db.add_all([user, subject])
                await db.commit()
                await db.refresh(user)
                await db.refresh(subject)

                t = CanonicalTopic(
                    subject_id=subject.id, canonical_label="Dynamic Topic", normalized_label="dynamic topic"
                )
                db.add(t)
                await db.flush()

                q = Question(subject_id=subject.id, text="Q Dyn", marks_weight=10)
                db.add(q)
                await db.flush()

                v = QuestionVariant(
                    subject_id=subject.id, topic_id=t.id, legacy_question_id=q.id,
                    text=q.text, normalized_text="q dyn", normalized_hash=uuid.uuid4().hex,
                )
                db.add(v)
                await db.commit()

                # Step 1: No evaluations
                rep0 = await student_performance_service.get_subject_topic_performance(
                    db=db, user_id=user.id, subject_id=subject.id
                )
                self.assertIsNone(rep0.topics[0].mastery)
                self.assertEqual(rep0.topics[0].evaluation_count, 0)

                # Step 2: First attempt (4/10 = 0.40)
                ev1 = AnswersEvaluation(
                    user_id=user.id, question_id=q.id, user_submitted_answer="A1",
                    feedback="F1", estimated_marks=4.0, max_marks=10.0,
                )
                db.add(ev1)
                await db.commit()

                rep1 = await student_performance_service.get_subject_topic_performance(
                    db=db, user_id=user.id, subject_id=subject.id
                )
                self.assertEqual(rep1.topics[0].mastery, 0.4000)
                self.assertEqual(rep1.topics[0].evaluation_count, 1)

                # Step 3: Second attempt (8/10 = 0.80) -> mean becomes 0.60
                ev2 = AnswersEvaluation(
                    user_id=user.id, question_id=q.id, user_submitted_answer="A2",
                    feedback="F2", estimated_marks=8.0, max_marks=10.0,
                )
                db.add(ev2)
                await db.commit()

                rep2 = await student_performance_service.get_subject_topic_performance(
                    db=db, user_id=user.id, subject_id=subject.id
                )
                self.assertEqual(rep2.topics[0].mastery, 0.6000)
                self.assertEqual(rep2.topics[0].evaluation_count, 2)

        self.loop.run_until_complete(_run())

    def test_05_student_isolation_in_evaluation_flow(self) -> None:
        """
        Verify that Student A's evaluation does not affect Student B:
        Student A: 0.40 mastery
        Student B: 0.90 mastery
        """
        async def _run():
            async with SessionLocal() as db:
                user_a = User(
                    email=f"stu_iso_a_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="h", full_name="Student A", role="student",
                )
                user_b = User(
                    email=f"stu_iso_b_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="h", full_name="Student B", role="student",
                )
                subject = Subject(
                    code=f"ISO-{uuid.uuid4().hex[:4].upper()}",
                    name="Student Isolation Subject", semester=6, branch="Comp",
                )
                db.add_all([user_a, user_b, subject])
                await db.commit()
                await db.refresh(user_a)
                await db.refresh(user_b)
                await db.refresh(subject)

                t = CanonicalTopic(
                    subject_id=subject.id, canonical_label="TCP Congestion", normalized_label="tcp congestion"
                )
                db.add(t)
                await db.flush()

                q = Question(subject_id=subject.id, text="Q TCP", marks_weight=10)
                db.add(q)
                await db.flush()

                v = QuestionVariant(
                    subject_id=subject.id, topic_id=t.id, legacy_question_id=q.id,
                    text=q.text, normalized_text="q tcp", normalized_hash=uuid.uuid4().hex,
                )
                db.add(v)
                await db.flush()

                # Student A scores 4.0 / 10.0 = 0.40
                ev_a = AnswersEvaluation(
                    user_id=user_a.id, question_id=q.id, user_submitted_answer="Ans A",
                    feedback="F A", estimated_marks=4.0, max_marks=10.0,
                )
                # Student B scores 9.0 / 10.0 = 0.90
                ev_b = AnswersEvaluation(
                    user_id=user_b.id, question_id=q.id, user_submitted_answer="Ans B",
                    feedback="F B", estimated_marks=9.0, max_marks=10.0,
                )
                db.add_all([ev_a, ev_b])
                await db.commit()

                # Query Student A
                rep_a = await student_performance_service.get_subject_topic_performance(
                    db=db, user_id=user_a.id, subject_id=subject.id
                )
                self.assertEqual(rep_a.topics[0].mastery, 0.4000)
                self.assertEqual(rep_a.topics[0].weakness, 0.6000)
                self.assertEqual(rep_a.topics[0].evaluation_count, 1)

                # Query Student B
                rep_b = await student_performance_service.get_subject_topic_performance(
                    db=db, user_id=user_b.id, subject_id=subject.id
                )
                self.assertEqual(rep_b.topics[0].mastery, 0.9000)
                self.assertEqual(rep_b.topics[0].weakness, 0.1000)
                self.assertEqual(rep_b.topics[0].evaluation_count, 1)

        self.loop.run_until_complete(_run())

    def test_06_subject_isolation_in_evaluation_flow(self) -> None:
        """
        Verify that evaluations under Subject 1 do not leak into Subject 2,
        even if topic labels are identical.
        """
        async def _run():
            async with SessionLocal() as db:
                user = User(
                    email=f"stu_sub_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="h", full_name="Subj Student", role="student",
                )
                s1 = Subject(code=f"S1-{uuid.uuid4().hex[:4]}", name="Subj 1", semester=5, branch="Comp")
                s2 = Subject(code=f"S2-{uuid.uuid4().hex[:4]}", name="Subj 2", semester=6, branch="Comp")
                db.add_all([user, s1, s2])
                await db.commit()
                await db.refresh(user)
                await db.refresh(s1)
                await db.refresh(s2)

                t1 = CanonicalTopic(subject_id=s1.id, canonical_label="OS Deadlocks", normalized_label="os deadlocks")
                t2 = CanonicalTopic(subject_id=s2.id, canonical_label="OS Deadlocks", normalized_label="os deadlocks")
                db.add_all([t1, t2])
                await db.flush()

                q1 = Question(subject_id=s1.id, text="Q Deadlocks S1", marks_weight=10)
                db.add(q1)
                await db.flush()

                v1 = QuestionVariant(
                    subject_id=s1.id, topic_id=t1.id, legacy_question_id=q1.id,
                    text=q1.text, normalized_text="q deadlocks s1", normalized_hash=uuid.uuid4().hex,
                )
                db.add(v1)
                await db.flush()

                # User evaluated only in Subject 1: 8.0 / 10.0 = 0.80
                ev1 = AnswersEvaluation(
                    user_id=user.id, question_id=q1.id, user_submitted_answer="Ans",
                    feedback="F", estimated_marks=8.0, max_marks=10.0,
                )
                db.add(ev1)
                await db.commit()

                # Check Subject 1 -> Mastery 0.80
                rep1 = await student_performance_service.get_subject_topic_performance(
                    db=db, user_id=user.id, subject_id=s1.id
                )
                self.assertEqual(rep1.topics[0].mastery, 0.8000)

                # Check Subject 2 -> Mastery None
                rep2 = await student_performance_service.get_subject_topic_performance(
                    db=db, user_id=user.id, subject_id=s2.id
                )
                self.assertIsNone(rep2.topics[0].mastery)
                self.assertEqual(rep2.topics[0].evaluation_count, 0)
                self.assertFalse(rep2.has_student_data)

        self.loop.run_until_complete(_run())

    def test_07_unresolved_evaluations_excluded_from_mastery(self) -> None:
        """
        Verify that an evaluated answer for an unlinked question does NOT fabricate
        topic mastery for existing canonical topics and increments unresolved_evaluations_count.
        """
        async def _run():
            async with SessionLocal() as db:
                user = User(
                    email=f"stu_unres_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="h", full_name="Unresolved Student", role="student",
                )
                subject = Subject(
                    code=f"UNRES7B-{uuid.uuid4().hex[:4]}",
                    name="Unresolved Subject", semester=6, branch="Comp",
                )
                db.add_all([user, subject])
                await db.commit()
                await db.refresh(user)
                await db.refresh(subject)

                t = CanonicalTopic(
                    subject_id=subject.id, canonical_label="Registered Topic", normalized_label="registered topic"
                )
                db.add(t)
                await db.flush()

                # Unlinked question
                q_unlinked = Question(subject_id=subject.id, text="Unlinked Q", marks_weight=10)
                db.add(q_unlinked)
                await db.flush()

                ev_unlinked = AnswersEvaluation(
                    user_id=user.id, question_id=q_unlinked.id, user_submitted_answer="Ans",
                    feedback="F", estimated_marks=9.0, max_marks=10.0,
                )
                db.add(ev_unlinked)
                await db.commit()

                report = await student_performance_service.get_subject_topic_performance(
                    db=db, user_id=user.id, subject_id=subject.id
                )
                self.assertEqual(report.unresolved_evaluations_count, 1)
                self.assertEqual(report.evaluated_topics_count, 0)
                self.assertIsNone(report.topics[0].mastery)
                self.assertEqual(report.topics[0].evaluation_count, 0)

        self.loop.run_until_complete(_run())

    def test_08_multi_topic_isolation(self) -> None:
        """
        Verify that evaluations on Topic A do not alter Topic B's mastery.
        """
        async def _run():
            async with SessionLocal() as db:
                user = User(
                    email=f"stu_top_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="h", full_name="Topic Student", role="student",
                )
                subject = Subject(
                    code=f"TOP7B-{uuid.uuid4().hex[:4]}",
                    name="Topic Isolation Subject", semester=6, branch="Comp",
                )
                db.add_all([user, subject])
                await db.commit()
                await db.refresh(user)
                await db.refresh(subject)

                t_a = CanonicalTopic(subject_id=subject.id, canonical_label="Topic Alpha", normalized_label="topic alpha")
                t_b = CanonicalTopic(subject_id=subject.id, canonical_label="Topic Beta", normalized_label="topic beta")
                db.add_all([t_a, t_b])
                await db.flush()

                q_a = Question(subject_id=subject.id, text="Q A", marks_weight=10)
                db.add(q_a)
                await db.flush()

                v_a = QuestionVariant(
                    subject_id=subject.id, topic_id=t_a.id, legacy_question_id=q_a.id,
                    text=q_a.text, normalized_text="q a", normalized_hash=uuid.uuid4().hex,
                )
                db.add(v_a)
                await db.flush()

                # Only Topic Alpha evaluated: 5.0 / 10.0 = 0.50
                ev_a = AnswersEvaluation(
                    user_id=user.id, question_id=q_a.id, user_submitted_answer="Ans A",
                    feedback="F A", estimated_marks=5.0, max_marks=10.0,
                )
                db.add(ev_a)
                await db.commit()

                report = await student_performance_service.get_subject_topic_performance(
                    db=db, user_id=user.id, subject_id=subject.id
                )
                t_map = {t.canonical_label: t for t in report.topics}
                self.assertEqual(t_map["Topic Alpha"].mastery, 0.5000)
                self.assertEqual(t_map["Topic Alpha"].evaluation_count, 1)

                self.assertIsNone(t_map["Topic Beta"].mastery)
                self.assertEqual(t_map["Topic Beta"].evaluation_count, 0)
                self.assertFalse(t_map["Topic Beta"].has_student_data)

        self.loop.run_until_complete(_run())

    def test_09_exam_priority_integration_consumes_student_mastery(self) -> None:
        """
        Verify end-to-end integration with the Exam Priority engine:
        1. Before evaluation: Mode B (no student data)
        2. After attempt 1 (0.40): Mode A with mastery=0.4, weakness=0.6
        3. After attempt 2 (0.80): Mode A dynamically updates with mastery=0.6, weakness=0.4
        """
        async def _run():
            async with SessionLocal() as db:
                user = User(
                    email=f"stu_ep_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="h", full_name="EP Student", role="student",
                )
                subject = Subject(
                    code=f"EP7B-{uuid.uuid4().hex[:4].upper()}",
                    name="Exam Priority Integration Subject", semester=6, branch="Comp",
                )
                db.add_all([user, subject])
                await db.commit()
                await db.refresh(user)
                await db.refresh(subject)

                t = CanonicalTopic(
                    subject_id=subject.id,
                    canonical_label="Process Synchronization",
                    normalized_label="process synchronization",
                    unit_tag="Unit 2",
                )
                db.add(t)
                await db.flush()

                q = Question(
                    subject_id=subject.id, text="Explain Semaphores.", marks_weight=10, is_pyq=True, occurrences=2
                )
                db.add(q)
                await db.flush()

                v = QuestionVariant(
                    subject_id=subject.id, topic_id=t.id, legacy_question_id=q.id,
                    text=q.text, normalized_text="explain semaphores", normalized_hash=uuid.uuid4().hex,
                )
                db.add(v)
                await db.flush()

                paper = PYQPaper(subject_id=subject.id, title="Dec 2023", exam_year=2023)
                db.add(paper)
                await db.flush()

                occ = PYQQuestionOccurrence(
                    paper_id=paper.id, variant_id=v.id, marks_weight=10, source_text=v.text
                )
                db.add(occ)
                await db.flush()

                # Step 1: Query Exam Priority before any student evaluations (Mode B)
                ep_report_0 = await analytics_service.get_exam_priority_report(
                    db=db, user_id=user.id, subject_id=subject.id
                )
                self.assertFalse(ep_report_0.has_student_data)
                top_0 = ep_report_0.topics[0]
                self.assertIsNone(top_0.student_mastery)
                self.assertIsNone(top_0.weakness_score)
                # Mode B: 0.60 * 1.0 + 0.40 * 1.0 = 1.000
                self.assertEqual(top_0.priority_score, 1.000)

                # Step 2: Student completes attempt 1 (4/10 = 0.40 mastery, 0.60 weakness)
                ev1 = AnswersEvaluation(
                    user_id=user.id, question_id=q.id, user_submitted_answer="Partial semaphores answer",
                    feedback="Needs wait/signal definitions", estimated_marks=4.0, max_marks=10.0,
                )
                db.add(ev1)
                await db.commit()

                # Query Exam Priority: switches to Mode A with weakness=0.60
                ep_report_1 = await analytics_service.get_exam_priority_report(
                    db=db, user_id=user.id, subject_id=subject.id
                )
                self.assertTrue(ep_report_1.has_student_data)
                top_1 = ep_report_1.topics[0]
                self.assertEqual(top_1.student_mastery, 0.4)
                self.assertEqual(top_1.weakness_score, 0.6)
                # Mode A: 0.40 * 1.0 + 0.30 * 1.0 + 0.30 * 0.60 = 0.40 + 0.30 + 0.18 = 0.880
                self.assertEqual(top_1.priority_score, 0.880)

                # Step 3: Student completes attempt 2 (8/10 -> mastery becomes 0.60, weakness becomes 0.40)
                ev2 = AnswersEvaluation(
                    user_id=user.id, question_id=q.id, user_submitted_answer="Improved semaphores answer",
                    feedback="Much better", estimated_marks=8.0, max_marks=10.0,
                )
                db.add(ev2)
                await db.commit()

                # Query Exam Priority: dynamically recalculates with weakness=0.40
                ep_report_2 = await analytics_service.get_exam_priority_report(
                    db=db, user_id=user.id, subject_id=subject.id
                )
                top_2 = ep_report_2.topics[0]
                self.assertEqual(top_2.student_mastery, 0.6)
                self.assertEqual(top_2.weakness_score, 0.4)
                # Mode A: 0.40 * 1.0 + 0.30 * 1.0 + 0.30 * 0.40 = 0.40 + 0.30 + 0.12 = 0.820
                self.assertEqual(top_2.priority_score, 0.820)

        self.loop.run_until_complete(_run())

    def test_10_api_endpoints_end_to_end(self) -> None:
        """
        Verify the real API endpoint flow:
        POST /api/v1/evaluations/
        followed by
        GET /api/v1/analytics/subjects/{id}/topic-performance
        """
        async def _run():
            async with SessionLocal() as db:
                user = User(
                    email=f"api_e2e_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="h", full_name="API User", role="student",
                )
                subject = Subject(
                    code=f"API7B-{uuid.uuid4().hex[:4].upper()}",
                    name="API Flow Subject", semester=6, branch="Comp",
                )
                db.add_all([user, subject])
                await db.commit()
                await db.refresh(user)
                await db.refresh(subject)

                t = CanonicalTopic(
                    subject_id=subject.id,
                    canonical_label="API Mastery Topic",
                    normalized_label="api mastery topic",
                )
                db.add(t)
                await db.flush()

                q = Question(subject_id=subject.id, text="API Question", marks_weight=10)
                db.add(q)
                await db.flush()

                v = QuestionVariant(
                    subject_id=subject.id, topic_id=t.id, legacy_question_id=q.id,
                    text=q.text, normalized_text="api question", normalized_hash=uuid.uuid4().hex,
                )
                db.add(v)
                await db.commit()

                # Call evaluate_essay_answer endpoint directly
                eval_in = EvaluationCreate(
                    question_id=q.id,
                    user_submitted_answer="Detailed answer for API evaluation testing.",
                )
                eval_out = await evaluate_essay_answer(
                    eval_in=eval_in, db=db, current_user=user
                )
                self.assertEqual(eval_out.question_id, q.id)
                self.assertEqual(eval_out.user_id, user.id)

                # Call get_subject_topic_performance endpoint directly
                tp_out = await get_subject_topic_performance(
                    subject_id=subject.id, db=db, current_user=user
                )
                self.assertIsInstance(tp_out, SubjectTopicPerformanceOut)
                self.assertEqual(tp_out.subject_id, subject.id)
                self.assertEqual(tp_out.student_id, user.id)
                self.assertTrue(tp_out.has_student_data)
                self.assertEqual(tp_out.evaluated_topics_count, 1)

                top = tp_out.topics[0]
                self.assertEqual(top.topic_id, t.id)
                self.assertEqual(top.evaluation_count, 1)
                self.assertIsNotNone(top.mastery)
                self.assertIsNotNone(top.weakness)
                self.assertAlmostEqual(top.mastery + top.weakness, 1.0, places=4)

        self.loop.run_until_complete(_run())


if __name__ == "__main__":
    unittest.main()
