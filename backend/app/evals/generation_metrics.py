"""
Pure deterministic evaluation functions for ExamGPT Phase 6A:
Generation + Grounding Evaluation.

Metrics implemented:
- extract_citations: Strict regex parser for canonical [Source X, Page Y] tags.
- validate_citations: Checks source index bounds (1..k) and cited page vs chunk metadata.
- calculate_concept_coverage: Robust, token/boundary-safe expected concept coverage in answer.
- calculate_grounded_concept_coverage: Deterministic proxy checking whether expected concepts
  appear in both the answer and the retrieved study context.
  NOTE: This is an exact lexical/context overlap proxy, NOT semantic faithfulness.
- calculate_confidence_compliance: Verifies exactly one valid Confidence declaration.
"""

import re
import unicodedata
from typing import List, Dict, Sequence, Any, Tuple, Optional

from app.evals.generation_schemas import CitationResult, GenerationMetrics


# Canonical citation regex: [Source X, Page Y] (case-insensitive, strict comma and whitespace)
CITATION_PATTERN = re.compile(
    r'\[Source\s+(\d+),\s+Page\s+(\d+)\]',
    re.IGNORECASE
)

# Confidence patterns
CONFIDENCE_STANDARD_PATTERN = re.compile(
    r'^\s*Confidence:\s*(High|Medium|Low)\s*$',
    re.IGNORECASE | re.MULTILINE
)

# Production fallback pattern:
# "Confidence: Low. Insufficient evidence in uploaded documents to answer."
CONFIDENCE_FALLBACK_PATTERN = re.compile(
    r'Confidence:\s*Low\.\s*Insufficient\s+evidence\s+in\s+uploaded\s+documents\s+to\s+answer',
    re.IGNORECASE
)


def normalize_text(text: str) -> str:
    """
    Standardize text for deterministic comparison:
    - Unicode normalization (NFKD)
    - Lowercase / casefold
    - Normalize apostrophes/dashes/punctuation
    - Collapse multiple whitespace to single space
    """
    if not text:
        return ""
    # Unicode decomposition
    normalized = unicodedata.normalize("NFKD", text)
    # Convert to lowercase
    normalized = normalized.casefold()
    # Normalize curved apostrophes and quotes
    normalized = re.sub(r"[''ʻʼ]", "'", normalized)
    normalized = re.sub(r'[""«»]', '"', normalized)
    # Replace non-alphanumeric punctuation with spaces except hyphens/underscores inside words
    normalized = re.sub(r'[^\w\s-]', ' ', normalized)
    # Collapse multiple whitespace
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized


def _concept_in_text(concept: str, normalized_text: str) -> bool:
    """
    Boundary-safe check if a concept is represented in normalized text.
    Handles exact phrase match, lemmatized/plural variations (e.g. protocol vs protocols).
    """
    norm_concept = normalize_text(concept)
    if not norm_concept or not normalized_text:
        return False

    # 1. Exact phrase boundary match
    escaped = re.escape(norm_concept)
    if re.search(rf'\b{escaped}\b', normalized_text):
        return True

    # 2. Simple plural / singular heuristic if single word
    if ' ' not in norm_concept:
        if norm_concept.endswith('s') and len(norm_concept) > 3:
            singular = norm_concept[:-1]
            if re.search(rf'\b{re.escape(singular)}\b', normalized_text):
                return True
        else:
            plural = norm_concept + 's'
            if re.search(rf'\b{re.escape(plural)}\b', normalized_text):
                return True

    # 3. Multi-word phrase: verify all constituent key tokens appear in proximity
    tokens = norm_concept.split()
    if len(tokens) > 1:
        # Check if all tokens appear in the text
        if all(re.search(rf'\b{re.escape(t)}\b', normalized_text) for t in tokens):
            return True

    return False


def extract_citations(answer: str) -> List[Tuple[str, int, int]]:
    """
    Parse canonical citations of the form:
    [Source X, Page Y]

    Returns a list of tuples: (matched_text, source_index, page_number)
    """
    if not answer:
        return []

    citations = []
    for match in CITATION_PATTERN.finditer(answer):
        text = match.group(0)
        source_idx = int(match.group(1))
        page_num = int(match.group(2))
        citations.append((text, source_idx, page_num))

    return citations


def validate_citations(
    citations: Sequence[Tuple[str, int, int]],
    retrieved_chunks: Sequence[Dict[str, Any]],
) -> List[CitationResult]:
    """
    Validate parsed citations against the ordered list of retrieved chunks (1-indexed).
    Checks:
    - source_index is >= 1 and <= len(retrieved_chunks)
    - page is a positive integer
    - cited page matches chunk metadata page
    """
    results: List[CitationResult] = []
    num_chunks = len(retrieved_chunks)

    for cit_text, src_idx, page_num in citations:
        # 1-indexed check
        is_valid_src = (1 <= src_idx <= num_chunks)
        is_valid_page = (page_num > 0)
        source_chunk_id = None
        matches_retrieved = False

        if is_valid_src:
            chunk = retrieved_chunks[src_idx - 1]
            source_chunk_id = str(chunk.get("chunk_id", ""))
            
            # Extract expected chunk page
            chunk_page = None
            if "metadata" in chunk and isinstance(chunk["metadata"], dict):
                chunk_page = chunk["metadata"].get("page")
            elif "page" in chunk:
                chunk_page = chunk["page"]

            # If page metadata exists, compare as integer
            if chunk_page is not None:
                try:
                    matches_retrieved = (int(chunk_page) == page_num)
                except (ValueError, TypeError):
                    matches_retrieved = False
            else:
                matches_retrieved = False

        results.append(CitationResult(
            citation_text=cit_text,
            source_index=src_idx,
            page=page_num,
            valid_source_index=is_valid_src,
            valid_page=is_valid_page,
            source_chunk_id=source_chunk_id,
            matches_retrieved_source=matches_retrieved,
        ))

    return results


