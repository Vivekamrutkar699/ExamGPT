"""
Unit tests for ExamGPT Phase 5A: RAG Retrieval Evaluation System.

Tests cover:
1. Deterministic Recall@k calculations (Recall@3, Recall@5, multiple golden chunks, duplicates, edge cases).
2. Deterministic MRR calculations (first rank, deep rank, no hits, edge cases).
3. Deterministic Context Relevance proxy calculations (keywords, unit matching, edge cases).
4. Aggregate metrics calculation (averaging, zero counts, non-finite values).
5. Referential integrity validation between curated dataset and frozen corpus.
6. RetrievalEvalRunner execution (single case, batch dataset evaluation, failure tracking).
7. Report generation (JSON schema validity and Markdown report structure).
"""

import json
import unittest
from pathlib import Path

from app.evals.metrics import (
    calculate_recall_at_k,
    calculate_mrr,
    calculate_context_relevance,
    aggregate_case_metrics,
)
from app.evals.schemas import (
    EvalCase,
    EvalDataset,
    CaseMetricScore,
    AggregateEvalMetrics,
    EvalRunReport,
)
from app.evals.validator import (
    load_frozen_corpus,
    load_eval_dataset,
    validate_eval_dataset_integrity,
)
from app.evals.runner import RetrievalEvalRunner
from app.evals.reporter import (
    generate_json_report,
    generate_markdown_report,
)


