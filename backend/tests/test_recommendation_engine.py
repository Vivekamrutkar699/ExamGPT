import asyncio
import math
import sys
import unittest
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from fastapi import HTTPException
import app.database.base  # noqa: F401
from app.api.v1.endpoints.analytics import get_subject_recommendations
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
from app.schemas.recommendation import (
    RecommendationAction,
    TopicRecommendationOut,
    SubjectRecommendationsOut,
)
from app.services.recommendation import (
    TopicRecommendation,
    derive_topic_recommendation,
    sort_recommendations,
    recommendation_service,
)
from app.services.analytics import analytics_service


@dataclass
class MockTopicInput:
    """Mock topic input for testing pure recommendation engine."""
    topic_id: uuid.UUID
    canonical_label: str
    unit_tag: Optional[str] = "Unit 1"
    priority_score: float = 0.80
    priority_label: str = "Very High"
    student_mastery: Optional[float] = None
    weakness_score: Optional[float] = None
    evaluation_count: int = 0
    total_occurrences: int = 5


class RecommendationEnginePureTests(unittest.TestCase):
    """
    Unit tests for the pure deterministic recommendation engine.
    Tests boundary thresholds, all cases 1 to 6, edge cases, and ordering.
    """

    def test_01_no_student_data_very_high_priority_assess(self) -> None:
        """1. No student data + Very High priority -> ASSESS"""
        topic = MockTopicInput(
            topic_id=uuid.uuid4(),
            canonical_label="Cache Memory Mapping",
            priority_score=0.90,
            priority_label="Very High",
            student_mastery=None,
        )
        rec = derive_topic_recommendation(topic)
        self.assertEqual(rec.recommended_action, RecommendationAction.ASSESS)
        self.assertEqual(rec.action_priority, 3)
        self.assertIn("High exam relevance but insufficient student performance data", rec.recommendation_reason)
        self.assertIsNone(rec.student_mastery)
        self.assertIsNone(rec.weakness_score)

    def test_02_no_student_data_medium_priority_assess(self) -> None:
        """2. No student data + Medium priority -> ASSESS"""
        topic = MockTopicInput(
            topic_id=uuid.uuid4(),
            canonical_label="Bus Arbitration",
            priority_score=0.45,
            priority_label="Medium",
            student_mastery=None,
        )
        rec = derive_topic_recommendation(topic)
        self.assertEqual(rec.recommended_action, RecommendationAction.ASSESS)
        self.assertEqual(rec.action_priority, 5)
        self.assertIn("Moderate exam relevance with no student performance data", rec.recommendation_reason)

    def test_03_no_student_data_low_priority_review(self) -> None:
        """3. No student data + Low priority -> REVIEW"""
        topic = MockTopicInput(
            topic_id=uuid.uuid4(),
            canonical_label="Historical Computing Overview",
            priority_score=0.15,
            priority_label="Low",
            student_mastery=None,
        )
        rec = derive_topic_recommendation(topic)
        self.assertEqual(rec.recommended_action, RecommendationAction.REVIEW)
        self.assertEqual(rec.action_priority, 6)
        self.assertIn("Lower exam priority with no student performance data", rec.recommendation_reason)

    def test_04_very_high_priority_mastery_0_40_practice(self) -> None:
        """4. Very High priority + mastery 0.40 -> PRACTICE"""
        topic = MockTopicInput(
            topic_id=uuid.uuid4(),
            canonical_label="Process Scheduling",
            priority_score=0.88,
            priority_label="Very High",
            student_mastery=0.40,
            weakness_score=0.60,
            evaluation_count=3,
        )
        rec = derive_topic_recommendation(topic)
        self.assertEqual(rec.recommended_action, RecommendationAction.PRACTICE)
        self.assertEqual(rec.action_priority, 1)
        self.assertIn("High exam relevance combined with low demonstrated mastery", rec.recommendation_reason)

    def test_05_high_priority_mastery_0_49_practice(self) -> None:
        """5. High priority + mastery 0.49 (boundary) -> PRACTICE"""
        topic = MockTopicInput(
            topic_id=uuid.uuid4(),
            canonical_label="Virtual Memory Paging",
            priority_score=0.65,
            priority_label="High",
            student_mastery=0.49,
            weakness_score=0.51,
            evaluation_count=2,
        )
        rec = derive_topic_recommendation(topic)
        self.assertEqual(rec.recommended_action, RecommendationAction.PRACTICE)
        self.assertEqual(rec.action_priority, 1)

    def test_06_high_priority_mastery_0_50_quiz(self) -> None:
        """6. High priority + mastery 0.50 (boundary) -> QUIZ"""
        topic = MockTopicInput(
            topic_id=uuid.uuid4(),
            canonical_label="Virtual Memory Paging",
            priority_score=0.65,
            priority_label="High",
            student_mastery=0.50,
            weakness_score=0.50,
            evaluation_count=2,
        )
        rec = derive_topic_recommendation(topic)
        self.assertEqual(rec.recommended_action, RecommendationAction.QUIZ)
        self.assertEqual(rec.action_priority, 2)
        self.assertIn("High exam relevance with partial mastery", rec.recommendation_reason)

    def test_07_high_priority_mastery_0_74_quiz(self) -> None:
        """7. High priority + mastery 0.74 (boundary) -> QUIZ"""
        topic = MockTopicInput(
            topic_id=uuid.uuid4(),
            canonical_label="Deadlock Avoidance",
            priority_score=0.70,
            priority_label="High",
            student_mastery=0.74,
            weakness_score=0.26,
            evaluation_count=4,
        )
        rec = derive_topic_recommendation(topic)
        self.assertEqual(rec.recommended_action, RecommendationAction.QUIZ)
        self.assertEqual(rec.action_priority, 2)

    def test_08_high_priority_mastery_0_75_maintain(self) -> None:
        """8. High priority + mastery 0.75 (boundary) -> MAINTAIN"""
        topic = MockTopicInput(
            topic_id=uuid.uuid4(),
            canonical_label="Deadlock Avoidance",
            priority_score=0.70,
            priority_label="High",
            student_mastery=0.75,
            weakness_score=0.25,
            evaluation_count=4,
        )
        rec = derive_topic_recommendation(topic)
        self.assertEqual(rec.recommended_action, RecommendationAction.MAINTAIN)
        self.assertEqual(rec.action_priority, 7)
        self.assertIn("High exam relevance but strong demonstrated mastery", rec.recommendation_reason)

    def test_09_medium_priority_low_mastery_practice(self) -> None:
        """9. Medium priority + low mastery -> deterministic weak-topic action (PRACTICE)"""
        topic = MockTopicInput(
            topic_id=uuid.uuid4(),
            canonical_label="DMA Controller",
            priority_score=0.45,
            priority_label="Medium",
            student_mastery=0.35,
            weakness_score=0.65,
            evaluation_count=1,
        )
        rec = derive_topic_recommendation(topic)
        self.assertEqual(rec.recommended_action, RecommendationAction.PRACTICE)
        self.assertEqual(rec.action_priority, 4)
        self.assertIn("Moderate exam relevance with demonstrated weakness", rec.recommendation_reason)

    def test_09b_medium_priority_moderate_mastery_review(self) -> None:
        """Medium priority + moderate mastery (0.50 <= m < 0.75) -> REVIEW"""
        topic = MockTopicInput(
            topic_id=uuid.uuid4(),
            canonical_label="DMA Controller",
            priority_score=0.45,
            priority_label="Medium",
            student_mastery=0.60,
            weakness_score=0.40,
            evaluation_count=2,
        )
        rec = derive_topic_recommendation(topic)
        self.assertEqual(rec.recommended_action, RecommendationAction.REVIEW)
        self.assertEqual(rec.action_priority, 6)
        self.assertIn("Moderate exam relevance with partial mastery", rec.recommendation_reason)

    def test_09c_medium_priority_strong_mastery_maintain(self) -> None:
        """Medium priority + strong mastery (m >= 0.75) -> MAINTAIN"""
        topic = MockTopicInput(
            topic_id=uuid.uuid4(),
            canonical_label="DMA Controller",
            priority_score=0.45,
            priority_label="Medium",
            student_mastery=0.85,
            weakness_score=0.15,
            evaluation_count=3,
        )
        rec = derive_topic_recommendation(topic)
        self.assertEqual(rec.recommended_action, RecommendationAction.MAINTAIN)
        self.assertEqual(rec.action_priority, 7)
        self.assertIn("Moderate exam relevance with solid mastery", rec.recommendation_reason)

    def test_10_low_priority_low_mastery_review(self) -> None:
        """10. Low priority + low mastery -> REVIEW (does not dominate high-impact topics)"""
        topic = MockTopicInput(
            topic_id=uuid.uuid4(),
            canonical_label="8085 Pin Diagram",
            priority_score=0.20,
            priority_label="Low",
            student_mastery=0.20,
            weakness_score=0.80,
            evaluation_count=1,
        )
        rec = derive_topic_recommendation(topic)
        self.assertEqual(rec.recommended_action, RecommendationAction.REVIEW)
        self.assertEqual(rec.action_priority, 6)
        self.assertIn("Demonstrated weakness exists, but the topic has lower exam priority", rec.recommendation_reason)

    def test_11_low_priority_strong_mastery_maintain(self) -> None:
        """11. Low priority + strong mastery -> MAINTAIN"""
        topic = MockTopicInput(
            topic_id=uuid.uuid4(),
            canonical_label="8085 Pin Diagram",
            priority_score=0.20,
            priority_label="Low",
            student_mastery=0.80,
            weakness_score=0.20,
            evaluation_count=2,
        )
        rec = derive_topic_recommendation(topic)
        self.assertEqual(rec.recommended_action, RecommendationAction.MAINTAIN)
        self.assertEqual(rec.action_priority, 7)
        self.assertIn("Lower exam priority with satisfactory mastery", rec.recommendation_reason)

    def test_12_recommendation_reason_is_deterministic(self) -> None:
        """12. Recommendation reason is deterministic and non-LLM template."""
        topic = MockTopicInput(
            topic_id=uuid.uuid4(),
            canonical_label="Pipelining Hazards",
            priority_score=0.82,
            priority_label="Very High",
            student_mastery=0.30,
        )
        rec1 = derive_topic_recommendation(topic)
        rec2 = derive_topic_recommendation(topic)
        self.assertEqual(rec1.recommendation_reason, rec2.recommendation_reason)
        self.assertEqual(rec1.recommended_action, rec2.recommended_action)
        self.assertEqual(rec1.action_priority, rec2.action_priority)

    def test_13_recommendation_ordering_is_deterministic(self) -> None:
        """13. Recommendation ordering is deterministic across action priority tiers and tie-breakers."""
        # Tier 1: High Priority Practice
        t_high_practice = TopicRecommendation(
            topic_id=uuid.uuid4(),
            canonical_label="TCP Congestion Control",
            unit_tag="Unit 4",
            priority_score=0.85,
            priority_label="Very High",
            student_mastery=0.30,
            weakness_score=0.70,
            evaluation_count=2,
            recommended_action=RecommendationAction.PRACTICE,
            recommendation_reason="reason",
            action_priority=1,
            total_occurrences=6,
        )
        # Tier 2: High Priority Quiz
        t_high_quiz = TopicRecommendation(
            topic_id=uuid.uuid4(),
            canonical_label="Routing Algorithms",
            unit_tag="Unit 3",
            priority_score=0.80,
            priority_label="High",
            student_mastery=0.60,
            weakness_score=0.40,
            evaluation_count=2,
            recommended_action=RecommendationAction.QUIZ,
            recommendation_reason="reason",
            action_priority=2,
            total_occurrences=5,
        )
        # Tier 3: High Priority Assess
        t_high_assess = TopicRecommendation(
            topic_id=uuid.uuid4(),
            canonical_label="Subnetting",
            unit_tag="Unit 2",
            priority_score=0.78,
            priority_label="High",
            student_mastery=None,
            weakness_score=None,
            evaluation_count=0,
            recommended_action=RecommendationAction.ASSESS,
            recommendation_reason="reason",
            action_priority=3,
            total_occurrences=4,
        )
        # Tier 4: Medium Priority Practice
        t_med_practice = TopicRecommendation(
            topic_id=uuid.uuid4(),
            canonical_label="Sliding Window Protocol",
            unit_tag="Unit 2",
            priority_score=0.50,
            priority_label="Medium",
            student_mastery=0.25,
            weakness_score=0.75,
            evaluation_count=1,
            recommended_action=RecommendationAction.PRACTICE,
            recommendation_reason="reason",
            action_priority=4,
            total_occurrences=3,
        )
        # Tier 7: Maintain
        t_maintain = TopicRecommendation(
            topic_id=uuid.uuid4(),
            canonical_label="OSI Model Layers",
            unit_tag="Unit 1",
            priority_score=0.75,
            priority_label="High",
            student_mastery=0.90,
            weakness_score=0.10,
            evaluation_count=5,
            recommended_action=RecommendationAction.MAINTAIN,
            recommendation_reason="reason",
            action_priority=7,
            total_occurrences=7,
        )

        input_list = [t_maintain, t_med_practice, t_high_assess, t_high_quiz, t_high_practice]
        sorted_list = sort_recommendations(input_list)

        expected_order = [
            t_high_practice.canonical_label,
            t_high_quiz.canonical_label,
            t_high_assess.canonical_label,
            t_med_practice.canonical_label,
            t_maintain.canonical_label,
        ]
        actual_order = [item.canonical_label for item in sorted_list]
        self.assertEqual(actual_order, expected_order)

    def test_13b_tier_tiebreaking(self) -> None:
        """Same action priority tier sorts by priority_score desc, occurrences desc, label asc."""
        t1 = TopicRecommendation(
            topic_id=uuid.uuid4(),
            canonical_label="Beta Topic",
            unit_tag="Unit 1",
            priority_score=0.85,
            priority_label="Very High",
            student_mastery=0.30,
            weakness_score=0.70,
            evaluation_count=2,
            recommended_action=RecommendationAction.PRACTICE,
            recommendation_reason="reason",
            action_priority=1,
            total_occurrences=4,
        )
        t2 = TopicRecommendation(
            topic_id=uuid.uuid4(),
            canonical_label="Alpha Topic",
            unit_tag="Unit 1",
            priority_score=0.85,
            priority_label="Very High",
            student_mastery=0.30,
            weakness_score=0.70,
            evaluation_count=2,
            recommended_action=RecommendationAction.PRACTICE,
            recommendation_reason="reason",
            action_priority=1,
            total_occurrences=4,
        )
        t3 = TopicRecommendation(
            topic_id=uuid.uuid4(),
            canonical_label="Gamma Topic",
            unit_tag="Unit 1",
            priority_score=0.90,  # Higher score
            priority_label="Very High",
            student_mastery=0.20,
            weakness_score=0.80,
            evaluation_count=2,
            recommended_action=RecommendationAction.PRACTICE,
            recommendation_reason="reason",
            action_priority=1,
            total_occurrences=2,
        )

        sorted_recs = sort_recommendations([t1, t2, t3])
        # t3 has highest priority score (0.90) -> 1st
        # t1 and t2 tie on score (0.85) and occurrences (4), so alphabetical: Alpha Topic before Beta Topic
        self.assertEqual(sorted_recs[0].canonical_label, "Gamma Topic")
        self.assertEqual(sorted_recs[1].canonical_label, "Alpha Topic")
        self.assertEqual(sorted_recs[2].canonical_label, "Beta Topic")

    def test_14_multiple_topics_independently_recommended(self) -> None:
        """14. Multiple topics are independently evaluated without cross-topic pollution."""
        topics = [
            MockTopicInput(uuid.uuid4(), "Topic A", priority_label="Very High", student_mastery=0.2),
            MockTopicInput(uuid.uuid4(), "Topic B", priority_label="Very High", student_mastery=0.8),
            MockTopicInput(uuid.uuid4(), "Topic C", priority_label="Low", student_mastery=None),
        ]
        recs = [derive_topic_recommendation(t) for t in topics]
        self.assertEqual(recs[0].recommended_action, RecommendationAction.PRACTICE)
        self.assertEqual(recs[1].recommended_action, RecommendationAction.MAINTAIN)
        self.assertEqual(recs[2].recommended_action, RecommendationAction.REVIEW)

    def test_15_edge_cases_handling(self) -> None:
        """Handle extreme numeric boundaries: 0.0, 1.0, non-finite, and empty lists."""
        # Mastery 0.0
        t_zero = MockTopicInput(uuid.uuid4(), "Zero Mastery", priority_label="High", student_mastery=0.0)
        rec_zero = derive_topic_recommendation(t_zero)
        self.assertEqual(rec_zero.recommended_action, RecommendationAction.PRACTICE)
        self.assertEqual(rec_zero.student_mastery, 0.0)

        # Mastery 1.0
        t_one = MockTopicInput(uuid.uuid4(), "Perfect Mastery", priority_label="High", student_mastery=1.0)
        rec_one = derive_topic_recommendation(t_one)
        self.assertEqual(rec_one.recommended_action, RecommendationAction.MAINTAIN)
        self.assertEqual(rec_one.student_mastery, 1.0)

        # Non-finite values
        t_nan = MockTopicInput(
            uuid.uuid4(),
            "NaN Mastery",
            priority_score=float("nan"),
            priority_label="High",
            student_mastery=float("inf"),
        )
        rec_nan = derive_topic_recommendation(t_nan)
        self.assertIsNotNone(rec_nan.recommended_action)
        self.assertIsNone(rec_nan.student_mastery)
        self.assertEqual(rec_nan.priority_score, 0.0)

        # Empty sort
        self.assertEqual(sort_recommendations([]), [])


