import asyncio
import sys
import unittest
import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import event, select
import app.database.base  # noqa: F401
from app.database.session import SessionLocal
from app.models.subject import Subject
from app.models.pyq_topic import (
    CanonicalTopic,
    PYQPaper,
    PYQQuestionOccurrence,
    QuestionVariant,
)
from app.repositories.pyq_topic import pyq_topic_repository, TopicAggregate


class TopicAggregationRepositoryTests(unittest.TestCase):
    """
    Unit & integration tests verifying Phase 3A:
    Canonical-topic-level PYQ aggregation and unresolved variant retrieval.
    """

    def setUp(self) -> None:
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self) -> None:
        self.loop.close()

    def test_canonical_topic_rollup_and_distinct_papers_and_marks(self) -> None:
        """
        Verifies:
        1. Two variants belonging to the same canonical topic aggregate into one topic.
        2. Occurrences across multiple papers produce correct distinct_papers.
        3. Different marks [5, 10, 10] produce avg_marks = 25/3 and max_marks = 10.
        4. Empty topics with 0 occurrences are handled deliberately.
        """
        async def _run():
            async with SessionLocal() as db:
                subject = Subject(code=f"AGG1-{uuid.uuid4().hex[:6]}", name="Agg Test 1", semester=1, branch="CS")
                db.add(subject)
                await db.commit()
                await db.refresh(subject)

                try:
                    topic = CanonicalTopic(
                        subject_id=subject.id,
                        canonical_label="Virtual Memory",
                        normalized_label="virtual memory",
                        unit_tag="Unit 3",
                    )
                    empty_topic = CanonicalTopic(
                        subject_id=subject.id,
                        canonical_label="Cache Coherence",
                        normalized_label="cache coherence",
                        unit_tag="Unit 4",
                    )
                    db.add_all([topic, empty_topic])
                    await db.flush()

                    variant_1 = QuestionVariant(
                        subject_id=subject.id,
                        topic_id=topic.id,
                        text="What is virtual memory?",
                        normalized_text="what is virtual memory",
                        normalized_hash=uuid.uuid4().hex,
                        resolution_type="semantic_match",
                    )
                    variant_2 = QuestionVariant(
                        subject_id=subject.id,
                        topic_id=topic.id,
                        text="Explain the concept of virtual memory in operating systems.",
                        normalized_text="explain the concept of virtual memory in operating systems",
                        normalized_hash=uuid.uuid4().hex,
                        resolution_type="semantic_match",
                    )
                    db.add_all([variant_1, variant_2])
                    await db.flush()

                    paper_1 = PYQPaper(subject_id=subject.id, title="Dec 2022", exam_year=2022)
                    paper_2 = PYQPaper(subject_id=subject.id, title="May 2023", exam_year=2023)
                    db.add_all([paper_1, paper_2])
                    await db.flush()

                    # 3 occurrences:
                    # paper 1, variant 1 -> 5 marks
                    # paper 1, variant 2 -> 10 marks
                    # paper 2, variant 2 -> 10 marks
                    occ_1 = PYQQuestionOccurrence(
                        paper_id=paper_1.id, variant_id=variant_1.id, marks_weight=5, source_text=variant_1.text
                    )
                    occ_2 = PYQQuestionOccurrence(
                        paper_id=paper_1.id, variant_id=variant_2.id, marks_weight=10, source_text=variant_2.text
                    )
                    occ_3 = PYQQuestionOccurrence(
                        paper_id=paper_2.id, variant_id=variant_2.id, marks_weight=10, source_text=variant_2.text
                    )
                    db.add_all([occ_1, occ_2, occ_3])
                    await db.commit()

                    aggregates = await pyq_topic_repository.get_topic_aggregates(db, subject.id)
                    agg_map = {agg.topic_id: agg for agg in aggregates}

                    self.assertEqual(len(aggregates), 2)
                    self.assertIn(topic.id, agg_map)
                    self.assertIn(empty_topic.id, agg_map)

                    # Rollup checks for Virtual Memory
                    vm_agg = agg_map[topic.id]
                    self.assertEqual(vm_agg.canonical_label, "Virtual Memory")
                    self.assertEqual(vm_agg.normalized_label, "virtual memory")
                    self.assertEqual(vm_agg.unit_tag, "Unit 3")
                    self.assertEqual(vm_agg.total_occurrences, 3)
                    self.assertEqual(vm_agg.distinct_papers, 2)
                    self.assertAlmostEqual(vm_agg.avg_marks, 25 / 3, places=5)
                    self.assertEqual(vm_agg.max_marks, 10)

                    # Empty topic checks
                    empty_agg = agg_map[empty_topic.id]
                    self.assertEqual(empty_agg.total_occurrences, 0)
                    self.assertEqual(empty_agg.distinct_papers, 0)
                    self.assertEqual(empty_agg.avg_marks, 0.0)
                    self.assertEqual(empty_agg.max_marks, 0)
                finally:
                    await db.delete(subject)
                    await db.commit()

        self.loop.run_until_complete(_run())

    def test_subject_isolation(self) -> None:
        """
        Verifies:
        An occurrence from another subject does not affect the requested subject.
        """
        async def _run():
            async with SessionLocal() as db:
                subject_1 = Subject(code=f"SUB1-{uuid.uuid4().hex[:6]}", name="Course 1", semester=1, branch="CS")
                subject_2 = Subject(code=f"SUB2-{uuid.uuid4().hex[:6]}", name="Course 2", semester=1, branch="IT")
                db.add_all([subject_1, subject_2])
                await db.commit()
                await db.refresh(subject_1)
                await db.refresh(subject_2)

                try:
                    topic_1 = CanonicalTopic(
                        subject_id=subject_1.id, canonical_label="Topic in Sub 1", normalized_label="topic in sub 1"
                    )
                    topic_2 = CanonicalTopic(
                        subject_id=subject_2.id, canonical_label="Topic in Sub 2", normalized_label="topic in sub 2"
                    )
                    db.add_all([topic_1, topic_2])
                    await db.flush()

                    variant_1 = QuestionVariant(
                        subject_id=subject_1.id,
                        topic_id=topic_1.id,
                        text="Question 1 in Sub 1",
                        normalized_text="question 1 in sub 1",
                        normalized_hash=uuid.uuid4().hex,
                        resolution_type="semantic_match",
                    )
                    variant_2 = QuestionVariant(
                        subject_id=subject_2.id,
                        topic_id=topic_2.id,
                        text="Question 2 in Sub 2",
                        normalized_text="question 2 in sub 2",
                        normalized_hash=uuid.uuid4().hex,
                        resolution_type="semantic_match",
                    )
                    db.add_all([variant_1, variant_2])
                    await db.flush()

                    paper_1 = PYQPaper(subject_id=subject_1.id, title="Sub 1 Paper")
                    paper_2 = PYQPaper(subject_id=subject_2.id, title="Sub 2 Paper")
                    db.add_all([paper_1, paper_2])
                    await db.flush()

                    occ_1 = PYQQuestionOccurrence(
                        paper_id=paper_1.id, variant_id=variant_1.id, marks_weight=6, source_text=variant_1.text
                    )
                    occ_2 = PYQQuestionOccurrence(
                        paper_id=paper_2.id, variant_id=variant_2.id, marks_weight=14, source_text=variant_2.text
                    )
                    db.add_all([occ_1, occ_2])
                    await db.commit()

                    # Query Subject 1
                    aggs_1 = await pyq_topic_repository.get_topic_aggregates(db, subject_1.id)
                    self.assertEqual(len(aggs_1), 1)
                    self.assertEqual(aggs_1[0].topic_id, topic_1.id)
                    self.assertEqual(aggs_1[0].total_occurrences, 1)
                    self.assertEqual(aggs_1[0].distinct_papers, 1)
                    self.assertEqual(aggs_1[0].avg_marks, 6.0)
                    self.assertEqual(aggs_1[0].max_marks, 6)

                    # Query Subject 2
                    aggs_2 = await pyq_topic_repository.get_topic_aggregates(db, subject_2.id)
                    self.assertEqual(len(aggs_2), 1)
                    self.assertEqual(aggs_2[0].topic_id, topic_2.id)
                    self.assertEqual(aggs_2[0].total_occurrences, 1)
                    self.assertEqual(aggs_2[0].distinct_papers, 1)
                    self.assertEqual(aggs_2[0].avg_marks, 14.0)
                    self.assertEqual(aggs_2[0].max_marks, 14)
                finally:
                    await db.delete(subject_1)
                    await db.delete(subject_2)
                    await db.commit()

        self.loop.run_until_complete(_run())

    def test_get_unresolved_variants(self) -> None:
        """
        Verifies:
        Unresolved variants (where topic_id IS NULL) are returned by get_unresolved_variants().
        Resolved variants (where topic_id is set) are excluded.
        """
        async def _run():
            async with SessionLocal() as db:
                subject = Subject(code=f"UNRES-{uuid.uuid4().hex[:6]}", name="Unresolved Test", semester=1, branch="CS")
                db.add(subject)
                await db.commit()
                await db.refresh(subject)

                try:
                    topic = CanonicalTopic(
                        subject_id=subject.id, canonical_label="Known Topic", normalized_label="known topic"
                    )
                    db.add(topic)
                    await db.flush()

                    resolved_var = QuestionVariant(
                        subject_id=subject.id,
                        topic_id=topic.id,
                        text="Resolved variant text",
                        normalized_text="resolved variant text",
                        normalized_hash=uuid.uuid4().hex,
                        resolution_type="semantic_match",
                    )
                    unresolved_var_1 = QuestionVariant(
                        subject_id=subject.id,
                        topic_id=None,
                        text="Ambiguous question 1",
                        normalized_text="ambiguous question 1",
                        normalized_hash=uuid.uuid4().hex,
                        resolution_type="ambiguous",
                    )
                    unresolved_var_2 = QuestionVariant(
                        subject_id=subject.id,
                        topic_id=None,
                        text="Ambiguous question 2",
                        normalized_text="ambiguous question 2",
                        normalized_hash=uuid.uuid4().hex,
                        resolution_type="unresolved_uncalibrated",
                    )
                    db.add_all([resolved_var, unresolved_var_1, unresolved_var_2])
                    await db.commit()

                    unresolved = await pyq_topic_repository.get_unresolved_variants(db, subject.id)
                    self.assertEqual(len(unresolved), 2)
                    unresolved_ids = {var.id for var in unresolved}
                    self.assertIn(unresolved_var_1.id, unresolved_ids)
                    self.assertIn(unresolved_var_2.id, unresolved_ids)
                    self.assertNotIn(resolved_var.id, unresolved_ids)

                    for var in unresolved:
                        self.assertIsNone(var.topic_id)
                        self.assertEqual(var.subject_id, subject.id)
                finally:
                    await db.delete(subject)
                    await db.commit()

        self.loop.run_until_complete(_run())

    def test_single_query_execution_no_n_plus_one(self) -> None:
        """
        Verifies:
        No N+1 query pattern is introduced.
        get_topic_aggregates executes exactly 1 SQL statement regardless of number of topics.
        """
        async def _run():
            async with SessionLocal() as db:
                subject = Subject(code=f"NPLUS-{uuid.uuid4().hex[:6]}", name="N+1 Check", semester=1, branch="CS")
                db.add(subject)
                await db.commit()
                await db.refresh(subject)

                try:
                    # Create 5 topics each with variants and occurrences
                    paper = PYQPaper(subject_id=subject.id, title="Test Paper")
                    db.add(paper)
                    await db.flush()

                    for i in range(5):
                        topic = CanonicalTopic(
                            subject_id=subject.id,
                            canonical_label=f"Topic {i}",
                            normalized_label=f"topic {i}",
                            unit_tag=f"Unit {i}",
                        )
                        db.add(topic)
                        await db.flush()

                        variant = QuestionVariant(
                            subject_id=subject.id,
                            topic_id=topic.id,
                            text=f"Question for topic {i}",
                            normalized_text=f"question for topic {i}",
                            normalized_hash=uuid.uuid4().hex,
                            resolution_type="semantic_match",
                        )
                        db.add(variant)
                        await db.flush()

                        occ = PYQQuestionOccurrence(
                            paper_id=paper.id, variant_id=variant.id, marks_weight=10, source_text=variant.text
                        )
                        db.add(occ)

                    await db.commit()

                    # Intercept SQL query execution on engine
                    captured_queries = []
                    def count_queries(conn, cursor, statement, parameters, context, executemany):
                        captured_queries.append(statement)

                    event.listen(db.bind.sync_engine, "before_cursor_execute", count_queries)
                    try:
                        results = await pyq_topic_repository.get_topic_aggregates(db, subject.id)
                    finally:
                        event.remove(db.bind.sync_engine, "before_cursor_execute", count_queries)

                    self.assertEqual(len(results), 5)
                    self.assertEqual(
                        len(captured_queries),
                        1,
                        f"Expected exactly 1 query to prevent N+1, but observed {len(captured_queries)} queries.",
                    )
                finally:
                    await db.delete(subject)
                    await db.commit()

        self.loop.run_until_complete(_run())


if __name__ == "__main__":
    unittest.main()
