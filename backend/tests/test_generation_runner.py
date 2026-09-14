"""
Unit tests for ExamGPT Phase 6B:
RAG Generation & Grounding Evaluation Runner.

Tests verify:
1. Successful generation and metric evaluation.
2. Generation failure handling (Ollama connection error / exception).
3. Malformed generation response (empty, missing citations, missing confidence).
4. Deterministic metric integration.
5. Preservation of retrieved chunk metadata and rank.
6. Aggregate metric calculations.
7. Per-subject aggregation across multiple subjects.
8. Failure reporting and filtering logic.
9. Empty dataset handling without divide-by-zero errors.
10. Partial case failure handling.
11. Markdown report formatting.

NOTE: All tests mock the generation boundary and do NOT require a running Ollama server.
"""

import asyncio
import unittest
from typing import List, Dict, Any

from app.evals.schemas import EvalCase, EvalDataset
from app.evals.generation_schemas import (
    GenerationEvalResult,
    GenerationMetrics,
    PreservedRetrievedChunk,
    GenerationBenchmarkReport,
)
from app.evals.generation_runner import (
    GenerationEvalRunner,
    format_retrieval_context,
    generate_generation_markdown_report,
)


class DummyRetrievalAdapter:
    """Mock adapter returning deterministic fake chunks."""

    def __init__(self, chunks: List[Dict[str, Any]] = None):
        self.chunks = chunks or [
            {
                "chunk_id": "chunk_cn_u1_001",
                "content": "TCP is a connection-oriented, reliable transport protocol with flow control.",
                "category": "study",
                "metadata": {"document_name": "computer_networks.pdf", "page": 4},
                "score": 0.95,
            },
            {
                "chunk_id": "chunk_cn_u1_002",
                "content": "UDP is connectionless and does not guarantee reliable delivery.",
                "category": "study",
                "metadata": {"document_name": "computer_networks.pdf", "page": 6},
                "score": 0.85,
            },
        ]

    def retrieve(self, configuration: str, query: str, limit: int = 4) -> List[Dict[str, Any]]:
        return self.chunks[:limit]