def calculate_concept_coverage(
    answer: str,
    expected_concepts: Sequence[str],
) -> float:
    """
    Calculate the proportion of expected concepts represented in the answer.
    Returns a float in [0.0, 1.0], rounded to 4 decimals.
    If expected_concepts is empty, returns 0.0.
    """
    if not answer or not expected_concepts:
        return 0.0

    clean_concepts = [c.strip() for c in expected_concepts if c and c.strip()]
    if not clean_concepts:
        return 0.0

    normalized_answer = normalize_text(answer)
    if not normalized_answer:
        return 0.0

    hits = sum(
        1 for concept in clean_concepts
        if _concept_in_text(concept, normalized_answer)
    )

    ratio = hits / float(len(clean_concepts))
    return round(min(1.0, max(0.0, ratio)), 4)


def calculate_grounded_concept_coverage(
    answer: str,
    expected_concepts: Sequence[str],
    retrieved_chunks: Sequence[Dict[str, Any]],
) -> float:
    """
    For each expected concept:
    - Checks if represented in answer
    - Checks if supporting evidence for that concept exists in retrieved context
    - Counts concept as grounded only when both conditions are satisfied.

    NOTE: This metric is a deterministic concept/context overlap proxy,
    NOT true semantic faithfulness.

    Returns a float in [0.0, 1.0], rounded to 4 decimals.
    """
    if not answer or not expected_concepts or not retrieved_chunks:
        return 0.0

    clean_concepts = [c.strip() for c in expected_concepts if c and c.strip()]
    if not clean_concepts:
        return 0.0

    normalized_answer = normalize_text(answer)
    # Combine retrieved chunks content into normalized context
    all_context_content = " ".join(str(c.get("content", "")) for c in retrieved_chunks)
    normalized_context = normalize_text(all_context_content)

    if not normalized_answer or not normalized_context:
        return 0.0

    grounded_hits = 0
    for concept in clean_concepts:
        in_answer = _concept_in_text(concept, normalized_answer)
        in_context = _concept_in_text(concept, normalized_context)
        if in_answer and in_context:
            grounded_hits += 1

    ratio = grounded_hits / float(len(clean_concepts))
    return round(min(1.0, max(0.0, ratio)), 4)


def calculate_confidence_compliance(answer: str) -> float:
    """
    Verify that the answer contains exactly one valid confidence indicator:
    - Exactly one 'Confidence: High | Medium | Low' line
    - OR the exact production fallback message:
      'Confidence: Low. Insufficient evidence in uploaded documents to answer.'

    Returns 1.0 if compliant, else 0.0.
    """
    if not answer:
        return 0.0

    # Check fallback message first
    if CONFIDENCE_FALLBACK_PATTERN.search(answer):
        return 1.0

    # Check standard confidence lines
    matches = CONFIDENCE_STANDARD_PATTERN.findall(answer)
    if len(matches) == 1:
        return 1.0

    return 0.0


def compute_generation_metrics(
    answer: str,
    expected_concepts: Sequence[str],
    retrieved_chunks: Sequence[Dict[str, Any]],
) -> Tuple[GenerationMetrics, List[CitationResult]]:
    """
    Evaluate all generation metrics deterministically for an answer.
    """
    # 1. Concept Coverage
    concept_cov = calculate_concept_coverage(answer, expected_concepts)

    # 2. Grounded Concept Coverage
    grounded_cov = calculate_grounded_concept_coverage(
        answer=answer,
        expected_concepts=expected_concepts,
        retrieved_chunks=retrieved_chunks,
    )

    # 3. Citation Extraction & Validation
    parsed_citations = extract_citations(answer)
    citation_results = validate_citations(parsed_citations, retrieved_chunks)

    if not citation_results:
        # If no citations exist in the answer:
        # Validity and match are 0.0 because grounded engineering answers require citations
        cit_validity = 0.0
        cit_match = 0.0
    else:
        num_cits = float(len(citation_results))
        valid_src_count = sum(1 for c in citation_results if c.valid_source_index)
        match_src_count = sum(1 for c in citation_results if c.matches_retrieved_source)
        cit_validity = round(valid_src_count / num_cits, 4)
        cit_match = round(match_src_count / num_cits, 4)

    # 4. Confidence Compliance
    conf_comp = calculate_confidence_compliance(answer)

    metrics = GenerationMetrics(
        concept_coverage=concept_cov,
        grounded_concept_coverage=grounded_cov,
        citation_validity=cit_validity,
        citation_source_match=cit_match,
        confidence_format_compliance=conf_comp,
    )

    return metrics, citation_results
