"""
Pydantic schemas for ExamGPT Phase 6A: Generation + Grounding Evaluation.
Defines deterministic schemas for citation parsing results, generation metrics,
and per-case generation evaluation results.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


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
        description="Proportion of parsed citations with a valid source index within 1..k (or 1.0 if no citations and none required)."
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
    question: str
    answer: str
    expected_concepts: List[str]
    retrieved_chunk_ids: List[str]
    metrics: GenerationMetrics
    citation_results: List[CitationResult] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