class TestRetrievalMetrics(unittest.TestCase):
    """Test deterministic retrieval metric calculations with exact known values."""

    def test_recall_at_k_single_golden_hit_top3(self):
        retrieved = ["chunk_a", "chunk_b", "chunk_c", "chunk_d", "chunk_e"]
        golden = ["chunk_a"]
        # chunk_a is at rank 1 <= 3
        self.assertEqual(calculate_recall_at_k(retrieved, golden, k=3), 1.0)
        self.assertEqual(calculate_recall_at_k(retrieved, golden, k=5), 1.0)

    def test_recall_at_k_single_golden_hit_at_rank_4(self):
        retrieved = ["chunk_a", "chunk_b", "chunk_c", "chunk_target", "chunk_e"]
        golden = ["chunk_target"]
        # chunk_target is at rank 4 (> 3, <= 5)
        self.assertEqual(calculate_recall_at_k(retrieved, golden, k=3), 0.0)
        self.assertEqual(calculate_recall_at_k(retrieved, golden, k=5), 1.0)

    def test_recall_at_k_multiple_golden_partial_hits(self):
        retrieved = ["c1", "c2", "c3", "c4", "c5"]
        golden = ["c1", "c3", "c99"]  # 2 of 3 golden in top 3
        # Top 3 has c1 and c3 -> 2/3 = 0.6667
        self.assertEqual(calculate_recall_at_k(retrieved, golden, k=3), 0.6667)
        # Top 5 still only has c1 and c3 -> 2/3 = 0.6667
        self.assertEqual(calculate_recall_at_k(retrieved, golden, k=5), 0.6667)

    def test_recall_at_k_duplicate_retrieved_handling(self):
        # Even if retrieved has duplicates of the same golden item, it should only count once
        retrieved = ["c1", "c1", "c1", "c2", "c3"]
        golden = ["c1", "c2"]
        # Top 3 unique are ['c1', 'c2'] -> hits=2, len(golden)=2 -> 1.0
        self.assertEqual(calculate_recall_at_k(retrieved, golden, k=3), 1.0)

    def test_recall_at_k_edge_cases(self):
        # Empty retrieved
        self.assertEqual(calculate_recall_at_k([], ["c1"], k=3), 0.0)
        # Empty golden
        self.assertEqual(calculate_recall_at_k(["c1"], [], k=3), 0.0)
        # k <= 0
        self.assertEqual(calculate_recall_at_k(["c1"], ["c1"], k=0), 0.0)
        self.assertEqual(calculate_recall_at_k(["c1"], ["c1"], k=-1), 0.0)
        # k larger than retrieved count
        self.assertEqual(calculate_recall_at_k(["c1"], ["c1"], k=10), 1.0)
        # No overlap
        self.assertEqual(calculate_recall_at_k(["c1", "c2"], ["c3", "c4"], k=5), 0.0)

    def test_mrr_exact_values(self):
        # First rank hit: 1/1 = 1.0
        self.assertEqual(calculate_mrr(["c1", "c2", "c3"], ["c1"]), 1.0)
        # Second rank hit: 1/2 = 0.5
        self.assertEqual(calculate_mrr(["c1", "c2", "c3"], ["c2"]), 0.5)
        # Third rank hit: 1/3 = 0.3333
        self.assertEqual(calculate_mrr(["c1", "c2", "c3"], ["c3"]), 0.3333)
        # Fourth rank hit: 1/4 = 0.25
        self.assertEqual(calculate_mrr(["c0", "c1", "c2", "c3"], ["c3"]), 0.25)
        # Fifth rank hit: 1/5 = 0.2
        self.assertEqual(calculate_mrr(["c0", "c1", "c2", "c3", "c4"], ["c4"]), 0.2)

    def test_mrr_first_match_priority(self):
        # If multiple golden items appear, MRR uses the FIRST match
        retrieved = ["noise", "golden_first", "noise2", "golden_second"]
        golden = ["golden_first", "golden_second"]
        # First match is at rank 2 -> 1/2 = 0.5
        self.assertEqual(calculate_mrr(retrieved, golden), 0.5)

    def test_mrr_edge_cases(self):
        # No match
        self.assertEqual(calculate_mrr(["c1", "c2"], ["c3"]), 0.0)
        # Empty lists
        self.assertEqual(calculate_mrr([], ["c1"]), 0.0)
        self.assertEqual(calculate_mrr(["c1"], []), 0.0)
        self.assertEqual(calculate_mrr([], []), 0.0)
        # Duplicate IDs in retrieved before match
        retrieved = ["noise", "noise", "target"]
        # Deduped retrieved is ['noise', 'target'] -> target is rank 2 -> 0.5
        self.assertEqual(calculate_mrr(retrieved, ["target"]), 0.5)

    def test_context_relevance_proxy(self):
        chunks = [
            {"content": "A Linker combines object modules.", "unit_tag": "Unit 1"},
            {"content": "Compilers perform lexical analysis.", "unit_tag": "Unit 2"},
            {"content": "Paging manages physical memory frames.", "unit_tag": "Unit 5"},
            {"content": "Unrelated network socket overview.", "unit_tag": "Unit 1"},
        ]
        # Concepts match chunks 0 and 1, chunk 3 matches Unit 1 -> 3 of 4 = 0.75
        rel = calculate_context_relevance(
            retrieved_chunks=chunks,
            expected_concepts=["linker", "compiler"],
            expected_unit="Unit 1",
        )
        self.assertEqual(rel, 0.75)

    def test_context_relevance_edge_cases(self):
        # Empty chunks
        self.assertEqual(calculate_context_relevance([], ["keyword"]), 0.0)
        # Empty concepts and no unit
        chunks = [{"content": "Some text", "unit_tag": "Unit 1"}]
        self.assertEqual(calculate_context_relevance(chunks, []), 0.0)
        # Case insensitivity
        chunks = [{"content": "DEADLOCK occurs when all Coffman conditions hold."}]
        self.assertEqual(calculate_context_relevance(chunks, ["deadlock"]), 1.0)

    def test_aggregate_case_metrics(self):
        case1 = CaseMetricScore(
            case_id="c1", subject="SPOS", unit="U1", query="q1",
            recall_at_3=1.0, recall_at_5=1.0, mrr=1.0, context_relevance=1.0,
            golden_chunk_ids=["g1"], retrieved_chunk_ids=["g1"],
            missed_golden_chunk_ids=[], matched_concepts=["concept"], has_relevant_chunk=True,
        )
        case2 = CaseMetricScore(
            case_id="c2", subject="SPOS", unit="U1", query="q2",
            recall_at_3=0.0, recall_at_5=1.0, mrr=0.25, context_relevance=0.5,
            golden_chunk_ids=["g2"], retrieved_chunk_ids=["x", "y", "z", "g2"],
            missed_golden_chunk_ids=[], matched_concepts=[], has_relevant_chunk=True,
        )
        case3 = CaseMetricScore(
            case_id="c3", subject="CN", unit="U1", query="q3",
            recall_at_3=0.0, recall_at_5=0.0, mrr=0.0, context_relevance=0.0,
            golden_chunk_ids=["g3"], retrieved_chunk_ids=["x", "y"],
            missed_golden_chunk_ids=["g3"], matched_concepts=[], has_relevant_chunk=False,
        )

        agg = aggregate_case_metrics([case1, case2, case3])
        self.assertEqual(agg.total_cases, 3)
        # Mean R@3 = (1.0 + 0.0 + 0.0)/3 = 0.3333
        self.assertEqual(agg.mean_recall_at_3, 0.3333)
        # Mean R@5 = (1.0 + 1.0 + 0.0)/3 = 0.6667
        self.assertEqual(agg.mean_recall_at_5, 0.6667)
        # Mean MRR = (1.0 + 0.25 + 0.0)/3 = 1.25/3 = 0.4167
        self.assertEqual(agg.mean_mrr, 0.4167)
        # Mean CR = (1.0 + 0.5 + 0.0)/3 = 1.5/3 = 0.5
        self.assertEqual(agg.mean_context_relevance, 0.5)
        self.assertEqual(agg.perfect_recall_at_3_count, 1)
        self.assertEqual(agg.perfect_recall_at_5_count, 2)
        self.assertEqual(agg.zero_mrr_count, 1)