class RecommendationEngineIntegrationTests(unittest.TestCase):
    """
    Integration tests for RecommendationService and API endpoint.
    Tests student isolation, subject isolation, 404 validation, and response schema.
    """

    def setUp(self) -> None:
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self) -> None:
        self.loop.close()

    def test_16_student_isolation(self) -> None:
        """16. Student A's weakness triggers PRACTICE while Student B (no data) gets ASSESS on the same topic."""
        async def _run():
            async with SessionLocal() as db:
                # Create subject
                subject = Subject(
                    code=f"ISO-{uuid.uuid4().hex[:4]}",
                    name="Student Isolation Subject",
                    semester=5,
                    branch="Computer Engineering",
                )
                student_a = User(
                    email=f"stu_a_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="hashed_password",
                    full_name="Student A",
                    role="student",
                )
                student_b = User(
                    email=f"stu_b_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="hashed_password",
                    full_name="Student B",
                    role="student",
                )
                db.add_all([subject, student_a, student_b])
                await db.commit()
                await db.refresh(subject)
                await db.refresh(student_a)
                await db.refresh(student_b)

                # Canonical topic
                topic = CanonicalTopic(
                    subject_id=subject.id,
                    canonical_label="B-Trees Indexing",
                    normalized_label="b-trees indexing",
                    unit_tag="Unit 2",
                )
                db.add(topic)
                await db.flush()

                # PYQ Occurrence
                paper = PYQPaper(
                    subject_id=subject.id,
                    title="May 2023 Endsem",
                    exam_session="DEC_JAN",
                    exam_year=2023,
                )
                db.add(paper)
                await db.flush()

                q = Question(subject_id=subject.id, text="Explain B-Tree insertion.", marks_weight=10)
                db.add(q)
                await db.flush()

                v = QuestionVariant(
                    subject_id=subject.id,
                    topic_id=topic.id,
                    legacy_question_id=q.id,
                    text=q.text,
                    normalized_text="explain b-tree insertion",
                    normalized_hash=uuid.uuid4().hex,
                    resolution_type="exact_match",
                )
                db.add(v)
                await db.flush()

                occ = PYQQuestionOccurrence(
                    paper_id=paper.id,
                    variant_id=v.id,
                    question_number="Q3a",
                    source_text=q.text,
                    marks_weight=10,
                )
                db.add(occ)

                # Student A evaluated with low score: 2.0 / 10.0 = 0.20
                eval_a = AnswersEvaluation(
                    user_id=student_a.id,
                    question_id=q.id,
                    user_submitted_answer="Partial attempt on B-Trees.",
                    feedback="Incomplete answer.",
                    estimated_marks=2.0,
                    max_marks=10.0,
                )
                db.add(eval_a)
                await db.commit()

                # Student A recommendations
                res_a = await recommendation_service.get_subject_recommendations(
                    db=db, user_id=student_a.id, subject_id=subject.id
                )
                self.assertTrue(res_a.has_student_data)
                self.assertEqual(len(res_a.recommendations), 1)
                rec_a = res_a.recommendations[0]
                self.assertEqual(rec_a.recommended_action, RecommendationAction.PRACTICE)
                self.assertEqual(rec_a.student_mastery, 0.20)

                # Student B recommendations (no evaluations)
                res_b = await recommendation_service.get_subject_recommendations(
                    db=db, user_id=student_b.id, subject_id=subject.id
                )
                self.assertFalse(res_b.has_student_data)
                self.assertEqual(len(res_b.recommendations), 1)
                rec_b = res_b.recommendations[0]
                self.assertEqual(rec_b.recommended_action, RecommendationAction.ASSESS)
                self.assertIsNone(rec_b.student_mastery)

        self.loop.run_until_complete(_run())

    def test_17_subject_isolation(self) -> None:
        """17. Recommendations for Subject 1 do not contain topics from Subject 2."""
        async def _run():
            async with SessionLocal() as db:
                user = User(
                    email=f"sub_iso_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="hashed_password",
                    full_name="Isolation Tester",
                    role="student",
                )
                subj1 = Subject(
                    code=f"SUB1-{uuid.uuid4().hex[:4]}",
                    name="Subject One",
                    semester=3,
                    branch="Computer Engineering",
                )
                subj2 = Subject(
                    code=f"SUB2-{uuid.uuid4().hex[:4]}",
                    name="Subject Two",
                    semester=3,
                    branch="Computer Engineering",
                )
                db.add_all([user, subj1, subj2])
                await db.commit()
                await db.refresh(user)
                await db.refresh(subj1)
                await db.refresh(subj2)

                top1 = CanonicalTopic(
                    subject_id=subj1.id,
                    canonical_label="Subject 1 Exclusive Topic",
                    normalized_label="subject 1 exclusive topic",
                )
                top2 = CanonicalTopic(
                    subject_id=subj2.id,
                    canonical_label="Subject 2 Exclusive Topic",
                    normalized_label="subject 2 exclusive topic",
                )
                db.add_all([top1, top2])
                await db.commit()

                res1 = await recommendation_service.get_subject_recommendations(
                    db=db, user_id=user.id, subject_id=subj1.id
                )
                res2 = await recommendation_service.get_subject_recommendations(
                    db=db, user_id=user.id, subject_id=subj2.id
                )

                labels1 = [r.canonical_label for r in res1.recommendations]
                labels2 = [r.canonical_label for r in res2.recommendations]

                self.assertIn("Subject 1 Exclusive Topic", labels1)
                self.assertNotIn("Subject 2 Exclusive Topic", labels1)
                self.assertIn("Subject 2 Exclusive Topic", labels2)
                self.assertNotIn("Subject 1 Exclusive Topic", labels2)

        self.loop.run_until_complete(_run())

    def test_18_subject_404_validation(self) -> None:
        """18. Non-existent subject ID returns HTTP 404."""
        async def _run():
            async with SessionLocal() as db:
                user = User(
                    email=f"user_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="hashed_password",
                    full_name="Tester",
                    role="student",
                )
                db.add(user)
                await db.commit()
                await db.refresh(user)

                non_existent_id = uuid.uuid4()
                with self.assertRaises(HTTPException) as ctx:
                    await get_subject_recommendations(
                        subject_id=non_existent_id,
                        db=db,
                        current_user=user,
                    )
                self.assertEqual(ctx.exception.status_code, 404)
                self.assertIn("Course Subject ID does not exist", ctx.exception.detail)

        self.loop.run_until_complete(_run())

    def test_19_api_endpoint_response_contract(self) -> None:
        """19. Endpoint returns valid SubjectRecommendationsOut schema matching API contract."""
        async def _run():
            async with SessionLocal() as db:
                user = User(
                    email=f"api_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="hashed_password",
                    full_name="API Tester",
                    role="student",
                )
                subject = Subject(
                    code=f"API-{uuid.uuid4().hex[:4]}",
                    name="API Contract Subject",
                    semester=4,
                    branch="Computer Engineering",
                )
                db.add_all([user, subject])
                await db.commit()
                await db.refresh(user)
                await db.refresh(subject)

                topic = CanonicalTopic(
                    subject_id=subject.id,
                    canonical_label="Paging Mechanics",
                    normalized_label="paging mechanics",
                    unit_tag="Unit 3",
                )
                db.add(topic)
                await db.commit()

                # Call endpoint handler directly
                result = await get_subject_recommendations(
                    subject_id=subject.id,
                    db=db,
                    current_user=user,
                )

                self.assertIsInstance(result, SubjectRecommendationsOut)
                self.assertEqual(result.subject_id, subject.id)
                self.assertIsInstance(result.has_student_data, bool)
                self.assertEqual(result.total_recommendations, len(result.recommendations))
                if result.recommendations:
                    rec = result.recommendations[0]
                    self.assertIsInstance(rec, TopicRecommendationOut)
                    self.assertIn(rec.recommended_action, list(RecommendationAction))
                    self.assertIsInstance(rec.recommendation_reason, str)
                    self.assertIsInstance(rec.action_priority, int)

        self.loop.run_until_complete(_run())

    def test_20_existing_exam_priority_remains_unchanged(self) -> None:
        """20. Ensure existing analytics_service.get_exam_priority_report behavior is unaffected."""
        async def _run():
            async with SessionLocal() as db:
                user = User(
                    email=f"prio_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="hashed_password",
                    full_name="Priority Tester",
                    role="student",
                )
                subject = Subject(
                    code=f"PRIO-{uuid.uuid4().hex[:4]}",
                    name="Priority Preserved Subject",
                    semester=4,
                    branch="Computer Engineering",
                )
                db.add_all([user, subject])
                await db.commit()
                await db.refresh(user)
                await db.refresh(subject)

                prio_report = await analytics_service.get_exam_priority_report(
                    db=db, user_id=user.id, subject_id=subject.id
                )
                self.assertEqual(prio_report.subject_id, subject.id)
                self.assertFalse(prio_report.has_student_data)
                self.assertIsInstance(prio_report.topics, list)

        self.loop.run_until_complete(_run())


if __name__ == "__main__":
    unittest.main()
