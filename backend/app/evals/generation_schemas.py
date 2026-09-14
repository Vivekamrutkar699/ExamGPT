"""
Pydantic schemas for ExamGPT Phase 6A & 6B: Generation + Grounding Evaluation.
Defines deterministic schemas for citation parsing results, generation metrics,
per-case generation evaluation results, preserved chunk metadata, and aggregate benchmark reports.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class PreservedRetrievedChunk(BaseModel):
    """Preserved retrieved chunk details for evaluation reproducibility and error inspection."""
    chunk_id: str
    document_name: str
    page: int
    rank: int
    content: str
    score: Optional[float] = None


class CitationResult(BaseModel):
    """Represents a single parsed inline citation from a generated answer."""
    citation_text: str
    source_index: int
    page: Optional[int] = None
    valid_source_index: bool
    valid_page: bool
    source_chunk_id: Optional[str] = None
    matches_retrieved_source: bool


class GenerationMetrics(BaseModel):
    """
    Deterministic evaluation metrics for a generated answer.
    All ratio metrics are bounded in [0.0, 1.0].
    """
    concept_coverage: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Proportion of expected concepts represented in the answer."
    )
    grounded_concept_coverage: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Proportion of expected concepts present in both answer and retrieved context (proxy metric)."
    )
    citation_validity: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Proportion of parsed citations with a valid source index within 1..k."
    )
    citation_source_match: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Proportion of parsed citations whose cited page matches the chunk metadata page."
    )
    confidence_format_compliance: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="1.0 if exactly one valid Confidence: High|Medium|Low line exists, else 0.0."
    )


class GenerationEvalResult(BaseModel):
    """Full evaluation result for a single question-answer pair."""
    eval_id: str
    subject: str = ""
    unit: str = ""
    question: str
    answer: str
    expected_concepts: List[str]
    retrieved_chunk_ids: List[str]
    retrieved_chunks: List[PreservedRetrievedChunk] = Field(default_factory=list)
    metrics: GenerationMetrics
    citation_results: List[CitationResult] = Field(default_factory=list)
    generation_success: bool = True
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class SubjectGenerationSummary(BaseModel):
    """Aggregated generation metrics for an individual subject."""
    subject: str
    total_cases: int
    mean_concept_coverage: float
    mean_grounded_concept_coverage: float
    mean_citation_validity: float
    mean_citation_source_match: float
    confidence_compliance_rate: float
    generation_success_rate: float


class AggregateGenerationMetrics(BaseModel):
    """Aggregated generation evaluation metrics across all evaluated cases."""
    total_cases: int
    successful_generation_count: int
    failed_generation_count: int
    successful_generation_rate: float
    mean_concept_coverage: float
    mean_grounded_concept_coverage: float
    mean_citation_validity: float
    mean_citation_source_match: float
    confidence_compliance_rate: float


class GenerationBenchmarkReport(BaseModel):
    """Full generation benchmark evaluation report."""
    evaluation_scope: str = "Production RAG retrieval and Ollama generation evaluated on the frozen 35-case benchmark corpus."
    dataset_name: str
    dataset_version: str
    dataset_path: str
    corpus_version: str
    model: str
    temperature: float
    max_tokens: int
    timestamp: str
    total_cases: int
    aggregate_metrics: AggregateGenerationMetrics
    subject_metrics: Dict[str, SubjectGenerationSummary]
    case_results: List[GenerationEvalResult]
    failures: List[GenerationEvalResult] = Field(default_factory=list)
