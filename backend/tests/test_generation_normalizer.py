"""
Deterministic unit tests for ExamGPT Phase 6C generation formatting normalizer.
Tests cover:
- Confidence format normalization (bolding, headers, colons, capitalization)
- Citation syntax normalization (bracketed indices, parenthesis, colon variants)
- Strict non-fabrication guarantees (no citations added to uncited claims)
- Preservation of technical content, markdown tables, and formulas
- No requirement for Ollama or network access
"""

import unittest
from app.evals.generation_normalizer import normalize_generation_formatting


class TestGenerationNormalizer(unittest.TestCase):
    """Test deterministic post-processing normalizer."""

    def test_confidence_normalization_markdown_variants(self):
        """Verify markdown bolding and heading variants of Confidence are normalized."""
        variants = [
            ("**Confidence:** High", "Confidence: High"),
            ("**Confidence: High**", "Confidence: High"),
            ("**Confidence**: High", "Confidence: High"),
            ("*Confidence*: High", "Confidence: High"),
            ("### Confidence: High", "Confidence: High"),
            ("## Confidence: High", "Confidence: High"),
            ("Confidence : High", "Confidence: High"),
            ("**Confidence:** Medium", "Confidence: Medium"),
            ("**Confidence: Low**", "Confidence: Low"),
            ("Confidence: high", "Confidence: High"),
        ]
        for input_text, expected in variants:
            with self.subTest(input_text=input_text):
                res = normalize_generation_formatting(input_text)
                self.assertEqual(res.strip(), expected)

    def test_confidence_with_surrounding_answer_body(self):
        """Verify confidence line in a full answer body is normalized without altering body."""
        body = (
            "A Linker combines object modules into an executable.\n\n"
            "**Key functions:**\n"
            "- Symbol resolution\n"
            "- Relocation\n\n"
            "**Confidence:** High"
        )
        normalized = normalize_generation_formatting(body)
        expected_ending = "Confidence: High"
        self.assertTrue(normalized.endswith(expected_ending))
        self.assertIn("A Linker combines object modules into an executable.", normalized)
        self.assertIn("**Key functions:**", normalized)

    def test_confidence_standalone_header_deduplication(self):
        """Verify standalone header preceding confidence line is cleaned up."""
        text = (
            "Answers details here.\n\n"
            "**Confidence**\n\n"
            "Confidence: High"
        )
        normalized = normalize_generation_formatting(text)
        self.assertIn("Confidence: High", normalized)
        # Should not have duplicate standalone Confidence word before it
        lines = [line.strip() for line in normalized.splitlines() if line.strip()]
        self.assertEqual(lines[-1], "Confidence: High")
        self.assertNotEqual(lines[-2], "**Confidence**")

    def test_confidence_not_fabricated_when_missing(self):
        """Verify that when confidence line is omitted, normalizer does NOT invent one."""
        text = "This is a factual answer without any confidence statement."
        normalized = normalize_generation_formatting(text)
        self.assertEqual(normalized, text)
        self.assertNotIn("Confidence:", normalized)

    def test_citation_syntax_normalization(self):
        """Verify explicit model citations with bracket or colon syntax errors are normalized."""
        cases = [
            ("See [Source [1], Page 4] for details.", "See [Source 1, Page 4] for details."),
            ("Refer to **Source [1], Page 3**: in study guide.", "Refer to [Source 1, Page 3] in study guide."),
            ("Mentioned in (Source 2, Page 7).", "Mentioned in [Source 2, Page 7]."),
            ("Found in [Source 3: Page 12].", "Found in [Source 3, Page 12]."),
            ("As per [Source 1, page 5].", "As per [Source 1, Page 5]."),
        ]
        for input_text, expected in cases:
            with self.subTest(input_text=input_text):
                res = normalize_generation_formatting(input_text)
                self.assertEqual(res, expected)

    def test_citation_non_fabrication_guarantee(self):
        """Strict non-fabrication guarantee: uncited claims remain uncited."""
        uncited_text = (
            "A page fault occurs when a program attempts to access a block of memory "
            "that is not stored in the physical RAM. The operating system handles this "
            "by loading the required page from secondary storage into main memory."
        )
        normalized = normalize_generation_formatting(uncited_text)
        self.assertEqual(normalized, uncited_text)
        self.assertNotIn("[Source", normalized)

    def test_source_index_and_page_integrity(self):
        """Verify source numbers and page numbers are never altered or shifted."""
        text = "Process state is saved in PCB [Source 2, Page 14] and registers [Source 4, Page 22]."
        normalized = normalize_generation_formatting(text)
        self.assertIn("[Source 2, Page 14]", normalized)
        self.assertIn("[Source 4, Page 22]", normalized)

    def test_markdown_tables_and_formatting_preserved(self):
        """Verify markdown tables, bolding, code snippets, and structure are preserved."""
        table_text = (
            "| Feature | Paging | Segmentation |\n"
            "| :--- | :--- | :--- |\n"
            "| Block size | Fixed | Variable |\n"
            "| Programmer visibility | Invisible | Visible |\n\n"
            "Formula: `Physical Address = Frame * Size + Offset`\n\n"
            "**Confidence:** High"
        )
        normalized = normalize_generation_formatting(table_text)
        self.assertIn("| Feature | Paging | Segmentation |", normalized)
        self.assertIn("`Physical Address = Frame * Size + Offset`", normalized)
        self.assertTrue(normalized.endswith("Confidence: High"))

    def test_empty_and_none_handling(self):
        """Verify empty string or whitespace does not crash."""
        self.assertEqual(normalize_generation_formatting(""), "")
        self.assertEqual(normalize_generation_formatting("   "), "   ")


if __name__ == "__main__":
    unittest.main()
