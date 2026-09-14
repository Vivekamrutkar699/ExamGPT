"""
ExamGPT Phase 5A and 5B Evaluation Package.
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
    MultiConfigBenchmarkReport,
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
from app.evals.adapter import EvalRetrievalAdapter
from app.evals.runner import RetrievalEvalRunner
from app.evals.reporter import (
    generate_json_report,
    generate_markdown_report,
    generate_multi_config_json_report,
    generate_multi_config_markdown_report,
)

__all__ = [
    "EvalCase",
    "EvalDataset",
    "FrozenCorpus",
    "FrozenCorpusChunk",
    "CaseMetricScore",
    "AggregateEvalMetrics",
    "EvalRunReport",
    "MultiConfigBenchmarkReport",
    "calculate_recall_at_k",
    "calculate_mrr",
    "calculate_context_relevance",
    "aggregate_case_metrics",
    "load_frozen_corpus",
    "load_eval_dataset",
    "validate_eval_dataset_integrity",
    "EvalRetrievalAdapter",
    "RetrievalEvalRunner",
    "generate_json_report",
    "generate_markdown_report",
    "generate_multi_config_json_report",
    "generate_multi_config_markdown_report",
]