class TestGenerationRunner(unittest.TestCase):
    """Test suite for GenerationEvalRunner without Ollama dependency."""

    def setUp(self):
        self.adapter = DummyRetrievalAdapter()
        self.sample_case_cn = EvalCase(
            case_id="EVAL-CN-001",
            subject="CN",
            unit="Unit 1",
            query="Explain TCP features and transport layer guarantees.",
            golden_chunk_ids=["chunk_cn_u1_001"],
            expected_concepts=["connection-oriented", "reliable transport", "flow control"],
        )
        self.sample_case_spos = EvalCase(
            case_id="EVAL-SPOS-001",
            subject="SPOS",
            unit="Unit 1",
            query="Explain the purpose of a linker.",
            golden_chunk_ids=["chunk_spos_u1_001"],
            expected_concepts=["linker", "symbol resolution", "relocation"],
        )

    def test_format_retrieval_context(self):
        chunks = [
            {
                "chunk_id": "c1",
                "content": "Test chunk 1",
                "category": "study",
                "metadata": {"document_name": "doc1.pdf", "page": 3},
            },
            {
                "chunk_id": "c2",
                "content": "Test chunk 2",
                "category": "study",
                "metadata": {"document_name": "doc2.pdf", "page": 7},
            },
        ]
        context = format_retrieval_context(chunks)
        self.assertIn("Source [1]: doc1.pdf, Page 3", context)
        self.assertIn("Source [2]: doc2.pdf, Page 7", context)
        self.assertIn("Chunk ID: c1", context)
        self.assertIn("Test chunk 1", context)

    def test_successful_generation(self):
        async def run_test():
            def mock_gen(query: str, context: str) -> str:
                return (
                    "TCP is a connection-oriented and reliable transport protocol with flow control "
                    "[Source 1, Page 4].\n\nConfidence: High"
                )

            runner = GenerationEvalRunner(
                adapter=self.adapter,
                generation_fn=mock_gen,
            )
            result = await runner.evaluate_single_case(self.sample_case_cn)

            self.assertTrue(result.generation_success)
            self.assertEqual(len(result.errors), 0)
            self.assertEqual(result.eval_id, "EVAL-CN-001")
            self.assertEqual(result.metrics.concept_coverage, 1.0)
            self.assertEqual(result.metrics.citation_validity, 1.0)
            self.assertEqual(result.metrics.citation_source_match, 1.0)
            self.assertEqual(result.metrics.confidence_format_compliance, 1.0)
            self.assertEqual(len(result.retrieved_chunks), 2)
            self.assertEqual(result.retrieved_chunks[0].chunk_id, "chunk_cn_u1_001")
            self.assertEqual(result.retrieved_chunks[0].page, 4)
            self.assertEqual(result.retrieved_chunks[0].rank, 1)

        asyncio.run(run_test())

    def test_generation_failure(self):
        async def run_test():
            def failing_gen(query: str, context: str) -> str:
                raise ConnectionError("Ollama server unavailable at http://localhost:11434")

            runner = GenerationEvalRunner(
                adapter=self.adapter,
                generation_fn=failing_gen,
            )
            result = await runner.evaluate_single_case(self.sample_case_cn)

            self.assertFalse(result.generation_success)
            self.assertEqual(len(result.errors), 1)
            self.assertIn("ConnectionError", result.errors[0])
            self.assertEqual(result.metrics.concept_coverage, 0.0)
            self.assertEqual(result.metrics.grounded_concept_coverage, 0.0)
            self.assertEqual(result.metrics.citation_validity, 0.0)
            self.assertEqual(result.metrics.confidence_format_compliance, 0.0)
            self.assertTrue(result.answer.startswith("[ERROR]"))

        asyncio.run(run_test())

    def test_malformed_generation_response(self):
        async def run_test():
            def malformed_gen(query: str, context: str) -> str:
                # Answer has no citations, no concepts, no confidence tag
                return "Just some text with no structure or answers."

            runner = GenerationEvalRunner(
                adapter=self.adapter,
                generation_fn=malformed_gen,
            )
            result = await runner.evaluate_single_case(self.sample_case_cn)

            self.assertTrue(result.generation_success)
            self.assertEqual(result.metrics.concept_coverage, 0.0)
            self.assertEqual(result.metrics.citation_validity, 0.0)
            self.assertEqual(result.metrics.citation_source_match, 0.0)
            self.assertEqual(result.metrics.confidence_format_compliance, 0.0)

        asyncio.run(run_test())

    def test_metric_integration(self):
        async def run_test():
            def mock_gen(query: str, context: str) -> str:
                # Partial concept coverage (only reliable transport), invalid page citation (Page 99)
                return "TCP provides reliable transport [Source 1, Page 99].\n\nConfidence: Medium"

            runner = GenerationEvalRunner(
                adapter=self.adapter,
                generation_fn=mock_gen,
            )
            result = await runner.evaluate_single_case(self.sample_case_cn)

            self.assertTrue(result.generation_success)
            # 1 of 3 concepts present -> 1/3 ~ 0.3333
            self.assertAlmostEqual(result.metrics.concept_coverage, 1 / 3, places=3)
            # Source 1 is valid index -> validity = 1.0
            self.assertEqual(result.metrics.citation_validity, 1.0)
            # Page 99 does not match chunk metadata page 4 -> source match = 0.0
            self.assertEqual(result.metrics.citation_source_match, 0.0)
            # Confidence: Medium is valid -> 1.0
            self.assertEqual(result.metrics.confidence_format_compliance, 1.0)

        asyncio.run(run_test())

    def test_partial_case_failures(self):
        async def run_test():
            # 1 case fails generation, 2 cases succeed
            def mock_gen(query: str, context: str) -> str:
                if "linker" in query:
                    raise RuntimeError("Ollama context length exceeded")
                return "TCP features.\n\nConfidence: Low"

            dataset = EvalDataset(
                dataset_name="Test Dataset",
                version="1.0.0",
                description="Test description",
                corpus_version="1.0.0",
                cases=[self.sample_case_cn, self.sample_case_spos],
            )
            runner = GenerationEvalRunner(
                adapter=self.adapter,
                generation_fn=mock_gen,
            )
            report = await runner.evaluate_dataset(dataset)

            self.assertEqual(report.aggregate_metrics.total_cases, 2)
            self.assertEqual(report.aggregate_metrics.successful_generation_count, 1)
            self.assertEqual(report.aggregate_metrics.failed_generation_count, 1)
            self.assertEqual(report.aggregate_metrics.successful_generation_rate, 0.5)

        asyncio.run(run_test())

    def test_retrieved_chunk_preservation(self):
        async def run_test():
            def mock_gen(query: str, context: str) -> str:
                return "Answer text.\n\nConfidence: Low"

            runner = GenerationEvalRunner(
                adapter=self.adapter,
                generation_fn=mock_gen,
            )
            result = await runner.evaluate_single_case(self.sample_case_cn)

            self.assertEqual(len(result.retrieved_chunks), 2)
            first_chunk = result.retrieved_chunks[0]
            self.assertEqual(first_chunk.chunk_id, "chunk_cn_u1_001")
            self.assertEqual(first_chunk.document_name, "computer_networks.pdf")
            self.assertEqual(first_chunk.page, 4)
            self.assertEqual(first_chunk.rank, 1)
            self.assertEqual(first_chunk.score, 0.95)
            self.assertIn("TCP is a connection-oriented", first_chunk.content)

        asyncio.run(run_test())

    def test_aggregate_and_per_subject_metrics(self):
        async def run_test():
            def mock_gen(query: str, context: str) -> str:
                if "TCP" in query:
                    return (
                        "TCP provides connection-oriented reliable transport and flow control "
                        "[Source 1, Page 4].\n\nConfidence: High"
                    )
                else:
                    # SPOS case fails generation
                    raise RuntimeError("Model timeout")

            dataset = EvalDataset(
                dataset_name="Test Dataset",
                version="1.0.0",
                description="Test description",
                corpus_version="1.0.0",
                cases=[self.sample_case_cn, self.sample_case_spos],
            )

            runner = GenerationEvalRunner(
                adapter=self.adapter,
                generation_fn=mock_gen,
            )
            report = await runner.evaluate_dataset(dataset)

            self.assertEqual(report.total_cases, 2)
            self.assertEqual(report.aggregate_metrics.successful_generation_count, 1)
            self.assertEqual(report.aggregate_metrics.failed_generation_count, 1)
            self.assertEqual(report.aggregate_metrics.successful_generation_rate, 0.5)

            # CN had full score (1.0), SPOS had 0.0 -> average = 0.5
            self.assertEqual(report.aggregate_metrics.mean_concept_coverage, 0.5)
            self.assertEqual(report.aggregate_metrics.confidence_compliance_rate, 0.5)

            # Per-subject breakdown
            self.assertIn("CN", report.subject_metrics)
            self.assertIn("SPOS", report.subject_metrics)
            self.assertEqual(report.subject_metrics["CN"].generation_success_rate, 1.0)
            self.assertEqual(report.subject_metrics["CN"].mean_concept_coverage, 1.0)
            self.assertEqual(report.subject_metrics["SPOS"].generation_success_rate, 0.0)
            self.assertEqual(report.subject_metrics["SPOS"].mean_concept_coverage, 0.0)

            # Failures list should contain the failing SPOS case
            self.assertTrue(any(f.eval_id == "EVAL-SPOS-001" for f in report.failures))

        asyncio.run(run_test())

    def test_empty_dataset_handling(self):
        async def run_test():
            dataset = EvalDataset(
                dataset_name="Empty Dataset",
                version="1.0.0",
                description="Test description",
                corpus_version="1.0.0",
                cases=[],
            )
            runner = GenerationEvalRunner(
                adapter=self.adapter,
                generation_fn=lambda q, c: "test",
            )
            report = await runner.evaluate_dataset(dataset)

            self.assertEqual(report.total_cases, 0)
            self.assertEqual(report.aggregate_metrics.total_cases, 0)
            self.assertEqual(report.aggregate_metrics.successful_generation_rate, 0.0)
            self.assertEqual(report.aggregate_metrics.mean_concept_coverage, 0.0)
            self.assertEqual(len(report.failures), 0)

        asyncio.run(run_test())

    def test_markdown_report_formatting(self):
        async def run_test():
            def mock_gen(query: str, context: str) -> str:
                return "TCP is connection-oriented [Source 1, Page 4].\n\nConfidence: High"

            dataset = EvalDataset(
                dataset_name="Test Markdown",
                version="1.0.0",
                description="Test description",
                corpus_version="1.0.0",
                cases=[self.sample_case_cn],
            )
            runner = GenerationEvalRunner(
                adapter=self.adapter,
                generation_fn=mock_gen,
            )
            report = await runner.evaluate_dataset(dataset)
            md = generate_generation_markdown_report(report)

            self.assertIn("# RAG Generation + Grounding Benchmark Report", md)
            self.assertIn("## Aggregate Metrics", md)
            self.assertIn("## Per-Subject Metrics", md)
            self.assertIn("## Failure Analysis", md)
            self.assertIn("CN", md)

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
