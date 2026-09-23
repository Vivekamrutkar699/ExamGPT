import asyncio
import sys
import unittest
import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from fastapi import HTTPException
from sqlalchemy import func, select
import app.database.base  # noqa: F401
from app.api.v1.endpoints.analytics import (
    execute_topic_recommendation_action,
    get_subject_recommendations,
)
from app.database.session import SessionLocal
from app.models.answers_evaluation import AnswersEvaluation
from app.models.chunk import Chunk
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
from app.schemas.recommendation import (
    RecommendationAction,
    SubjectRecommendationsOut,
    TopicActionResponse,
)
from app.services.recommendation import recommendation_service
from app.services.quiz import quiz_service


class RecommendationActionsIntegrationTests(unittest.TestCase):
    """
    Phase 7D Test Suite: Connecting Personalized Recommendations to Learning Actions.
    Tests verify:
    1. PRACTICE action execution and payload
    2. QUIZ action execution and worksheet generation
    3. ASSESS action execution and diagnostic assessment
    4. REVIEW action execution and syllabus/notes retrieval
    5. MAINTAIN action execution and lightweight revision
    6. Student isolation (different actions for different mastery on same topic)
    7. Topic isolation (mismatched subject/topic returns 404)
    8. Subject 404 and invalid topic 404 handling
    9. Compatibility with GET /recommendations endpoint and action_endpoint discovery
    """

    def setUp(self) -> None:
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self) -> None:
        self.loop.close()

    def test_01_practice_action_provides_practice_questions(self) -> None:
        """PRACTICE action returns topic-linked questions with marks and evaluation submission endpoint."""
        async def _run():
            async with SessionLocal() as db:
                subject = Subject(
                    code=f"PRAC-{uuid.uuid4().hex[:4]}",
                    name="Practice Action Subject",
                    semester=6,
                    branch="Computer Engineering",
                )
                user = User(
                    email=f"prac_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="hashed_password",
                    full_name="Practice Student",
                    role="student",
                )
                db.add_all([subject, user])
                await db.commit()
                await db.refresh(subject)
                await db.refresh(user)

                topic = CanonicalTopic(
                    subject_id=subject.id,
                    canonical_label="Process Synchronization Semaphores",
                    normalized_label="process synchronization semaphores",
                    unit_tag="Unit 2",
                )
                db.add(topic)
                await db.flush()

                paper = PYQPaper(
                    subject_id=subject.id,
                    title="May 2023 Paper",
                    exam_session="MAY_JUN",
                    exam_year=2023,
                )
                db.add(paper)
                await db.flush()

                q = Question(
                    subject_id=subject.id,
                    text="Explain the Producer-Consumer problem using counting semaphores.",
                    marks_weight=10,
                    unit_tag="Unit 2",
                )
                db.add(q)
                await db.flush()

                v = QuestionVariant(
                    subject_id=subject.id,
                    topic_id=topic.id,
                    legacy_question_id=q.id,
                    text=q.text,
                    normalized_text="explain producer consumer problem counting semaphores",
                    normalized_hash=uuid.uuid4().hex,
                    resolution_type="exact_match",
                )
                db.add(v)
                await db.flush()

                occ = PYQQuestionOccurrence(
                    paper_id=paper.id,
                    variant_id=v.id,
                    question_number="Q2a",
                    source_text=q.text,
                    marks_weight=10,
                )
                db.add(occ)

                # Low mastery: 2.0 / 10.0 = 0.20 (< 0.50) -> triggers PRACTICE
                ev = AnswersEvaluation(
                    user_id=user.id,
                    question_id=q.id,
                    user_submitted_answer="Semaphores are integers.",
                    feedback="Weak explanation.",
                    estimated_marks=2.0,
                    max_marks=10.0,
                )
                db.add(ev)
                await db.commit()

                # Execute action
                res = await execute_topic_recommendation_action(
                    subject_id=subject.id,
                    topic_id=topic.id,
                    db=db,
                    current_user=user,
                )

                self.assertIsInstance(res, TopicActionResponse)
                self.assertEqual(res.subject_id, subject.id)
                self.assertEqual(res.topic_id, topic.id)
                self.assertEqual(res.action, RecommendationAction.PRACTICE)
                self.assertEqual(res.action_priority, 1)
                self.assertIsNotNone(res.practice_data)
                self.assertGreaterEqual(len(res.practice_data), 1)
                self.assertEqual(res.practice_data[0].question_id, q.id)
                self.assertEqual(res.practice_data[0].marks_weight, 10)
                self.assertEqual(res.practice_data[0].source_scope, "topic")
                self.assertEqual(res.practice_data[0].submission_endpoint, "/api/v1/evaluations/")

        self.loop.run_until_complete(_run())

    def test_02_quiz_action_generates_topic_quiz(self) -> None:
        """QUIZ action generates an MCQ quiz worksheet with submit endpoint for partial mastery."""
        async def _run():
            async with SessionLocal() as db:
                subject = Subject(
                    code=f"QUIZ-{uuid.uuid4().hex[:4]}",
                    name="Quiz Action Subject",
                    semester=6,
                    branch="Computer Engineering",
                )
                user = User(
                    email=f"quiz_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="hashed_password",
                    full_name="Quiz Student",
                    role="student",
                )
                db.add_all([subject, user])
                await db.commit()
                await db.refresh(subject)
                await db.refresh(user)

                topic = CanonicalTopic(
                    subject_id=subject.id,
                    canonical_label="Deadlock Detection Algorithms",
                    normalized_label="deadlock detection algorithms",
                    unit_tag="Unit 3",
                )
                db.add(topic)
                await db.flush()

                paper = PYQPaper(
                    subject_id=subject.id,
                    title="Dec 2023 Paper",
                    exam_session="DEC_JAN",
                    exam_year=2023,
                )
                db.add(paper)
                await db.flush()

                q = Question(
                    subject_id=subject.id,
                    text="Explain Resource Allocation Graph for deadlock detection.",
                    marks_weight=10,
                    unit_tag="Unit 3",
                )
                db.add(q)
                await db.flush()

                v = QuestionVariant(
                    subject_id=subject.id,
                    topic_id=topic.id,
                    legacy_question_id=q.id,
                    text=q.text,
                    normalized_text="explain resource allocation graph deadlock detection",
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

                # Moderate mastery: 6.0 / 10.0 = 0.60 (0.50 <= m < 0.75) -> triggers QUIZ
                ev = AnswersEvaluation(
                    user_id=user.id,
                    question_id=q.id,
                    user_submitted_answer="RAG detects cycles for single-unit resources.",
                    feedback="Partial explanation.",
                    estimated_marks=6.0,
                    max_marks=10.0,
                )
                db.add(ev)
                await db.commit()

                res = await execute_topic_recommendation_action(
                    subject_id=subject.id,
                    topic_id=topic.id,
                    db=db,
                    current_user=user,
                )

                self.assertEqual(res.action, RecommendationAction.QUIZ)
                self.assertEqual(res.action_priority, 2)
                self.assertIsNotNone(res.quiz_data)
                self.assertEqual(res.quiz_data.quiz_type, "MCQ")
                self.assertIn("submit", res.quiz_data.submission_endpoint)
                self.assertGreaterEqual(res.quiz_data.total_questions, 1)

        self.loop.run_until_complete(_run())

    def test_03_assess_action_generates_diagnostic_assessment(self) -> None:
        """ASSESS action generates a diagnostic assessment quiz when no student data exists."""
        async def _run():
            async with SessionLocal() as db:
                subject = Subject(
                    code=f"ASSESS-{uuid.uuid4().hex[:4]}",
                    name="Assess Action Subject",
                    semester=6,
                    branch="Computer Engineering",
                )
                user = User(
                    email=f"assess_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="hashed_password",
                    full_name="Assess Student",
                    role="student",
                )
                db.add_all([subject, user])
                await db.commit()
                await db.refresh(subject)
                await db.refresh(user)

                topic = CanonicalTopic(
                    subject_id=subject.id,
                    canonical_label="Virtual Memory Demand Paging",
                    normalized_label="virtual memory demand paging",
                    unit_tag="Unit 4",
                )
                db.add(topic)
                await db.flush()

                paper = PYQPaper(
                    subject_id=subject.id,
                    title="Dec 2023 Paper",
                    exam_session="DEC_JAN",
                    exam_year=2023,
                )
                db.add(paper)
                await db.flush()

                q = Question(
                    subject_id=subject.id,
                    text="Describe the page fault handling routine.",
                    marks_weight=10,
                    unit_tag="Unit 4",
                )
                db.add(q)
                await db.flush()

                v = QuestionVariant(
                    subject_id=subject.id,
                    topic_id=topic.id,
                    legacy_question_id=q.id,
                    text=q.text,
                    normalized_text="describe page fault handling routine",
                    normalized_hash=uuid.uuid4().hex,
                    resolution_type="exact_match",
                )
                db.add(v)
                await db.flush()

                occ = PYQQuestionOccurrence(
                    paper_id=paper.id,
                    variant_id=v.id,
                    question_number="Q4a",
                    source_text=q.text,
                    marks_weight=10,
                )
                db.add(occ)
                await db.commit()

                # User has NO evaluations -> triggers ASSESS
                res = await execute_topic_recommendation_action(
                    subject_id=subject.id,
                    topic_id=topic.id,
                    db=db,
                    current_user=user,
                )

                self.assertEqual(res.action, RecommendationAction.ASSESS)
                self.assertEqual(res.action_priority, 3)
                self.assertIsNotNone(res.quiz_data)
                self.assertIn("Diagnostic Assessment", res.quiz_data.title)
                self.assertIn("submit", res.quiz_data.submission_endpoint)

        self.loop.run_until_complete(_run())

    def test_04_review_action_returns_study_material_and_chunks(self) -> None:
        """REVIEW action returns syllabus summary, key concepts, and document chunks."""
        async def _run():
            async with SessionLocal() as db:
                subject = Subject(
                    code=f"REV-{uuid.uuid4().hex[:4]}",
                    name="Review Action Subject",
                    semester=6,
                    branch="Computer Engineering",
                )
                user = User(
                    email=f"rev_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="hashed_password",
                    full_name="Review Student",
                    role="student",
                )
                db.add_all([subject, user])
                await db.commit()
                await db.refresh(subject)
                await db.refresh(user)

                # Low priority topic (0 occurrences) -> triggers REVIEW
                topic = CanonicalTopic(
                    subject_id=subject.id,
                    canonical_label="History of Operating Systems",
                    normalized_label="history of operating systems",
                    unit_tag="Unit 1",
                )
                db.add(topic)
                await db.flush()

                # Add a document and chunk for review
                doc = Document(
                    subject_id=subject.id,
                    name="os_intro.pdf",
                    storage_path="mock/os_intro.pdf",
                    file_type="pdf",
                    category="notes",
                    processing_status="completed",
                )
                db.add(doc)
                await db.flush()

                chunk = Chunk(
                    document_id=doc.id,
                    chunk_index=1,
                    content="The history of operating systems begins with early mainframes and batch processing.",
                    section_title="OS Evolution",
                    unit_tag="Unit 1",
                    metadata_json={"page": 2},
                )
                db.add(chunk)
                await db.commit()

                res = await execute_topic_recommendation_action(
                    subject_id=subject.id,
                    topic_id=topic.id,
                    db=db,
                    current_user=user,
                )

                self.assertEqual(res.action, RecommendationAction.REVIEW)
                self.assertEqual(res.action_priority, 6)
                self.assertIsNotNone(res.review_data)
                self.assertIn("History of Operating Systems", res.review_data.summary)
                self.assertEqual(len(res.review_data.key_concepts), 0)

        self.loop.run_until_complete(_run())

    def test_05_maintain_action_returns_takeaways_and_refresher(self) -> None:
        """MAINTAIN action returns key takeaways, quick revision notes, and sample question."""
        async def _run():
            async with SessionLocal() as db:
                subject = Subject(
                    code=f"MAINT-{uuid.uuid4().hex[:4]}",
                    name="Maintain Action Subject",
                    semester=6,
                    branch="Computer Engineering",
                )
                user = User(
                    email=f"maint_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="hashed_password",
                    full_name="Maintain Student",
                    role="student",
                )
                db.add_all([subject, user])
                await db.commit()
                await db.refresh(subject)
                await db.refresh(user)

                topic = CanonicalTopic(
                    subject_id=subject.id,
                    canonical_label="CPU Scheduling Algorithms",
                    normalized_label="cpu scheduling algorithms",
                    unit_tag="Unit 2",
                )
                db.add(topic)
                await db.flush()

                paper = PYQPaper(
                    subject_id=subject.id,
                    title="Dec 2023 Paper",
                    exam_session="DEC_JAN",
                    exam_year=2023,
                )
                db.add(paper)
                await db.flush()

                q = Question(
                    subject_id=subject.id,
                    text="Compare FCFS and SJF scheduling algorithms.",
                    marks_weight=10,
                    unit_tag="Unit 2",
                )
                db.add(q)
                await db.flush()

                v = QuestionVariant(
                    subject_id=subject.id,
                    topic_id=topic.id,
                    legacy_question_id=q.id,
                    text=q.text,
                    normalized_text="compare fcfs sjf scheduling algorithms",
                    normalized_hash=uuid.uuid4().hex,
                    resolution_type="exact_match",
                )
                db.add(v)
                await db.flush()

                occ = PYQQuestionOccurrence(
                    paper_id=paper.id,
                    variant_id=v.id,
                    question_number="Q2b",
                    source_text=q.text,
                    marks_weight=10,
                )
                db.add(occ)

                # Strong mastery: 9.0 / 10.0 = 0.90 (>= 0.75) -> triggers MAINTAIN
                ev = AnswersEvaluation(
                    user_id=user.id,
                    question_id=q.id,
                    user_submitted_answer="Comprehensive comparison of SJF and FCFS.",
                    feedback="Excellent answer.",
                    estimated_marks=9.0,
                    max_marks=10.0,
                )
                db.add(ev)
                await db.commit()

                res = await execute_topic_recommendation_action(
                    subject_id=subject.id,
                    topic_id=topic.id,
                    db=db,
                    current_user=user,
                )

                self.assertEqual(res.action, RecommendationAction.MAINTAIN)
                self.assertEqual(res.action_priority, 7)
                self.assertIsNotNone(res.maintain_data)
                self.assertGreaterEqual(len(res.maintain_data.key_takeaways), 1)
                self.assertGreaterEqual(len(res.maintain_data.quick_revision_notes), 1)
                self.assertIsNotNone(res.maintain_data.sample_question)
                self.assertEqual(res.maintain_data.sample_question.source_scope, "topic")
                # Ensure no unsupported claims
                for text in res.maintain_data.key_takeaways + res.maintain_data.quick_revision_notes:
                    self.assertNotIn("formula", text.lower())
                    self.assertNotIn("diagram", text.lower())

        self.loop.run_until_complete(_run())

    def test_06_student_isolation_on_action_execution(self) -> None:
        """Student A (weak) gets PRACTICE while Student B (unattempted) gets ASSESS on the same topic."""
        async def _run():
            async with SessionLocal() as db:
                subject = Subject(
                    code=f"ISO-{uuid.uuid4().hex[:4]}",
                    name="Student Action Isolation Subject",
                    semester=6,
                    branch="Computer Engineering",
                )
                stu_a = User(
                    email=f"iso_a_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="hashed_password",
                    full_name="Student Weak",
                    role="student",
                )
                stu_b = User(
                    email=f"iso_b_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="hashed_password",
                    full_name="Student New",
                    role="student",
                )
                db.add_all([subject, stu_a, stu_b])
                await db.commit()
                await db.refresh(subject)
                await db.refresh(stu_a)
                await db.refresh(stu_b)

                topic = CanonicalTopic(
                    subject_id=subject.id,
                    canonical_label="B-Trees Index Structures",
                    normalized_label="b-trees index structures",
                    unit_tag="Unit 3",
                )
                db.add(topic)
                await db.flush()

                paper = PYQPaper(
                    subject_id=subject.id,
                    title="May 2023 Endsem",
                    exam_session="MAY_JUN",
                    exam_year=2023,
                )
                db.add(paper)
                await db.flush()

                q = Question(
                    subject_id=subject.id,
                    text="Explain B-Tree node splitting algorithm.",
                    marks_weight=10,
                    unit_tag="Unit 3",
                )
                db.add(q)
                await db.flush()

                v = QuestionVariant(
                    subject_id=subject.id,
                    topic_id=topic.id,
                    legacy_question_id=q.id,
                    text=q.text,
                    normalized_text="explain b-tree node splitting algorithm",
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

                # Student A has weak score: 2.0 / 10.0 = 0.20
                ev_a = AnswersEvaluation(
                    user_id=stu_a.id,
                    question_id=q.id,
                    user_submitted_answer="Partial attempt.",
                    feedback="Needs practice.",
                    estimated_marks=2.0,
                    max_marks=10.0,
                )
                db.add(ev_a)
                await db.commit()

                # Action for Student A -> PRACTICE
                res_a = await execute_topic_recommendation_action(
                    subject_id=subject.id,
                    topic_id=topic.id,
                    db=db,
                    current_user=stu_a,
                )
                self.assertEqual(res_a.action, RecommendationAction.PRACTICE)
                self.assertIsNotNone(res_a.practice_data)

                # Action for Student B -> ASSESS
                res_b = await execute_topic_recommendation_action(
                    subject_id=subject.id,
                    topic_id=topic.id,
                    db=db,
                    current_user=stu_b,
                )
                self.assertEqual(res_b.action, RecommendationAction.ASSESS)
                self.assertIsNotNone(res_b.quiz_data)

        self.loop.run_until_complete(_run())

    def test_07_topic_isolation_mismatched_subject_topic_404(self) -> None:
        """A topic belonging to Subject 1 requested under Subject 2 returns 404."""
        async def _run():
            async with SessionLocal() as db:
                subj1 = Subject(
                    code=f"S1-{uuid.uuid4().hex[:4]}",
                    name="Subject 1",
                    semester=5,
                    branch="Computer Engineering",
                )
                subj2 = Subject(
                    code=f"S2-{uuid.uuid4().hex[:4]}",
                    name="Subject 2",
                    semester=5,
                    branch="Computer Engineering",
                )
                user = User(
                    email=f"iso_user_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="hashed_password",
                    full_name="Iso User",
                    role="student",
                )
                db.add_all([subj1, subj2, user])
                await db.commit()
                await db.refresh(subj1)
                await db.refresh(subj2)
                await db.refresh(user)

                top1 = CanonicalTopic(
                    subject_id=subj1.id,
                    canonical_label="Subject 1 Topic",
                    normalized_label="subject 1 topic",
                )
                db.add(top1)
                await db.commit()

                # Request top1 under subj2 -> 404
                with self.assertRaises(HTTPException) as ctx:
                    await execute_topic_recommendation_action(
                        subject_id=subj2.id,
                        topic_id=top1.id,
                        db=db,
                        current_user=user,
                    )
                self.assertEqual(ctx.exception.status_code, 404)
                self.assertIn("Canonical Topic ID does not exist", ctx.exception.detail)

        self.loop.run_until_complete(_run())

    def test_08_invalid_subject_404(self) -> None:
        """Nonexistent subject ID returns 404."""
        async def _run():
            async with SessionLocal() as db:
                user = User(
                    email=f"usr_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="hashed_password",
                    full_name="User",
                    role="student",
                )
                db.add(user)
                await db.commit()
                await db.refresh(user)

                fake_subject = uuid.uuid4()
                fake_topic = uuid.uuid4()

                with self.assertRaises(HTTPException) as ctx:
                    await execute_topic_recommendation_action(
                        subject_id=fake_subject,
                        topic_id=fake_topic,
                        db=db,
                        current_user=user,
                    )
                self.assertEqual(ctx.exception.status_code, 404)
                self.assertIn("Course Subject ID does not exist", ctx.exception.detail)

        self.loop.run_until_complete(_run())

    def test_09_recommendations_endpoint_includes_action_endpoints(self) -> None:
        """GET /recommendations includes action_endpoint for seamless frontend action dispatch."""
        async def _run():
            async with SessionLocal() as db:
                subject = Subject(
                    code=f"RECO-{uuid.uuid4().hex[:4]}",
                    name="Recommendations Subject",
                    semester=4,
                    branch="Computer Engineering",
                )
                user = User(
                    email=f"rec_stu_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="hashed_password",
                    full_name="Reco Student",
                    role="student",
                )
                db.add_all([subject, user])
                await db.commit()
                await db.refresh(subject)
                await db.refresh(user)

                topic = CanonicalTopic(
                    subject_id=subject.id,
                    canonical_label="Pipelining Hazards",
                    normalized_label="pipelining hazards",
                    unit_tag="Unit 2",
                )
                db.add(topic)
                await db.commit()

                res = await get_subject_recommendations(
                    subject_id=subject.id,
                    db=db,
                    current_user=user,
                )

                self.assertIsInstance(res, SubjectRecommendationsOut)
                self.assertGreaterEqual(len(res.recommendations), 1)
                rec = res.recommendations[0]
                self.assertIsNotNone(rec.action_endpoint)
                self.assertEqual(
                    rec.action_endpoint,
                    f"/api/v1/analytics/subjects/{subject.id}/topics/{topic.id}/action",
                )

        self.loop.run_until_complete(_run())

    def test_10_no_synthetic_question_inserted_when_no_questions_exist(self) -> None:
        """Zero Question records are inserted/persisted when a topic has no questions in DB."""
        async def _run():
            async with SessionLocal() as db:
                subject = Subject(
                    code=f"NOF-{uuid.uuid4().hex[:4]}",
                    name="No Fake Question Subject",
                    semester=6,
                    branch="Computer Engineering",
                )
                user = User(
                    email=f"nof_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="hashed_password",
                    full_name="No Fake Student",
                    role="student",
                )
                db.add_all([subject, user])
                await db.commit()
                await db.refresh(subject)
                await db.refresh(user)

                topic = CanonicalTopic(
                    subject_id=subject.id,
                    canonical_label="Empty Practice Topic",
                    normalized_label="empty practice topic",
                    unit_tag="Unit 9",
                )
                db.add(topic)
                await db.flush()

                paper = PYQPaper(
                    subject_id=subject.id,
                    title="May 2023 Paper",
                    exam_session="MAY_JUN",
                    exam_year=2023,
                )
                db.add(paper)
                await db.flush()

                from unittest.mock import patch
                from app.services.recommendation import TopicRecommendation

                dummy_practice_rec = TopicRecommendation(
                    topic_id=topic.id,
                    canonical_label=topic.canonical_label,
                    unit_tag=topic.unit_tag,
                    priority_score=0.92,
                    priority_label="Very High",
                    student_mastery=0.20,
                    weakness_score=0.80,
                    evaluation_count=1,
                    recommended_action=RecommendationAction.PRACTICE,
                    recommendation_reason="High exam relevance combined with low demonstrated mastery.",
                    action_priority=1,
                )

                # Direct verification of _get_topic_practice_questions returning empty result
                direct_qs, direct_scope = await recommendation_service._get_topic_practice_questions(
                    db=db,
                    subject_id=subject.id,
                    topic=topic,
                )
                self.assertEqual(direct_qs, [])
                self.assertEqual(direct_scope, "none")

                # Count questions in database before action execution
                count_before = (await db.execute(select(func.count(Question.id)))).scalar() or 0

                # Execute PRACTICE action on topic with no questions
                with patch("app.services.recommendation.derive_topic_recommendation", return_value=dummy_practice_rec):
                    res = await execute_topic_recommendation_action(
                        subject_id=subject.id,
                        topic_id=topic.id,
                        db=db,
                        current_user=user,
                    )

                # Count questions in database after action execution
                count_after = (await db.execute(select(func.count(Question.id)))).scalar() or 0

                # Must not insert or mutate database Question count
                self.assertEqual(count_before, count_after)
                self.assertEqual(res.action, RecommendationAction.PRACTICE)
                self.assertEqual(res.practice_data, [])
                self.assertIn("No practice questions are currently available", res.reason)

        self.loop.run_until_complete(_run())

    def test_11_topic_specific_quiz_selection_excludes_unrelated_unit_questions(self) -> None:
        """Topic-focused quiz generation prefers topic questions and excludes unrelated same-unit questions."""
        async def _run():
            async with SessionLocal() as db:
                subject = Subject(
                    code=f"TQ-{uuid.uuid4().hex[:4]}",
                    name="Topic Quiz Filter Subject",
                    semester=6,
                    branch="Computer Engineering",
                )
                user = User(
                    email=f"tq_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="hashed_password",
                    full_name="Topic Quiz Student",
                    role="student",
                )
                db.add_all([subject, user])
                await db.commit()
                await db.refresh(subject)
                await db.refresh(user)

                # Two distinct topics in the same Unit 5
                topic_a = CanonicalTopic(
                    subject_id=subject.id,
                    canonical_label="Page Replacement Algorithms",
                    normalized_label="page replacement algorithms",
                    unit_tag="Unit 5",
                )
                topic_b = CanonicalTopic(
                    subject_id=subject.id,
                    canonical_label="Disk Scheduling Algorithms",
                    normalized_label="disk scheduling algorithms",
                    unit_tag="Unit 5",
                )
                db.add_all([topic_a, topic_b])
                await db.flush()

                # Question A for Topic A
                q_a = Question(
                    subject_id=subject.id,
                    text="Explain the Optimal Page Replacement algorithm.",
                    marks_weight=10,
                    unit_tag="Unit 5",
                )
                # Question B for Topic B (unrelated, but same unit)
                q_b = Question(
                    subject_id=subject.id,
                    text="Explain C-LOOK disk scheduling algorithm with head movements.",
                    marks_weight=10,
                    unit_tag="Unit 5",
                )
                db.add_all([q_a, q_b])
                await db.flush()

                v_a = QuestionVariant(
                    subject_id=subject.id,
                    topic_id=topic_a.id,
                    legacy_question_id=q_a.id,
                    text=q_a.text,
                    normalized_text="explain optimal page replacement algorithm",
                    normalized_hash=uuid.uuid4().hex,
                    resolution_type="exact_match",
                )
                v_b = QuestionVariant(
                    subject_id=subject.id,
                    topic_id=topic_b.id,
                    legacy_question_id=q_b.id,
                    text=q_b.text,
                    normalized_text="explain c-look disk scheduling algorithm head movements",
                    normalized_hash=uuid.uuid4().hex,
                    resolution_type="exact_match",
                )
                db.add_all([v_a, v_b])
                await db.commit()

                # Generate quiz specifying topic_a.id
                quiz = await quiz_service.generate_quiz(
                    db=db,
                    subject_id=subject.id,
                    title="Topic A Focused Quiz",
                    quiz_type="MCQ",
                    unit_tag="Unit 5",
                    topic_id=topic_a.id,
                )

                questions = quiz.questions_data.get("questions", [])
                self.assertGreaterEqual(len(questions), 1)

                question_texts = [q["question"] for q in questions]
                # Must include Topic A question
                self.assertTrue(any("Page Replacement" in t for t in question_texts))
                # Must NOT include unrelated Topic B question from the same unit
                self.assertFalse(any("disk scheduling" in t.lower() for t in question_texts))

        self.loop.run_until_complete(_run())

    def test_12_unit_fallback_clearly_labeled_with_source_scope(self) -> None:
        """Unit fallback questions are explicitly labeled with source_scope='unit'."""
        async def _run():
            async with SessionLocal() as db:
                subject = Subject(
                    code=f"FALL-{uuid.uuid4().hex[:4]}",
                    name="Unit Fallback Subject",
                    semester=6,
                    branch="Computer Engineering",
                )
                user = User(
                    email=f"fall_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="hashed_password",
                    full_name="Fallback Student",
                    role="student",
                )
                db.add_all([subject, user])
                await db.commit()
                await db.refresh(subject)
                await db.refresh(user)

                # Topic with no variants/compatibility question, but matching unit_tag
                topic = CanonicalTopic(
                    subject_id=subject.id,
                    canonical_label="Secondary Topic Without PYQs",
                    normalized_label="secondary topic without pyqs",
                    unit_tag="Unit 4",
                )
                db.add(topic)
                await db.flush()

                # Generic question in Unit 4
                q_unit = Question(
                    subject_id=subject.id,
                    text="Explain general concepts of memory management.",
                    marks_weight=5,
                    unit_tag="Unit 4",
                )
                db.add(q_unit)
                await db.commit()

                # Directly test _get_topic_practice_questions
                questions, scope = await recommendation_service._get_topic_practice_questions(
                    db=db, subject_id=subject.id, topic=topic
                )
                self.assertEqual(scope, "unit")
                self.assertEqual(len(questions), 1)
                self.assertEqual(questions[0].id, q_unit.id)

        self.loop.run_until_complete(_run())


if __name__ == "__main__":
    unittest.main()
