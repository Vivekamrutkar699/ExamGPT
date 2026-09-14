"""
Unit and integration tests for ExamGPT Phase 5B:
Connecting the RAG retrieval pipeline to the evaluation harness.

Tests cover:
1. Retrieval adapter initialization and deterministic frozen corpus indexing.
2. Individual retrieval configuration execution (dense, lexical, hybrid/RRF, hybrid_reranked).
3. Configuration coverage: all 4 strategies return structured candidate dicts.
4. Deterministic repeated-run test: verifying identical rankings and scores across runs.
5. End-to-end multi-configuration benchmark runner test with the 35 curated cases.
6. JSON and Markdown multi-configuration report generation.
"""

import json
import unittest
from pathlib import Path

from app.evals.schemas import (
    EvalDataset,
    FrozenCorpus,
    MultiConfigBenchmarkReport,
)
from app.evals.validator import (
    load_frozen_corpus,
    load_eval_dataset,
)
from app.evals.adapter import EvalRetrievalAdapter
from app.evals.runner import RetrievalEvalRunner
from app.evals.reporter import (
    generate_multi_config_json_report,
    generate_multi_config_markdown_report,
)


class TestEvalRetrievalAdapter(unittest.TestCase):
    """Test retrieval adapter algorithms against frozen corpus."""

    @classmethod
    def setUpClass(cls):
        cls.corpus = load_frozen_corpus()
        cls.dataset = load_eval_dataset()
        cls.adapter = EvalRetrievalAdapter(cls.corpus, precompute_embeddings=True)

    def test_adapter_initialization(self):
        self.assertEqual(len(self.adapter.chunks), 35)
        self.assertIsNotNone(self.adapter.chunk_embeddings)
        self.assertEqual(self.adapter.chunk_embeddings.shape, (35, 384))

    def test_lexical_retrieval(self):
        # Query specifically with keywords from chunk_spos_u1_001
        results = self.adapter.lexical_retrieval(
            query="linker loader executable binary image",
            limit=5,
        )
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0]["chunk_id"], "chunk_spos_u1_001")
        self.assertIn("score", results[0])
        self.assertTrue(results[0]["score"] > 0.0)

    def test_dense_retrieval(self):
        # Semantic query
        results = self.adapter.dense_retrieval(
            query="How does an operating system resolve symbols and load programs into RAM?",
            limit=5,
        )
        self.assertTrue(len(results) > 0)
        # Should identify chunk_spos_u1_001 or chunk_spos_u1_002
        top_ids = [r["chunk_id"] for r in results[:3]]
        self.assertIn("chunk_spos_u1_001", top_ids)

    def test_hybrid_rrf_retrieval(self):
        results = self.adapter.hybrid_rrf_retrieval(
            query="Cyclic redundancy check crc generator polynomial",
            limit=5,
        )
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0]["chunk_id"], "chunk_cn_u2_001")
        self.assertIn("rrf_score", results[0])

    def test_hybrid_reranked_retrieval(self):
        results = self.adapter.hybrid_reranked_retrieval(
            query="Banker's algorithm safe state resource allocation",
            limit=5,
        )
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0]["chunk_id"], "chunk_spos_u4_003")
        self.assertIn("score", results[0])

    def test_configuration_coverage(self):
        # Test that retrieve(...) works for all 4 named configurations
        configs = ["dense", "lexical", "hybrid", "hybrid_reranked"]
        for config in configs:
            retrieved = self.adapter.retrieve(
                configuration=config,
                query="Turing machine halting problem undecidable",
                limit=3,
            )
            self.assertTrue(len(retrieved) > 0, f"Empty retrieval for config {config}")
            self.assertIn("chunk_id", retrieved[0])
            self.assertEqual(retrieved[0]["chunk_id"], "chunk_toc_u4_001")

    def test_deterministic_repeated_runs(self):
        # Two successive runs with the exact same query and configuration must yield identical results
        query = "Two-phase locking protocol 2PL concurrency serializability"
        run_1 = self.adapter.retrieve("hybrid_reranked", query, limit=5)
        run_2 = self.adapter.retrieve("hybrid_reranked", query, limit=5)

        self.assertEqual(len(run_1), len(run_2))
        for item1, item2 in zip(run_1, run_2):
            self.assertEqual(item1["chunk_id"], item2["chunk_id"])
            self.assertAlmostEqual(item1["score"], item2["score"], places=6)


class TestMultiConfigBenchmarkRunner(unittest.TestCase):
    """Test multi-configuration benchmark runner and reporting."""

    @classmethod
    def setUpClass(cls):
        cls.corpus = load_frozen_corpus()
        cls.dataset = load_eval_dataset()
        cls.adapter = EvalRetrievalAdapter(cls.corpus, precompute_embeddings=True)
        cls.runner = RetrievalEvalRunner()

    def test_benchmark_runner_full_run(self):
        # Run across all 4 configurations
        benchmark = self.runner.evaluate_multi_configurations(
            dataset=self.dataset,
            adapter=self.adapter,
            configurations=("dense", "lexical", "hybrid", "hybrid_reranked"),
            limit=5,
        )

        self.assertIsInstance(benchmark, MultiConfigBenchmarkReport)
        self.assertEqual(benchmark.total_cases, 35)
        self.assertIn("dense", benchmark.configuration_reports)
        self.assertIn("lexical", benchmark.configuration_reports)
        self.assertIn("hybrid", benchmark.configuration_reports)
        self.assertIn("hybrid_reranked", benchmark.configuration_reports)

        for config_name, rep in benchmark.configuration_reports.items():
            self.assertEqual(rep.aggregate_metrics.total_cases, 35)
            # Scores must be finite and within [0.0, 1.0]
            self.assertTrue(0.0 <= rep.aggregate_metrics.mean_recall_at_3 <= 1.0)
            self.assertTrue(0.0 <= rep.aggregate_metrics.mean_recall_at_5 <= 1.0)
            self.assertTrue(0.0 <= rep.aggregate_metrics.mean_mrr <= 1.0)
            self.assertTrue(0.0 <= rep.aggregate_metrics.mean_context_relevance <= 1.0)

    def test_multi_config_reporting(self):
        benchmark = self.runner.evaluate_multi_configurations(
            dataset=self.dataset,
            adapter=self.adapter,
            configurations=("dense", "lexical", "hybrid", "hybrid_reranked"),
            limit=5,
        )

        json_str = generate_multi_config_json_report(benchmark)
        parsed = json.loads(json_str)
        self.assertEqual(parsed["total_cases"], 35)
        self.assertIn("configuration_reports", parsed)

        md_str = generate_multi_config_markdown_report(benchmark)
        self.assertIn("# RAG Retrieval Architecture Benchmark Comparison", md_str)
        self.assertIn("## Configuration Comparison", md_str)
        self.assertIn("dense", md_str)
        self.assertIn("lexical", md_str)
        self.assertIn("hybrid", md_str)
        self.assertIn("hybrid_reranked", md_str)
        self.assertIn("Per-Subject Breakdown", md_str)


if __name__ == "__main__":
    unittest.main()
