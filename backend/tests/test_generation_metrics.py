"""
Deterministic unit tests for ExamGPT Phase 6A:
Generation + Grounding Evaluation Foundation.

Tests cover:
- Citation extraction ([Source X, Page Y] canonical syntax)
- Citation validation (bounds, page match, mismatch, invalid index)
- Concept coverage (token-safe, normalization, plural/singular)
- Grounded concept coverage (hallucination detection: in-answer vs in-context)
- Confidence format compliance (single vs multiple, valid levels, fallback format)
- Full metrics computation
- Empty inputs and edge cases
"""

import unittest
from app.evals.generation_schemas import CitationResult, GenerationMetrics
from app.evals.generation_metrics import (
    extract_citations,
    validate_citations,
    calculate_concept_coverage,
    calculate_grounded_concept_coverage,
    calculate_confidence_compliance,
    compute_generation_metrics,
    normalize_text,
)


class TestGenerationMetrics(unittest.TestCase):
    """Test pure deterministic generation metrics."""

    def setUp(self):
        self.mock_chunks = [
            {
                "chunk_id": "chunk_001",
                "content": "A Linker combines object modules into an executable binary image. It performs symbol relocation.",
                "metadata": {"page": 3, "document_name": "SPOS_Notes.pdf"}
            },
            {
                "chunk_id": "chunk_002",
                "content": "Loaders place executable images into main RAM memory.",
                "metadata": {"page": 7, "document_name": "SPOS_Notes.pdf"}
            }
        ]

    # -------------------------------------------------------------
    # Citation Extraction Tests
    # -------------------------------------------------------------

    def test_extract_citations_no_citations(self):
        text = "This answer contains no source citations at all."
        self.assertEqual(extract_citations(text), [])

    def test_extract_citations_single_valid(self):
        text = "Linkers resolve external symbols [Source 1, Page 3]."
        cits = extract_citations(text)
        self.assertEqual(len(cits), 1)
        self.assertEqual(cits[0], ("[Source 1, Page 3]", 1, 3))

    def test_extract_citations_multiple_valid(self):
        text = (
            "Linkers combine modules [Source 1, Page 3]. "
            "Loaders place the image into memory [Source 2, Page 7]."
        )
        cits = extract_citations(text)
        self.assertEqual(len(cits), 2)
        self.assertEqual(cits[0], ("[Source 1, Page 3]", 1, 3))
        self.assertEqual(cits[1], ("[Source 2, Page 7]", 2, 7))

    def test_extract_citations_duplicate_citations(self):
        text = (
            "First claim [Source 1, Page 3]. "
            "Second claim [Source 1, Page 3]."
        )
        cits = extract_citations(text)
        self.assertEqual(len(cits), 2)
        self.assertEqual(cits[0][0], "[Source 1, Page 3]")
        self.assertEqual(cits[1][0], "[Source 1, Page 3]")

    def test_extract_citations_malformed(self):
        # Missing commas, missing 'Page', or non-numeric indices should not match canonical pattern
        text = "Malformed [Source 1] and [Source 1, p. 3] and (Source 1, Page 3)."
        cits = extract_citations(text)
        self.assertEqual(len(cits), 0)

    # -------------------------------------------------------------
    # Citation Validation Tests
    # -------------------------------------------------------------

    def test_validate_citations_valid(self):
        raw_cits = [("[Source 1, Page 3]", 1, 3), ("[Source 2, Page 7]", 2, 7)]
        results = validate_citations(raw_cits, self.mock_chunks)
        self.assertEqual(len(results), 2)
        self.assertTrue(results[0].valid_source_index)
        self.assertTrue(results[0].valid_page)
        self.assertTrue(results[0].matches_retrieved_source)
        self.assertEqual(results[0].source_chunk_id, "chunk_001")

        self.assertTrue(results[1].valid_source_index)
        self.assertTrue(results[1].valid_page)
        self.assertTrue(results[1].matches_retrieved_source)
        self.assertEqual(results[1].source_chunk_id, "chunk_002")

    def test_validate_citations_invalid_source_index(self):
        # Index 99 does not exist in 2-chunk retrieval
        raw_cits = [("[Source 99, Page 3]", 99, 3), ("[Source 0, Page 3]", 0, 3)]
        results = validate_citations(raw_cits, self.mock_chunks)
        self.assertFalse(results[0].valid_source_index)
        self.assertFalse(results[0].matches_retrieved_source)
        self.assertIsNone(results[0].source_chunk_id)

        self.assertFalse(results[1].valid_source_index)
        self.assertFalse(results[1].matches_retrieved_source)

    def test_validate_citations_page_mismatch(self):
        # Source 1 exists (page 3), but cited as page 99
        raw_cits = [("[Source 1, Page 99]", 1, 99)]
        results = validate_citations(raw_cits, self.mock_chunks)
        self.assertTrue(results[0].valid_source_index)
        self.assertFalse(results[0].matches_retrieved_source)

    def test_validate_citations_empty_chunks(self):
        raw_cits = [("[Source 1, Page 3]", 1, 3)]
        results = validate_citations(raw_cits, [])
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0].valid_source_index)
        self.assertFalse(results[0].matches_retrieved_source)

    # -------------------------------------------------------------
    # Concept Coverage Tests
    # -------------------------------------------------------------

    def test_concept_coverage_fully_covered(self):
        answer = "A linker combines object modules and performs symbol relocation."
        concepts = ["linker", "object modules", "relocation"]
        cov = calculate_concept_coverage(answer, concepts)
        self.assertEqual(cov, 1.0)

    def test_concept_coverage_partially_covered(self):
        answer = "A linker combines object modules."
        concepts = ["linker", "object modules", "compiler", "loader"]
        # 2 of 4 concepts matched
        cov = calculate_concept_coverage(answer, concepts)
        self.assertEqual(cov, 0.5)

    def test_concept_coverage_none_covered(self):
        answer = "Completely unrelated database query information."
        concepts = ["linker", "loader", "relocation"]
        cov = calculate_concept_coverage(answer, concepts)
        self.assertEqual(cov, 0.0)

    def test_concept_coverage_token_safe_plural_and_normalization(self):
        # "protocol" matches "protocols", case insensitive, unicode normalized
        answer = "TCP and UDP are transport layer protocols."
        concepts = ["protocol", "TCP"]
        cov = calculate_concept_coverage(answer, concepts)
        self.assertEqual(cov, 1.0)

    def test_concept_coverage_empty_inputs(self):
        self.assertEqual(calculate_concept_coverage("", ["linker"]), 0.0)
        self.assertEqual(calculate_concept_coverage("Some answer", []), 0.0)
        self.assertEqual(calculate_concept_coverage("", []), 0.0)

    # -------------------------------------------------------------
    # Grounded Concept Coverage Tests
    # -------------------------------------------------------------

    def test_grounded_concept_coverage_all_grounded(self):
        # Concepts present in both answer and retrieved context
        answer = "A linker performs symbol relocation on object modules."
        concepts = ["linker", "object modules", "relocation"]
        cov = calculate_grounded_concept_coverage(answer, concepts, self.mock_chunks)
        self.assertEqual(cov, 1.0)

    def test_grounded_concept_coverage_hallucination_penalty(self):
        # "compiler" is in the answer, but NOT present in the retrieved context
        answer = "A linker and compiler perform symbol relocation."
        concepts = ["linker", "relocation", "compiler"]
        # "linker" and "relocation" are in both; "compiler" is only in the answer
        cov = calculate_grounded_concept_coverage(answer, concepts, self.mock_chunks)
        # 2 of 3 grounded -> 0.6667
        self.assertEqual(cov, 0.6667)

    def test_grounded_concept_coverage_concept_in_context_not_answer(self):
        # "loader" is in context, but student didn't include it in answer
        answer = "A linker handles object modules."
        concepts = ["linker", "loader"]
        # only "linker" is in both -> 1 of 2 = 0.5
        cov = calculate_grounded_concept_coverage(answer, concepts, self.mock_chunks)
        self.assertEqual(cov, 0.5)

    def test_grounded_concept_coverage_empty_inputs(self):
        self.assertEqual(calculate_grounded_concept_coverage("", ["linker"], self.mock_chunks), 0.0)
        self.assertEqual(calculate_grounded_concept_coverage("answer", [], self.mock_chunks), 0.0)
        self.assertEqual(calculate_grounded_concept_coverage("answer", ["linker"], []), 0.0)

    # -------------------------------------------------------------
    # Confidence Compliance Tests
    # -------------------------------------------------------------

    def test_confidence_compliance_valid_single_line(self):
        answer = "The explanation goes here.\n\nConfidence: High"
        self.assertEqual(calculate_confidence_compliance(answer), 1.0)

        answer_med = "The explanation goes here.\n\nConfidence: Medium"
        self.assertEqual(calculate_confidence_compliance(answer_med), 1.0)

        answer_low = "The explanation goes here.\n\nConfidence: Low"
        self.assertEqual(calculate_confidence_compliance(answer_low), 1.0)

    def test_confidence_compliance_production_fallback(self):
        answer = "Confidence: Low. Insufficient evidence in uploaded documents to answer."
        self.assertEqual(calculate_confidence_compliance(answer), 1.0)

    def test_confidence_compliance_multiple_confidence_lines(self):
        # Ambiguous output with multiple confidence lines should fail
        answer = "Intro.\nConfidence: High\nBody.\nConfidence: Low"
        self.assertEqual(calculate_confidence_compliance(answer), 0.0)

    def test_confidence_compliance_missing(self):
        answer = "The explanation goes here without any confidence declaration."
        self.assertEqual(calculate_confidence_compliance(answer), 0.0)

    def test_confidence_compliance_empty(self):
        self.assertEqual(calculate_confidence_compliance(""), 0.0)

    # -------------------------------------------------------------
    # Full Metrics Computation Tests
    # -------------------------------------------------------------

    def test_compute_generation_metrics_complete_good_answer(self):
        answer = (
            "A Linker combines object modules into an executable binary image [Source 1, Page 3].\n"
            "Loaders place the image into RAM [Source 2, Page 7].\n\n"
            "Confidence: High"
        )
        concepts = ["linker", "loader", "executable", "ram"]
        metrics, cit_results = compute_generation_metrics(
            answer=answer,
            expected_concepts=concepts,
            retrieved_chunks=self.mock_chunks,
        )

        self.assertEqual(metrics.concept_coverage, 1.0)
        self.assertEqual(metrics.grounded_concept_coverage, 1.0)
        self.assertEqual(metrics.citation_validity, 1.0)
        self.assertEqual(metrics.citation_source_match, 1.0)
        self.assertEqual(metrics.confidence_format_compliance, 1.0)
        self.assertEqual(len(cit_results), 2)


if __name__ == "__main__":
    unittest.main()
