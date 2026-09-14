import asyncio
import math
import sys
import unittest
import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from fastapi import HTTPException
from sqlalchemy import event, select
import app.database.base  # noqa: F401
from app.api.v1.endpoints.analytics import get_subject_analytics_report, get_subject_exam_priority
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
from app.repositories.topic_mastery import topic_mastery_repository
from app.schemas.analytics import SubjectAnalyticsOut, SubjectExamPriorityOut
from app.services.analytics import analytics_service


class ExamPriorityApiTests(unittest.TestCase):
    """
    Phase 3C integration & API test suite:
    Verifies the end-to-end integration between:
    - Topic-level PYQ aggregations (Phase 3A)
    - Student evaluation mastery aggregated at the canonical topic level
    - Pure Exam Intelligence Service (Phase 3B)
    - Analytics service and API endpoints (Phase 3C)
    """

    def setUp(self) -> None:
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self) -> None:
        self.loop.close()

    def test_01_topic_aggregation_and_scoring_integration(self) -> None:
        """
        Verify end-to-end integration:
        - Topic aggregates from PYQ occurrences
        - Student mastery from answer evaluations
        - Output structure matching SubjectExamPriorityOut
        """
        async def _run():
            async with SessionLocal() as db:
                user = User(
                    email=f"student_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="hashed_password",
                    full_name="Exam Priority Student",
                    role="student",
                )
                subject = Subject(
                    code=f"CS-3C-{uuid.uuid4().hex[:4].upper()}",
                    name="Phase 3C Integration Subject",
                    semester=6,
                    branch="Computer Engineering",
                )
                db.add_all([user, subject])
                await db.commit()
                await db.refresh(user)
                await db.refresh(subject)

                # Topics: T1 (High PYQ), T2 (Medium PYQ)
                t1 = CanonicalTopic(
                    subject_id=subject.id,
                    canonical_label="Pipeline Hazards",
                    normalized_label="pipeline hazards",
                    unit_tag="Unit 2",
                )
                t2 = CanonicalTopic(
                    subject_id=subject.id,
                    canonical_label="Cache Memory",
                    normalized_label="cache memory",
                    unit_tag="Unit 3",
                )
                db.add_all([t1, t2])
                await db.flush()

                # Questions and Variants
                q1 = Question(
                    subject_id=subject.id,
                    text="Explain pipeline hazards.",
                    marks_weight=10,
                    unit_tag="Unit 2",
                    is_pyq=True,
                    occurrences=2,
                )
                q2 = Question(
                    subject_id=subject.id,
                    text="Describe direct mapped cache.",
                    marks_weight=5,
                    unit_tag="Unit 3",
                    is_pyq=True,
                    occurrences=1,
                )
                db.add_all([q1, q2])
                await db.flush()

                v1 = QuestionVariant(
                    subject_id=subject.id,
                    topic_id=t1.id,
                    legacy_question_id=q1.id,
                    text=q1.text,
                    normalized_text="explain pipeline hazards",
                    normalized_hash=uuid.uuid4().hex,
                    resolution_type="semantic_match",
                )
                v2 = QuestionVariant(
                    subject_id=subject.id,
                    topic_id=t2.id,
                    legacy_question_id=q2.id,
                    text=q2.text,
                    normalized_text="describe direct mapped cache",
                    normalized_hash=uuid.uuid4().hex,
                    resolution_type="semantic_match",
                )
                db.add_all([v1, v2])
                await db.flush()

                paper = PYQPaper(subject_id=subject.id, title="May 2023", exam_year=2023)
                db.add(paper)
                await db.flush()

                occ1 = PYQQuestionOccurrence(
                    paper_id=paper.id, variant_id=v1.id, marks_weight=10, source_text=v1.text
                )
                occ2 = PYQQuestionOccurrence(
                    paper_id=paper.id, variant_id=v2.id, marks_weight=5, source_text=v2.text
                )
                db.add_all([occ1, occ2])
                await db.flush()

                # Evaluation on q1: 4.0 / 10.0 = 0.40 mastery (weakness = 0.60)
                eval1 = AnswersEvaluation(
                    user_id=user.id,
                    question_id=q1.id,
                    user_submitted_answer="Partial explanation of hazards.",
                    feedback="Needs structural hazard examples.",
                    estimated_marks=4.0,
                    max_marks=10.0,
                    improvement_points={"gaps": ["structural hazards"]},
                )
                db.add(eval1)
                await db.commit()

                # Run report
                report = await analytics_service.get_exam_priority_report(
                    db=db, user_id=user.id, subject_id=subject.id
                )

                self.assertIsInstance(report, SubjectExamPriorityOut)
                self.assertEqual(report.subject_id, subject.id)
                self.assertTrue(report.has_student_data)
                self.assertEqual(report.total_topics, 2)

                res_by_id = {r.topic_id: r for r in report.topics}
                t1_res = res_by_id[t1.id]
                t2_res = res_by_id[t2.id]

                # T1 has student evaluation:
                self.assertEqual(t1_res.frequency_score, 1.0)
                self.assertEqual(t1_res.marks_score, 1.0)
                self.assertEqual(t1_res.student_mastery, 0.4)
                self.assertEqual(t1_res.weakness_score, 0.6)
                # Mode A: 0.40 * 1.0 + 0.30 * 1.0 + 0.30 * 0.6 = 0.40 + 0.30 + 0.18 = 0.880
                self.assertEqual(t1_res.priority_score, 0.880)
                self.assertEqual(t1_res.priority_label, "Very High")
                self.assertEqual(t1_res.evaluation_count, 1)
                self.assertTrue(t1_res.has_student_data)
                self.assertIn("40%", t1_res.evidence.mastery_rationale)

                # T2 has NO student evaluation -> Mode B:
                self.assertEqual(t2_res.frequency_score, 1.0)
                self.assertEqual(t2_res.marks_score, 0.5)
                self.assertIsNone(t2_res.student_mastery)
                self.assertIsNone(t2_res.weakness_score)
                # Mode B: 0.60 * 1.0 + 0.40 * 0.5 = 0.60 + 0.20 = 0.800
                self.assertEqual(t2_res.priority_score, 0.800)
                self.assertEqual(t2_res.priority_label, "Very High")
                self.assertEqual(t2_res.evaluation_count, 0)
                self.assertFalse(t2_res.has_student_data)

        self.loop.run_until_complete(_run())

    def test_02_multiple_variants_and_evaluations_arithmetic_mean(self) -> None:
        """
        Verify that multiple variants belonging to one canonical topic aggregate
        their evaluations into the correct arithmetic mean:
        Variant 1 -> 4/10 = 0.4
        Variant 2 -> 8/10 = 0.8
        Topic mastery = (0.4 + 0.8) / 2 = 0.6
        Weakness = 1.0 - 0.6 = 0.4
        """
        async def _run():
            async with SessionLocal() as db:
                user = User(
                    email=f"mean_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="pass",
                    full_name="Mean Tester",
                    role="student",
                )
                subject = Subject(
                    code=f"CS-MEAN-{uuid.uuid4().hex[:4].upper()}",
                    name="Arithmetic Mean Subject",
                    semester=6,
                    branch="Computer Engineering",
                )
                db.add_all([user, subject])
                await db.commit()

                topic = CanonicalTopic(
                    subject_id=subject.id,
                    canonical_label="Virtual Memory & Paging",
                    normalized_label="virtual memory and paging",
                )
                db.add(topic)
                await db.flush()

                q1 = Question(subject_id=subject.id, text="Q1 Paging", marks_weight=10)
                q2 = Question(subject_id=subject.id, text="Q2 Virtual Memory", marks_weight=10)
                db.add_all([q1, q2])
                await db.flush()

                v1 = QuestionVariant(
                    subject_id=subject.id,
                    topic_id=topic.id,
                    legacy_question_id=q1.id,
                    text="Q1 text",
                    normalized_text="q1 text",
                    normalized_hash=uuid.uuid4().hex,
                )
                v2 = QuestionVariant(
                    subject_id=subject.id,
                    topic_id=topic.id,
                    legacy_question_id=q2.id,
                    text="Q2 text",
                    normalized_text="q2 text",
                    normalized_hash=uuid.uuid4().hex,
                )
                db.add_all([v1, v2])
                await db.flush()

                # Evaluations:
                # ev1 on q1: 4/10 = 0.4
                # ev2 on q2: 8/10 = 0.8
                ev1 = AnswersEvaluation(
                    user_id=user.id,
                    question_id=q1.id,
                    user_submitted_answer="Ans 1",
                    feedback="Fb 1",
                    estimated_marks=4.0,
                    max_marks=10.0,
                )
                ev2 = AnswersEvaluation(
                    user_id=user.id,
                    question_id=q2.id,
                    user_submitted_answer="Ans 2",
                    feedback="Fb 2",
                    estimated_marks=8.0,
                    max_marks=10.0,
                )
                db.add_all([ev1, ev2])
                await db.commit()

                mastery_map = await topic_mastery_repository.get_student_topic_mastery(
                    db, user_id=user.id, subject_id=subject.id
                )

                self.assertIn(topic.id, mastery_map)
                perf = mastery_map[topic.id]
                self.assertEqual(perf.evaluation_count, 2)
                self.assertAlmostEqual(perf.mastery, 0.6, places=5)

        self.loop.run_until_complete(_run())

    def test_03_compatibility_bridge_mapping(self) -> None:
        """
        Verify that an evaluation on CanonicalTopic.compatibility_question_id
        is safely mapped to the topic even when no QuestionVariant.legacy_question_id points to it.
        """
        async def _run():
            async with SessionLocal() as db:
                user = User(
                    email=f"bridge_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="pass",
                    full_name="Bridge Tester",
                    role="student",
                )
                subject = Subject(
                    code=f"CS-BRDG-{uuid.uuid4().hex[:4].upper()}",
                    name="Bridge Subject",
                    semester=6,
                    branch="Computer Engineering",
                )
                db.add_all([user, subject])
                await db.commit()

                compat_q = Question(subject_id=subject.id, text="Compatibility Question", marks_weight=10)
                db.add(compat_q)
                await db.flush()

                topic = CanonicalTopic(
                    subject_id=subject.id,
                    canonical_label="Bridge Topic",
                    normalized_label="bridge topic",
                    compatibility_question_id=compat_q.id,
                )
                db.add(topic)
                await db.flush()

                # Evaluation on compat_q: 9.0 / 10.0 = 0.9
                ev = AnswersEvaluation(
                    user_id=user.id,
                    question_id=compat_q.id,
                    user_submitted_answer="Great answer",
                    feedback="Excellent",
                    estimated_marks=9.0,
                    max_marks=10.0,
                )
                db.add(ev)
                await db.commit()

                mastery_map = await topic_mastery_repository.get_student_topic_mastery(
                    db, user_id=user.id, subject_id=subject.id
                )

                self.assertIn(topic.id, mastery_map)
                self.assertEqual(mastery_map[topic.id].evaluation_count, 1)
                self.assertAlmostEqual(mastery_map[topic.id].mastery, 0.9, places=5)

        self.loop.run_until_complete(_run())

    def test_04_multiple_attempts_same_question(self) -> None:
        """
        Verify that multiple attempts on the same question are both included in the
        arithmetic mean mastery:
        Attempt 1: 3/10 = 0.3
        Attempt 2: 7/10 = 0.7
        Mean = (0.3 + 0.7) / 2 = 0.5, count = 2
        """
        async def _run():
            async with SessionLocal() as db:
                user = User(
                    email=f"attempts_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="pass",
                    full_name="Attempt Tester",
                    role="student",
                )
                subject = Subject(
                    code=f"CS-ATTM-{uuid.uuid4().hex[:4].upper()}",
                    name="Attempt Subject",
                    semester=6,
                    branch="Computer Engineering",
                )
                db.add_all([user, subject])
                await db.commit()

                q = Question(subject_id=subject.id, text="Repeated Attempt Question", marks_weight=10)
                db.add(q)
                await db.flush()

                topic = CanonicalTopic(
                    subject_id=subject.id,
                    canonical_label="Repeated Attempt Topic",
                    normalized_label="repeated attempt topic",
                    compatibility_question_id=q.id,
                )
                db.add(topic)
                await db.flush()

                ev1 = AnswersEvaluation(
                    user_id=user.id,
                    question_id=q.id,
                    user_submitted_answer="First try",
                    feedback="Needs work",
                    estimated_marks=3.0,
                    max_marks=10.0,
                )
                ev2 = AnswersEvaluation(
                    user_id=user.id,
                    question_id=q.id,
                    user_submitted_answer="Second try",
                    feedback="Much better",
                    estimated_marks=7.0,
                    max_marks=10.0,
                )
                db.add_all([ev1, ev2])
                await db.commit()

                mastery_map = await topic_mastery_repository.get_student_topic_mastery(
                    db, user_id=user.id, subject_id=subject.id
                )

                self.assertIn(topic.id, mastery_map)
                self.assertEqual(mastery_map[topic.id].evaluation_count, 2)
                self.assertAlmostEqual(mastery_map[topic.id].mastery, 0.5, places=5)

        self.loop.run_until_complete(_run())

    def test_05_subject_isolation(self) -> None:
        """
        Verify that a student's evaluations in Subject B NEVER affect Subject A.
        """
        async def _run():
            async with SessionLocal() as db:
                user = User(
                    email=f"iso_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="pass",
                    full_name="Isolation Tester",
                    role="student",
                )
                sub_a = Subject(code=f"SUB-A-{uuid.uuid4().hex[:4].upper()}", name="Subject A", semester=5, branch="CS")
                sub_b = Subject(code=f"SUB-B-{uuid.uuid4().hex[:4].upper()}", name="Subject B", semester=5, branch="CS")
                db.add_all([user, sub_a, sub_b])
                await db.commit()

                # Topic in Subject A
                q_a = Question(subject_id=sub_a.id, text="Question A", marks_weight=10)
                db.add(q_a)
                await db.flush()

                t_a = CanonicalTopic(
                    subject_id=sub_a.id,
                    canonical_label="Topic A",
                    normalized_label="topic a",
                    compatibility_question_id=q_a.id,
                )
                db.add(t_a)
                await db.flush()

                # Topic in Subject B
                q_b = Question(subject_id=sub_b.id, text="Question B", marks_weight=10)
                db.add(q_b)
                await db.flush()

                t_b = CanonicalTopic(
                    subject_id=sub_b.id,
                    canonical_label="Topic B",
                    normalized_label="topic b",
                    compatibility_question_id=q_b.id,
                )
                db.add(t_b)
                await db.flush()

                # Evaluation in Subject A: 9/10 = 0.9
                # Evaluation in Subject B: 2/10 = 0.2
                ev_a = AnswersEvaluation(
                    user_id=user.id,
                    question_id=q_a.id,
                    user_submitted_answer="Ans A",
                    feedback="Good",
                    estimated_marks=9.0,
                    max_marks=10.0,
                )
                ev_b = AnswersEvaluation(
                    user_id=user.id,
                    question_id=q_b.id,
                    user_submitted_answer="Ans B",
                    feedback="Weak",
                    estimated_marks=2.0,
                    max_marks=10.0,
                )
                db.add_all([ev_a, ev_b])
                await db.commit()

                # Query Subject A
                mastery_a = await topic_mastery_repository.get_student_topic_mastery(
                    db, user_id=user.id, subject_id=sub_a.id
                )
                self.assertIn(t_a.id, mastery_a)
                self.assertNotIn(t_b.id, mastery_a)
                self.assertAlmostEqual(mastery_a[t_a.id].mastery, 0.9, places=5)

                # Query Subject B
                mastery_b = await topic_mastery_repository.get_student_topic_mastery(
                    db, user_id=user.id, subject_id=sub_b.id
                )
                self.assertIn(t_b.id, mastery_b)
                self.assertNotIn(t_a.id, mastery_b)
                self.assertAlmostEqual(mastery_b[t_b.id].mastery, 0.2, places=5)

        self.loop.run_until_complete(_run())

    def test_06_no_student_data_falls_back_to_mode_b(self) -> None:
        """
        Verify that when no student evaluation data exists:
        - has_student_data is False
        - student_mastery is None
        - weakness_score is None
        - Mode B formula is applied: P = 0.60 * F + 0.40 * M
        """
        async def _run():
            async with SessionLocal() as db:
                user = User(
                    email=f"nostudent_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="pass",
                    full_name="No Student Data",
                    role="student",
                )
                subject = Subject(
                    code=f"CS-NOMAST-{uuid.uuid4().hex[:4].upper()}",
                    name="No Student Data Subject",
                    semester=6,
                    branch="Computer Engineering",
                )
                db.add_all([user, subject])
                await db.commit()

                t1 = CanonicalTopic(
                    subject_id=subject.id,
                    canonical_label="Operating Systems",
                    normalized_label="operating systems",
                )
                db.add(t1)
                await db.flush()

                v1 = QuestionVariant(
                    subject_id=subject.id,
                    topic_id=t1.id,
                    text="Explain process states.",
                    normalized_text="explain process states",
                    normalized_hash=uuid.uuid4().hex,
                )
                paper = PYQPaper(subject_id=subject.id, title="Paper 2023", exam_year=2023)
                db.add_all([v1, paper])
                await db.flush()

                occ = PYQQuestionOccurrence(
                    paper_id=paper.id, variant_id=v1.id, marks_weight=10, source_text=v1.text
                )
                db.add(occ)
                await db.commit()

                report = await analytics_service.get_exam_priority_report(
                    db=db, user_id=user.id, subject_id=subject.id
                )

                self.assertFalse(report.has_student_data)
                self.assertEqual(len(report.topics), 1)

                topic_res = report.topics[0]
                self.assertIsNone(topic_res.student_mastery)
                self.assertIsNone(topic_res.weakness_score)
                self.assertEqual(topic_res.evaluation_count, 0)
                self.assertFalse(topic_res.has_student_data)
                # Mode B: 0.60 * 1.0 + 0.40 * 1.0 = 1.000
                self.assertEqual(topic_res.priority_score, 1.000)
                self.assertEqual(topic_res.priority_label, "Very High")
                self.assertEqual(
                    topic_res.evidence.mastery_rationale,
                    "Student mastery is unavailable because no evaluated answers exist for this topic.",
                )

        self.loop.run_until_complete(_run())

    def test_07_zero_pyq_topic_handling(self) -> None:
        """
        Verify Mode C behavior for topics with zero PYQ occurrences:
        - With student mastery (0.2, weakness 0.8): P_t = 0.30 * 0.8 = 0.240 ("Low")
        - Without student mastery: P_t = 0.000 ("Low")
        """
        async def _run():
            async with SessionLocal() as db:
                user = User(
                    email=f"zeropyq_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="pass",
                    full_name="Zero PYQ Tester",
                    role="student",
                )
                subject = Subject(
                    code=f"CS-ZEROPYQ-{uuid.uuid4().hex[:4].upper()}",
                    name="Zero PYQ Subject",
                    semester=6,
                    branch="Computer Engineering",
                )
                db.add_all([user, subject])
                await db.commit()

                q_with = Question(subject_id=subject.id, text="Syllabus Question", marks_weight=10)
                db.add(q_with)
                await db.flush()

                t_with = CanonicalTopic(
                    subject_id=subject.id,
                    canonical_label="Syllabus Topic With Mastery",
                    normalized_label="syllabus topic with mastery",
                    compatibility_question_id=q_with.id,
                )
                t_without = CanonicalTopic(
                    subject_id=subject.id,
                    canonical_label="Syllabus Topic Without Mastery",
                    normalized_label="syllabus topic without mastery",
                )
                db.add_all([t_with, t_without])
                await db.flush()

                # Evaluation on q_with: 2.0 / 10.0 = 0.2 mastery (weakness = 0.8)
                ev = AnswersEvaluation(
                    user_id=user.id,
                    question_id=q_with.id,
                    user_submitted_answer="Poor answer",
                    feedback="Weak",
                    estimated_marks=2.0,
                    max_marks=10.0,
                )
                db.add(ev)
                await db.commit()

                report = await analytics_service.get_exam_priority_report(
                    db=db, user_id=user.id, subject_id=subject.id
                )

                res_by_id = {r.topic_id: r for r in report.topics}
                r_with = res_by_id[t_with.id]
                r_without = res_by_id[t_without.id]

                # Mode C with mastery: 0.30 * 0.8 = 0.240
                self.assertEqual(r_with.total_occurrences, 0)
                self.assertEqual(r_with.student_mastery, 0.2)
                self.assertEqual(r_with.weakness_score, 0.8)
                self.assertEqual(r_with.priority_score, 0.240)
                self.assertEqual(r_with.priority_label, "Low")
                self.assertEqual(
                    r_with.evidence.recommendation,
                    "Treat this as syllabus study rather than PYQ-driven exam priority.",
                )

                # Mode C without mastery: 0.000
                self.assertEqual(r_without.total_occurrences, 0)
                self.assertIsNone(r_without.student_mastery)
                self.assertEqual(r_without.priority_score, 0.000)
                self.assertEqual(r_without.priority_label, "Low")

        self.loop.run_until_complete(_run())

    def test_08_unresolved_variants_not_assigned_to_topics(self) -> None:
        """
        Verify that unresolved QuestionVariants (topic_id is None):
        1. Are never included in any canonical topic's aggregation.
        2. Are reflected in unresolved_occurrences_count.
        """
        async def _run():
            async with SessionLocal() as db:
                user = User(
                    email=f"unres_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="pass",
                    full_name="Unresolved Tester",
                    role="student",
                )
                subject = Subject(
                    code=f"CS-UNRES-{uuid.uuid4().hex[:4].upper()}",
                    name="Unresolved Subject",
                    semester=6,
                    branch="Computer Engineering",
                )
                db.add_all([user, subject])
                await db.commit()

                # One resolved topic
                topic = CanonicalTopic(
                    subject_id=subject.id,
                    canonical_label="Resolved Topic",
                    normalized_label="resolved topic",
                )
                db.add(topic)
                await db.flush()

                v_res = QuestionVariant(
                    subject_id=subject.id,
                    topic_id=topic.id,
                    text="Resolved text",
                    normalized_text="resolved text",
                    normalized_hash=uuid.uuid4().hex,
                )
                # One UNRESOLVED variant
                v_unres = QuestionVariant(
                    subject_id=subject.id,
                    topic_id=None,
                    text="Ambiguous text",
                    normalized_text="ambiguous text",
                    normalized_hash=uuid.uuid4().hex,
                    resolution_type="unresolved",
                )
                paper = PYQPaper(subject_id=subject.id, title="Paper 2023", exam_year=2023)
                db.add_all([v_res, v_unres, paper])
                await db.flush()

                occ_res = PYQQuestionOccurrence(paper_id=paper.id, variant_id=v_res.id, marks_weight=10, source_text=v_res.text)
                occ_unres_1 = PYQQuestionOccurrence(paper_id=paper.id, variant_id=v_unres.id, marks_weight=5, source_text=v_unres.text)
                occ_unres_2 = PYQQuestionOccurrence(paper_id=paper.id, variant_id=v_unres.id, marks_weight=5, source_text=v_unres.text)
                db.add_all([occ_res, occ_unres_1, occ_unres_2])
                await db.commit()

                report = await analytics_service.get_exam_priority_report(
                    db=db, user_id=user.id, subject_id=subject.id
                )

                # Resolved topic total occurrences must only be 1 (does not include unresolved)
                self.assertEqual(len(report.topics), 1)
                self.assertEqual(report.topics[0].total_occurrences, 1)
                # Unresolved occurrences count must be exactly 2
                self.assertEqual(report.unresolved_occurrences_count, 2)

        self.loop.run_until_complete(_run())

    def test_09_invalid_and_out_of_range_marks_clamped_and_ignored(self) -> None:
        """
        Verify:
        - max_marks <= 0 is completely ignored.
        - estimated_marks > max_marks is clamped to 1.0.
        - estimated_marks < 0 is clamped to 0.0.
        """
        async def _run():
            async with SessionLocal() as db:
                user = User(
                    email=f"clamp_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="pass",
                    full_name="Clamp Tester",
                    role="student",
                )
                subject = Subject(
                    code=f"CS-CLMP-{uuid.uuid4().hex[:4].upper()}",
                    name="Clamping Subject",
                    semester=6,
                    branch="Computer Engineering",
                )
                db.add_all([user, subject])
                await db.commit()

                q = Question(subject_id=subject.id, text="Clamping Question", marks_weight=10)
                db.add(q)
                await db.flush()

                topic = CanonicalTopic(
                    subject_id=subject.id,
                    canonical_label="Clamping Topic",
                    normalized_label="clamping topic",
                    compatibility_question_id=q.id,
                )
                db.add(topic)
                await db.flush()

                # 1. Invalid: max_marks = 0 -> ignored
                ev_zero = AnswersEvaluation(
                    user_id=user.id,
                    question_id=q.id,
                    user_submitted_answer="Ans 0",
                    feedback="Zero max",
                    estimated_marks=5.0,
                    max_marks=0.0,
                )
                # 2. Above: 15 / 10 -> clamped to 1.0
                ev_high = AnswersEvaluation(
                    user_id=user.id,
                    question_id=q.id,
                    user_submitted_answer="Ans high",
                    feedback="High",
                    estimated_marks=15.0,
                    max_marks=10.0,
                )
                # 3. Below: -5 / 10 -> clamped to 0.0
                ev_low = AnswersEvaluation(
                    user_id=user.id,
                    question_id=q.id,
                    user_submitted_answer="Ans low",
                    feedback="Low",
                    estimated_marks=-5.0,
                    max_marks=10.0,
                )
                db.add_all([ev_zero, ev_high, ev_low])
                await db.commit()

                mastery_map = await topic_mastery_repository.get_student_topic_mastery(
                    db, user_id=user.id, subject_id=subject.id
                )

                self.assertIn(topic.id, mastery_map)
                # Exactly 2 valid evaluations: [1.0, 0.0] -> mean = 0.5
                self.assertEqual(mastery_map[topic.id].evaluation_count, 2)
                self.assertAlmostEqual(mastery_map[topic.id].mastery, 0.5, places=5)

        self.loop.run_until_complete(_run())

    def test_10_api_endpoint_integration_and_404(self) -> None:
        """
        Verify the FastAPI endpoint handler:
        - Returns 404 HTTPException if the subject ID does not exist.
        - Returns SubjectExamPriorityOut for a valid subject.
        """
        async def _run():
            async with SessionLocal() as db:
                user = User(
                    email=f"api_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="pass",
                    full_name="API Tester",
                    role="student",
                )
                subject = Subject(
                    code=f"CS-API-{uuid.uuid4().hex[:4].upper()}",
                    name="API Endpoint Subject",
                    semester=6,
                    branch="Computer Engineering",
                )
                db.add_all([user, subject])
                await db.commit()
                await db.refresh(user)
                await db.refresh(subject)

                # 404 test on nonexistent subject
                non_existent_id = uuid.uuid4()
                with self.assertRaises(HTTPException) as ctx:
                    await get_subject_exam_priority(
                        subject_id=non_existent_id,
                        db=db,
                        current_user=user,
                    )
                self.assertEqual(ctx.exception.status_code, 404)

                # Valid subject test
                result = await get_subject_exam_priority(
                    subject_id=subject.id,
                    db=db,
                    current_user=user,
                )
                self.assertIsInstance(result, SubjectExamPriorityOut)
                self.assertEqual(result.subject_id, subject.id)
                self.assertEqual(result.total_topics, 0)

        self.loop.run_until_complete(_run())

    def test_11_existing_analytics_endpoint_preserved(self) -> None:
        """
        Verify that the existing GET /subjects/{subject_id} endpoint
        continues to function properly without regression.
        """
        async def _run():
            async with SessionLocal() as db:
                user = User(
                    email=f"regress_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="pass",
                    full_name="Regression Tester",
                    role="student",
                )
                subject = Subject(
                    code=f"CS-REGR-{uuid.uuid4().hex[:4].upper()}",
                    name="Regression Subject",
                    semester=6,
                    branch="Computer Engineering",
                )
                db.add_all([user, subject])
                await db.commit()
                await db.refresh(user)
                await db.refresh(subject)

                report = await get_subject_analytics_report(
                    subject_id=subject.id,
                    db=db,
                    current_user=user,
                )
                self.assertIsInstance(report, SubjectAnalyticsOut)
                self.assertEqual(report.subject_id, subject.id)
                self.assertEqual(report.total_essays_evaluated, 0)

        self.loop.run_until_complete(_run())

    def test_12_query_count_and_no_n_plus_1(self) -> None:
        """
        Verify that student mastery aggregation executes in a single SQL query
        across any number of canonical topics, proving no N+1 query vulnerability.
        """
        async def _run():
            async with SessionLocal() as db:
                user = User(
                    email=f"nplus1_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="pass",
                    full_name="N+1 Tester",
                    role="student",
                )
                subject = Subject(
                    code=f"CS-N1-{uuid.uuid4().hex[:4].upper()}",
                    name="N+1 Test Subject",
                    semester=6,
                    branch="Computer Engineering",
                )
                db.add_all([user, subject])
                await db.commit()

                # Create 5 distinct topics with questions & evaluations
                for i in range(5):
                    q = Question(subject_id=subject.id, text=f"Question {i}", marks_weight=10)
                    db.add(q)
                    await db.flush()

                    topic = CanonicalTopic(
                        subject_id=subject.id,
                        canonical_label=f"Topic {i}",
                        normalized_label=f"topic {i}",
                        compatibility_question_id=q.id,
                    )
                    db.add(topic)
                    await db.flush()

                    ev = AnswersEvaluation(
                        user_id=user.id,
                        question_id=q.id,
                        user_submitted_answer=f"Answer {i}",
                        feedback="OK",
                        estimated_marks=6.0,
                        max_marks=10.0,
                    )
                    db.add(ev)

                await db.commit()

                # Track SQL queries executed during topic_mastery_repository call
                queries = []

                def _tracker(conn, cursor, statement, parameters, context, executemany):
                    queries.append(statement)

                event.listen(db.sync_session.bind, "before_cursor_execute", _tracker)
                try:
                    mastery_map = await topic_mastery_repository.get_student_topic_mastery(
                        db, user_id=user.id, subject_id=subject.id
                    )
                finally:
                    event.remove(db.sync_session.bind, "before_cursor_execute", _tracker)

                # All 5 topics must be aggregated in EXACTLY 1 query!
                self.assertEqual(len(queries), 1, f"Expected 1 query, executed {len(queries)}")
                self.assertEqual(len(mastery_map), 5)

        self.loop.run_until_complete(_run())


if __name__ == "__main__":
    unittest.main()
