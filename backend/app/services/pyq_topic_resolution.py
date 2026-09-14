import hashlib
import re
import unicodedata
from dataclasses import dataclass
from typing import Protocol, Sequence

import numpy as np

from app.core.config import settings
from app.document_processing.chunking import get_embedding_model


class EmbeddingEncoder(Protocol):
    @property
    def model_version(self) -> str: ...

    def encode(self, texts: Sequence[str]) -> list[list[float]]: ...


class SentenceTransformerEmbeddingEncoder:
    @property
    def model_version(self) -> str:
        return settings.EMBEDDING_MODEL

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        vectors = get_embedding_model().encode(list(texts))
        return [np.asarray(vector, dtype=float).tolist() for vector in vectors]


class QuestionNormalizer:
    _marks = re.compile(r"[\(\[]\s*\d+\s*(?:m|marks?|mark)\s*[\)\]]", re.I)
    _prefix = re.compile(r"^\s*(?:q\s*\d+[\.:]?|\d+[\.:]?|[a-z]\))\s*", re.I)

    def normalize(self, text: str) -> str:
        value = unicodedata.normalize("NFKC", text).replace("\r\n", "\n")
        value = self._marks.sub("", value)
        value = self._prefix.sub("", value)
        value = re.sub(r"\s+", " ", value).strip().casefold()
        return value.rstrip(".?!;:").strip()

    def digest(self, normalized_text: str) -> str:
        return hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()

    def paper_digest(self, paper_text: str) -> str:
        return hashlib.sha256(unicodedata.normalize("NFKC", paper_text).replace("\r\n", "\n").strip().encode("utf-8")).hexdigest()


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    a, b = np.asarray(left, dtype=float), np.asarray(right, dtype=float)
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.dot(a, b) / denominator) if denominator else 0.0


@dataclass(frozen=True)
class TopicCandidate:
    topic_id: object
    score: float


@dataclass(frozen=True)
class MatchDecision:
    resolution_type: str
    topic_id: object | None
    best: TopicCandidate | None
    second: TopicCandidate | None


class TopicMatchPolicy:
    def decide(self, candidates: list[TopicCandidate]) -> MatchDecision:
        best = candidates[0] if candidates else None
        second = candidates[1] if len(candidates) > 1 else None
        threshold, margin = settings.PYQ_TOPIC_MATCH_THRESHOLD, settings.PYQ_TOPIC_AMBIGUITY_MARGIN
        if best is None:
            return MatchDecision("new_topic", None, None, None)
        if threshold is None or margin is None:
            return MatchDecision("unresolved_uncalibrated", None, best, second)
        if best.score < threshold:
            return MatchDecision("new_topic", None, best, second)
        if second and best.score - second.score < margin:
            return MatchDecision("ambiguous", None, best, second)
        return MatchDecision("semantic_match", best.topic_id, best, second)
