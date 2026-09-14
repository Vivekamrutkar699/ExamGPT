"""
Deterministic Post-Processing Normalizer for ExamGPT Phase 6C.

STRICT CONSTRAINTS:
1. Do NOT invent citations.
2. Do NOT assign a citation to a claim that the model did not cite.
3. Do NOT create semantic facts or modify technical explanations.
4. ONLY perform deterministic format normalization on:
   - Confidence indicator lines (e.g., stripping Markdown bolding/asterisks/headings).
   - Minor syntax variations of existing inline citation markers (e.g., [Source [1], Page 3] or (Source 1, Page 3)).
"""

import re


# Matches markdown-bolded, heading-styled, or stylized confidence lines:
# Examples:
#   **Confidence**: High
#   **Confidence:** High
#   **Confidence: High**
#   ### Confidence: High
#   *Confidence*: High
#   Confidence : High
CONFIDENCE_NORMALIZATION_REGEX = re.compile(
    r'^\s*(?:#{1,6}\s*)?(?:\*{1,2})?Confidence(?:\*{1,2})?\s*(?::(?:\*{1,2})?|(?:\*{1,2})?:)\s*(?:\*{1,2})?(High|Medium|Low)(?:\*{1,2})?\s*$',
    re.IGNORECASE | re.MULTILINE
)

# Standalone confidence headers immediately preceding a confidence line:
# e.g. "**Confidence**\n\nConfidence: High" or "### Confidence\nConfidence: High"
CONFIDENCE_STANDALONE_HEADER_REGEX = re.compile(
    r'^\s*(?:#{1,6}\s*)?(?:\*{1,2})?Confidence(?:\*{1,2})?\s*\n+(?=Confidence:\s*(?:High|Medium|Low))',
    re.IGNORECASE | re.MULTILINE
)

# Matches any formatting/markdown variations where model explicitly cited Source X and Page Y:
# Examples:
#   **Source [1], Page 3**: -> [Source 1, Page 3]
#   [Source [1], Page 4]   -> [Source 1, Page 4]
#   [Source 1: Page 4]    -> [Source 1, Page 4]
#   [Source 1, page 4]    -> [Source 1, Page 4]
#   (Source 1, Page 4)    -> [Source 1, Page 4]
CITATION_FLEXIBLE_NORMALIZATION_REGEX = re.compile(
    r'(?:\*{1,2})?(?:\[|\()?Source\s+(?:\[(\d+)\]|(\d+))[,:]?\s*(?:Page|page)\s+(\d+)(?:\]|\))?(?:\*{1,2})?:?',
    re.IGNORECASE
)


def normalize_generation_formatting(text: str) -> str:
    """
    Apply deterministic formatting normalization without altering content.
    """
    if not text:
        return text

    normalized = text

    # 1. Normalize malformed citation syntax (only where model already explicitly cited Source X and Page Y)
    def replace_citation(match: re.Match) -> str:
        s = match.group(1) or match.group(2)
        p = match.group(3)
        return f"[Source {s}, Page {p}]"

    normalized = CITATION_FLEXIBLE_NORMALIZATION_REGEX.sub(replace_citation, normalized)

    # 2. Remove redundant standalone header line if followed by Confidence line
    normalized = CONFIDENCE_STANDALONE_HEADER_REGEX.sub('', normalized)

    # 3. Normalize confidence line formatting (e.g. **Confidence**: High -> Confidence: High)
    def replace_confidence(match: re.Match) -> str:
        level = match.group(1).capitalize()
        return f"Confidence: {level}"

    normalized = CONFIDENCE_NORMALIZATION_REGEX.sub(replace_confidence, normalized)

    return normalized