class TestDatasetIntegrity(unittest.TestCase):
    """Verify referential integrity of curated evaluation cases against frozen corpus."""

    def setUp(self):
        self.corpus = load_frozen_corpus()
        self.dataset = load_eval_dataset()

    def test_dataset_case_count(self):
        # Must have exactly 35 curated cases
        self.assertEqual(len(self.dataset.cases), 35)

    def test_corpus_chunk_count(self):
        # Must have 35 frozen chunks
        self.assertEqual(len(self.corpus.chunks), 35)

    def test_dataset_integrity_validator(self):
        is_valid, errors = validate_eval_dataset_integrity(
            dataset=self.dataset,
            corpus=self.corpus,
            expected_case_count=35,
        )
        self.assertTrue(is_valid, f"Validation failed with errors: {errors}")
        self.assertEqual(len(errors), 0)

    def test_subject_coverage(self):
        subjects = {c.subject for c in self.dataset.cases}
        self.assertIn("SPOS", subjects)
        self.assertIn("CN", subjects)
        self.assertIn("DBMS", subjects)
        self.assertIn("TOC", subjects)

    def test_all_golden_chunks_exist_in_corpus(self):
        valid_chunk_ids = {c.chunk_id for c in self.corpus.chunks}
        for case in self.dataset.cases:
            for g_id in case.golden_chunk_ids:
                self.assertIn(
                    g_id,
                    valid_chunk_ids,
                    f"Case {case.case_id} references nonexistent chunk {g_id}",
                )


