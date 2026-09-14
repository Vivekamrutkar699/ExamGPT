"""
Deterministic retrieval metrics for ExamGPT Phase 5A evaluation harness.

Definitions:
- Recall@k:
    number of golden relevant chunks retrieved in top-k / number of golden relevant chunks.
- MRR (Mean Reciprocal Rank):
    reciprocal rank of the first relevant retrieved chunk (1 / rank), or 0.0 if no relevant chunk retrieved.
- Context Relevance:
    deterministic proxy metric: proportion of retrieved chunks that contain at least one of the
    explicitly labelled expected concept keywords or match the target unit metadata.
    NOTE: This is a deterministic lexical/metadata proxy, NOT semantic relevance and NOT an LLM judge.
"""

import math
from typing import List, Dict, Optional, Sequence, Any
from app.evals.schemas import CaseMetricScore, AggregateEvalMetrics


def calculate_recall_at_k(
    retrieved_chunk_ids: Sequence[str],
    golden_chunk_ids: Sequence[str],
    k: int,
) -> float:
    """
    Calculate Recall@k:
        number of golden relevant chunks retrieved in top-k / number of golden relevant chunks.

    Edge cases handled:
    - golden_chunk_ids is empty: returns 0.0.
    - k <= 0: returns 0.0.
    - retrieved_chunk_ids is empty: returns 0.0.
    - duplicates in retrieved_chunk_ids: deduplicated preserving first occurrence in top-k.
    - k larger than retrieved count: considers all available retrieved items up to k.
    - result is strictly bounded in [0.0, 1.0] and rounded to 4 decimals.
    """
    if not golden_chunk_ids or k <= 0 or not retrieved_chunk_ids:
        return 0.0

    golden_set = set(golden_chunk_ids)
    if not golden_set:
        return 0.0

    # Consider top-k retrieved items. Use an ordered deduplication to avoid double counting.
    seen = set()
    top_k_unique = []
    for cid in retrieved_chunk_ids:
        if cid not in seen:
            seen.add(cid)
            top_k_unique.append(cid)
        if len(top_k_unique) >= k:
            break

    hits = sum(1 for cid in top_k_unique if cid in golden_set)
    recall = hits / float(len(golden_set))
    return round(min(1.0, max(0.0, recall)), 4)


def calculate_mrr(
    retrieved_chunk_ids: Sequence[str],
    golden_chunk_ids: Sequence[str],
) -> float:
    """
    Calculate Reciprocal Rank (RR) for a single query:
        1.0 / rank (1-indexed) of the first golden chunk retrieved, or 0.0 if no golden chunk is retrieved.

    Edge cases handled:
    - golden_chunk_ids is empty: returns 0.0.
    - retrieved_chunk_ids is empty: returns 0.0.
    - duplicate IDs: deduplicated preserving first appearance.
    - result is strictly bounded in [0.0, 1.0] and rounded to 4 decimals.
    """
    if not golden_chunk_ids or not retrieved_chunk_ids:
        return 0.0

    golden_set = set(golden_chunk_ids)
    if not golden_set:
        return 0.0

    seen = set()
    deduped_retrieved = []
    for cid in retrieved_chunk_ids:
        if cid not in seen:
            seen.add(cid)
            deduped_retrieved.append(cid)

    for rank, cid in enumerate(deduped_retrieved, start=1):
        if cid in golden_set:
            rr = 1.0 / float(rank)
            return round(min(1.0, max(0.0, rr)), 4)

    return 0.0


def calculate_context_relevance(
    retrieved_chunks: Sequence[Dict[str, Any]],
    expected_concepts: Sequence[str],
    expected_unit: Optional[str] = None,
) -> float:
    """
    Calculate deterministic Context Relevance proxy metric:
    Proportion of retrieved chunks that contain at least one of the explicitly labelled
    expected concepts (case-insensitive substring match) or match the expected unit tag.

    NOTE: This is a deterministic lexical/metadata proxy, NOT semantic relevance and NOT an LLM judge.

    Edge cases handled:
    - retrieved_chunks is empty: returns 0.0.
    - expected_concepts is empty and expected_unit is None: returns 0.0.
    - non-string chunk content safely cast.
    - result is strictly bounded in [0.0, 1.0] and rounded to 4 decimals.
    """
    if not retrieved_chunks:
        return 0.0

    clean_concepts = [c.strip().lower() for c in expected_concepts if c and c.strip()]
    target_unit = expected_unit.strip().lower() if expected_unit and expected_unit.strip() else None

    if not clean_concepts and not target_unit:
        return 0.0

    relevant_count = 0
    for chunk in retrieved_chunks:
        content = str(chunk.get("content", "")).lower()
        chunk_unit = str(chunk.get("unit_tag") or chunk.get("unit") or "").strip().lower()

        # Check unit tag match
        unit_match = bool(target_unit and target_unit == chunk_unit)

        # Check concept keyword presence
        concept_match = any(concept in content for concept in clean_concepts)

        if unit_match or concept_match:
            relevant_count += 1

    relevance = relevant_count / float(len(retrieved_chunks))
    return round(min(1.0, max(0.0, relevance)), 4)


def aggregate_case_metrics(
    case_scores: Sequence[CaseMetricScore],
) -> AggregateEvalMetrics:
    """
    Safely aggregate individual case metric scores into dataset-wide summary statistics.
    Handles empty lists, non-finite values, and zeroes safely.
    """
    if not case_scores:
        return AggregateEvalMetrics(
            total_cases=0,
            mean_recall_at_3=0.0,
            mean_recall_at_5=0.0,
            mean_mrr=0.0,
            mean_context_relevance=0.0,
            perfect_recall_at_3_count=0,
            perfect_recall_at_5_count=0,
            zero_mrr_count=0,
        )

    def _safe_float(val: Any) -> float:
        try:
            f = float(val)
            return f if math.isfinite(f) else 0.0
        except (ValueError, TypeError):
            return 0.0

    valid_r3 = [_safe_float(cs.recall_at_3) for cs in case_scores]
    valid_r5 = [_safe_float(cs.recall_at_5) for cs in case_scores]
    valid_mrr = [_safe_float(cs.mrr) for cs in case_scores]
    valid_cr = [_safe_float(cs.context_relevance) for cs in case_scores]

    n = float(len(case_scores))
    mean_r3 = sum(valid_r3) / n
    mean_r5 = sum(valid_r5) / n
    mean_mrr = sum(valid_mrr) / n
    mean_cr = sum(valid_cr) / n

    perfect_r3 = sum(1 for cs in case_scores if _safe_float(cs.recall_at_3) >= 1.0)
    perfect_r5 = sum(1 for cs in case_scores if _safe_float(cs.recall_at_5) >= 1.0)
    zero_mrr = sum(1 for cs in case_scores if _safe_float(cs.mrr) == 0.0)

    return AggregateEvalMetrics(
        total_cases=len(case_scores),
        mean_recall_at_3=round(mean_r3, 4),
        mean_recall_at_5=round(mean_r5, 4),
        mean_mrr=round(mean_mrr, 4),
        mean_context_relevance=round(mean_cr, 4),
        perfect_recall_at_3_count=perfect_r3,
        perfect_recall_at_5_count=perfect_r5,
        zero_mrr_count=zero_mrr,
    )
