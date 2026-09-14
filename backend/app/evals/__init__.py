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

from app.evals.generation_schemas import (
    CitationResult,
    GenerationMetrics,
    GenerationEvalResult,
)
from app.evals.generation_metrics import (
    extract_citations,
    validate_citations,
    calculate_concept_coverage,
    calculate_grounded_concept_coverage,
    calculate_confidence_compliance,
    compute_generation_metrics,
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
    "CitationResult",
    "GenerationMetrics",
    "GenerationEvalResult",
    "extract_citations",
    "validate_citations",
    "calculate_concept_coverage",
    "calculate_grounded_concept_coverage",
    "calculate_confidence_compliance",
    "compute_generation_metrics",
]