class TestRetrievalEvalRunner(unittest.TestCase):
    """Test the independent evaluation runner."""

    def setUp(self):
        self.runner = RetrievalEvalRunner()
        self.dataset = load_eval_dataset()

    def test_evaluate_single_case_perfect_hit(self):
        case = self.dataset.cases[0]  # eval_spos_001, golden is chunk_spos_u1_001
        retrieved_chunks = [
            {"chunk_id": "chunk_spos_u1_001", "content": "Linker and loader explanation", "unit_tag": "Unit 1"},
            {"chunk_id": "chunk_other", "content": "Some other info", "unit_tag": "Unit 1"},
        ]
        score = self.runner.evaluate_single_case(case, retrieved_chunks)
        self.assertEqual(score.case_id, "eval_spos_001")
        self.assertEqual(score.recall_at_3, 1.0)
        self.assertEqual(score.recall_at_5, 1.0)
        self.assertEqual(score.mrr, 1.0)
        self.assertEqual(score.has_relevant_chunk, True)
        self.assertEqual(len(score.missed_golden_chunk_ids), 0)

    def test_evaluate_single_case_miss(self):
        case = self.dataset.cases[0]
        retrieved_chunks = [
            {"chunk_id": "irrelevant_1", "content": "Random text", "unit_tag": "Unit 9"},
            {"chunk_id": "irrelevant_2", "content": "More random text", "unit_tag": "Unit 9"},
        ]
        score = self.runner.evaluate_single_case(case, retrieved_chunks)
        self.assertEqual(score.recall_at_3, 0.0)
        self.assertEqual(score.recall_at_5, 0.0)
        self.assertEqual(score.mrr, 0.0)
        self.assertEqual(score.has_relevant_chunk, False)
        self.assertEqual(score.missed_golden_chunk_ids, ["chunk_spos_u1_001"])

    def test_evaluate_full_dataset_batch(self):
        # Create simulated candidate mapping: perfect retrieval for first 20 cases, misses for the rest
        candidates = {}
        for idx, case in enumerate(self.dataset.cases):
            if idx < 20:
                candidates[case.case_id] = [
                    {"chunk_id": g_id, "content": "Relevant content", "unit_tag": case.unit}
                    for g_id in case.golden_chunk_ids
                ]
            else:
                candidates[case.case_id] = [
                    {"chunk_id": "unrelated_chunk", "content": "No match", "unit_tag": "Other"}
                ]

        report = self.runner.evaluate_dataset(self.dataset, candidates)
        self.assertEqual(report.aggregate_metrics.total_cases, 35)
        self.assertEqual(report.aggregate_metrics.perfect_recall_at_3_count, 20)
        self.assertEqual(report.aggregate_metrics.zero_mrr_count, 15)
        self.assertEqual(len(report.failures), 15)


class TestReportGenerator(unittest.TestCase):
    """Test JSON and Markdown report generation."""

    def setUp(self):
        self.runner = RetrievalEvalRunner()
        self.dataset = load_eval_dataset()
        # Build a small synthetic report
        candidates = {
            self.dataset.cases[0].case_id: [
                {"chunk_id": self.dataset.cases[0].golden_chunk_ids[0], "content": "linker loader", "unit_tag": "Unit 1"}
            ]
        }
        self.report = self.runner.evaluate_dataset(self.dataset, candidates)

    def test_json_report_serialization(self):
        json_str = generate_json_report(self.report)
        parsed = json.loads(json_str)
        self.assertIn("dataset_name", parsed)
        self.assertIn("aggregate_metrics", parsed)
        self.assertEqual(parsed["aggregate_metrics"]["total_cases"], 35)

    def test_markdown_report_formatting(self):
        md_str = generate_markdown_report(self.report)
        self.assertIn("# RAG Retrieval Benchmark Report", md_str)
        self.assertIn("Recall@3", md_str)
        self.assertIn("Recall@5", md_str)
        self.assertIn("MRR", md_str)
        self.assertIn("Context Relevance", md_str)
        self.assertIn("Subject Breakdown", md_str)
        self.assertIn("SPOS", md_str)
        self.assertIn("CN", md_str)
        self.assertIn("DBMS", md_str)
        self.assertIn("TOC", md_str)


if __name__ == "__main__":
    unittest.main()
