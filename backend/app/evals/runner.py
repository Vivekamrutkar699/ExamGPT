"""
Independent retrieval evaluation runner for ExamGPT Phase 5A.
Evaluates candidate retrieval results deterministically without invoking LLMs or external services.
"""

from typing import Dict, Sequence, List, Any, Optional

from app.evals.schemas import (
    EvalCase,
    EvalDataset,
    CaseMetricScore,
    EvalRunReport,
)
from app.evals.metrics import (
    calculate_recall_at_k,
    calculate_mrr,
    calculate_context_relevance,
    aggregate_case_metrics,
)


class RetrievalEvalRunner:
    """
    Independent runner that evaluates candidate retrieval results against curated evaluation cases.
    Can evaluate pre-computed candidate lists or candidate mappings from any retrieval mode
    (dense, lexical, hybrid/RRF, or reranked).
    """

    def evaluate_single_case(
        self,
        case: EvalCase,
        retrieved_chunks: Sequence[Dict[str, Any]],
    ) -> CaseMetricScore:
        """
        Evaluate a single evaluation case against a list of retrieved chunks.
        Chunks should be dicts containing at minimum 'chunk_id', with optional 'content' and 'unit_tag'.
        """
        # Extract ordered chunk IDs
        retrieved_ids = [str(c.get("chunk_id", "")) for c in retrieved_chunks if c.get("chunk_id")]

        # Calculate deterministic metrics
        recall_at_3 = calculate_recall_at_k(retrieved_ids, case.golden_chunk_ids, k=3)
        recall_at_5 = calculate_recall_at_k(retrieved_ids, case.golden_chunk_ids, k=5)
        mrr = calculate_mrr(retrieved_ids, case.golden_chunk_ids)
        context_rel = calculate_context_relevance(
            retrieved_chunks=retrieved_chunks,
            expected_concepts=case.expected_concepts,
            expected_unit=case.unit,
        )

        golden_set = set(case.golden_chunk_ids)
        retrieved_set = set(retrieved_ids)
        missed = sorted(list(golden_set - retrieved_set))

        # Check matched concept keywords
        matched_concepts = []
        full_retrieved_text = " ".join(str(c.get("content", "")).lower() for c in retrieved_chunks)
        for concept in case.expected_concepts:
            if concept.lower() in full_retrieved_text:
                matched_concepts.append(concept)

        has_relevant = mrr > 0.0

        return CaseMetricScore(
            case_id=case.case_id,
            subject=case.subject,
            unit=case.unit,
            query=case.query,
            recall_at_3=recall_at_3,
            recall_at_5=recall_at_5,
            mrr=mrr,
            context_relevance=context_rel,
            golden_chunk_ids=case.golden_chunk_ids,
            retrieved_chunk_ids=retrieved_ids,
            missed_golden_chunk_ids=missed,
            matched_concepts=matched_concepts,
            has_relevant_chunk=has_relevant,
        )

    def evaluate_dataset(
        self,
        dataset: EvalDataset,
        retrieval_candidates: Dict[str, Sequence[Dict[str, Any]]],
    ) -> EvalRunReport:
        """
        Evaluate the entire dataset against a mapping of case_id -> list of retrieved chunks.
        If a case_id is missing from candidates, it is evaluated with empty retrieved chunks (all zero scores).
        """
        case_scores: List[CaseMetricScore] = []
        failures: List[CaseMetricScore] = []

        for case in dataset.cases:
            chunks = retrieval_candidates.get(case.case_id, [])
            score = self.evaluate_single_case(case, chunks)
            case_scores.append(score)

            # Record failure if no golden chunk was retrieved at all
            if not score.has_relevant_chunk or score.recall_at_5 == 0.0:
                failures.append(score)

        aggregate = aggregate_case_metrics(case_scores)

        return EvalRunReport(
            dataset_name=dataset.dataset_name,
            dataset_version=dataset.version,
            corpus_version=dataset.corpus_version,
            aggregate_metrics=aggregate,
            case_scores=case_scores,
            failures=failures,
        )
