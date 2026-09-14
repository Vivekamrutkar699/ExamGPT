"""
Evaluation schemas for ExamGPT RAG Retrieval Evaluation System (Phase 5A).
Provides pure Pydantic models for evaluation datasets, frozen corpus,
retrieval candidates, deterministic metric results, and benchmark reports.
"""

from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field


class FrozenCorpusChunk(BaseModel):
    """Represents a frozen, deterministic chunk in the evaluation corpus."""
    chunk_id: str
    subject: str
    unit: str
    document_name: str
    page: int
    content: str


class FrozenCorpus(BaseModel):
    """Root structure of the frozen evaluation corpus."""
    corpus_version: str
    description: str
    chunks: List[FrozenCorpusChunk]


class EvalCase(BaseModel):
    """
    A single curated SPPU engineering evaluation case.
    Strictly specifies query, target subject/unit, golden chunk references,
    and deterministic concept keywords.
    """
    case_id: str
    subject: str
    unit: str
    query: str
    golden_chunk_ids: List[str]
    expected_concepts: List[str]
    expected_characteristics: Optional[str] = None
    difficulty: Optional[str] = "medium"


class EvalDataset(BaseModel):
    """Curated collection of evaluation cases."""
    dataset_name: str
    version: str
    description: str
    corpus_version: str
    cases: List[EvalCase]


class RetrievedChunkCandidate(BaseModel):
    """Represents a single retrieved chunk candidate to be evaluated."""
    chunk_id: str
    content: Optional[str] = ""
    unit_tag: Optional[str] = None
    subject: Optional[str] = None
    category: Optional[str] = None
    score: Optional[float] = 0.0
    rank: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


class CaseMetricScore(BaseModel):
    """Deterministic evaluation metrics for a single case."""
    case_id: str
    subject: str
    unit: str
    query: str
    recall_at_3: float
    recall_at_5: float
    mrr: float
    context_relevance: float
    golden_chunk_ids: List[str]
    retrieved_chunk_ids: List[str]
    missed_golden_chunk_ids: List[str]
    matched_concepts: List[str]
    has_relevant_chunk: bool


class AggregateEvalMetrics(BaseModel):
    """Aggregated deterministic retrieval metrics across all evaluated cases."""
    total_cases: int
    mean_recall_at_3: float
    mean_recall_at_5: float
    mean_mrr: float
    mean_context_relevance: float
    perfect_recall_at_3_count: int
    perfect_recall_at_5_count: int
    zero_mrr_count: int


class EvalRunReport(BaseModel):
    """Full benchmark evaluation run report containing summary and details."""
    dataset_name: str
    dataset_version: str
    corpus_version: str
    aggregate_metrics: AggregateEvalMetrics
    case_scores: List[CaseMetricScore]
    failures: List[CaseMetricScore] = Field(default_factory=list)
