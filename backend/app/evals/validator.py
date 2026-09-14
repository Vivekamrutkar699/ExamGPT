"""
Evaluation dataset loader and referential integrity validator for Phase 5A.
Ensures evaluation dataset integrity against the frozen evaluation corpus.
"""

import json
from pathlib import Path
from typing import Tuple, List, Set

from app.evals.schemas import EvalDataset, FrozenCorpus


EVAL_DATA_DIR = Path(__file__).resolve().parent / "data"
DEFAULT_CORPUS_PATH = EVAL_DATA_DIR / "frozen_eval_corpus.json"
DEFAULT_DATASET_PATH = EVAL_DATA_DIR / "sppu_engineering_eval_dataset.json"


def load_frozen_corpus(corpus_path: Path = DEFAULT_CORPUS_PATH) -> FrozenCorpus:
    """Load and parse the frozen evaluation corpus from disk."""
    if not corpus_path.exists():
        raise FileNotFoundError(f"Frozen corpus file not found at: {corpus_path}")
    with open(corpus_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return FrozenCorpus(**data)


def load_eval_dataset(dataset_path: Path = DEFAULT_DATASET_PATH) -> EvalDataset:
    """Load and parse the curated evaluation dataset from disk."""
    if not dataset_path.exists():
        raise FileNotFoundError(f"Evaluation dataset file not found at: {dataset_path}")
    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return EvalDataset(**data)


def validate_eval_dataset_integrity(
    dataset: EvalDataset,
    corpus: FrozenCorpus,
    expected_case_count: int = 35,
) -> Tuple[bool, List[str]]:
    """
    Strict validation of dataset referential integrity:
    1. Dataset case count matches expected count (default 35).
    2. Case IDs are completely unique.
    3. Every case has non-empty query.
    4. Every case has non-empty subject and unit.
    5. Every case has non-empty expected concepts.
    6. Every case has at least one golden chunk ID.
    7. EVERY golden chunk ID exists in the frozen evaluation corpus (no invented IDs).
    8. Corpus version referenced in dataset matches corpus version.

    Returns:
        (is_valid: bool, error_messages: List[str])
    """
    errors: List[str] = []

    # Check corpus version alignment
    if dataset.corpus_version != corpus.corpus_version:
        errors.append(
            f"Dataset corpus_version '{dataset.corpus_version}' does not match "
            f"frozen corpus_version '{corpus.corpus_version}'"
        )

    # Check case count
    if len(dataset.cases) != expected_case_count:
        errors.append(
            f"Expected {expected_case_count} evaluation cases, but found {len(dataset.cases)}"
        )

    # Collect valid corpus chunk IDs
    corpus_chunk_ids: Set[str] = {c.chunk_id for c in corpus.chunks}

    seen_case_ids: Set[str] = set()
    for idx, case in enumerate(dataset.cases):
        # Unique case IDs
        if case.case_id in seen_case_ids:
            errors.append(f"Case index {idx}: duplicate case_id '{case.case_id}'")
        seen_case_ids.add(case.case_id)

        # Non-empty query
        if not case.query or not case.query.strip():
            errors.append(f"Case '{case.case_id}': empty query")

        # Non-empty subject and unit
        if not case.subject or not case.subject.strip():
            errors.append(f"Case '{case.case_id}': empty subject")
        if not case.unit or not case.unit.strip():
            errors.append(f"Case '{case.case_id}': empty unit")

        # Non-empty expected concepts
        if not case.expected_concepts or len(case.expected_concepts) == 0:
            errors.append(f"Case '{case.case_id}': expected_concepts must not be empty")
        else:
            for concept in case.expected_concepts:
                if not concept or not concept.strip():
                    errors.append(f"Case '{case.case_id}': contains blank expected concept")

        # Golden chunks verification
        if not case.golden_chunk_ids or len(case.golden_chunk_ids) == 0:
            errors.append(f"Case '{case.case_id}': must have at least one golden_chunk_id")
        else:
            for g_id in case.golden_chunk_ids:
                if g_id not in corpus_chunk_ids:
                    errors.append(
                        f"Case '{case.case_id}': golden chunk '{g_id}' does not exist in frozen corpus"
                    )

    is_valid = len(errors) == 0
    return is_valid, errors
