"""
ExamGPT Phase 5A Evaluation Package.
Deterministic evaluation harness for RAG retrieval quality.
"""

from app.evals.schemas import (
    EvalCase,
    EvalDataset,
    FrozenCorpus,
    FrozenCorpusChunk,
    CaseMetricScore,
    AggregateEvalMetrics,
    EvalRunReport,
)
from app.evals.metrics import (
    calculate_recall_at_k,
    calculate_mrr,
    calculate_context_relevance,
    aggregate_case_metrics,
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

__all__ = [
    "EvalCase",
    "EvalDataset",
    "FrozenCorpus",
    "FrozenCorpusChunk",
    "CaseMetricScore",
    "AggregateEvalMetrics",
    "EvalRunReport",
    "calculate_recall_at_k",
    "calculate_mrr",
    "calculate_context_relevance",
    "aggregate_case_metrics",
    "load_frozen_corpus",
    "load_eval_dataset",
    "validate_eval_dataset_integrity",
    "RetrievalEvalRunner",
    "generate_json_report",
    "generate_markdown_report",
]
