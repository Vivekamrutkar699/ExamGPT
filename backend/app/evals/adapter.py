"""
Deterministic RAG retrieval adapter for ExamGPT Phase 5B evaluation harness.

Connects the actual retrieval pipeline implementations to the frozen evaluation corpus
without altering production RAG pipelines or modifying the mutable SQLite database.

Supports 4 configurations:
- Configuration A: Dense retrieval (SentenceTransformer cosine similarity)
- Configuration B: Lexical retrieval (exact Jaccard/keyword overlap from HybridSearcher)
- Configuration C: Hybrid/RRF (Reciprocal Rank Fusion 1 / (60 + rank))
- Configuration D: Hybrid + existing reranker (Reranker lexical density boost)
"""

import re
import numpy as np
from typing import List, Dict, Optional, Any, Sequence

from app.evals.schemas import FrozenCorpus, FrozenCorpusChunk
from app.document_processing.chunking import get_embedding_model
from app.rag.query_processor import query_processor
from app.rag.reranker import reranker


class EvalRetrievalAdapter:
    """
    Adapter that indexes the frozen evaluation corpus and executes the exact
    retrieval algorithms of the production RAG pipeline:
    - Dense vector search (cosine similarity on all-MiniLM-L6-v2 embeddings)
    - Sparse lexical search (keyword overlap using HybridSearcher._extract_keywords)
    - Hybrid Reciprocal Rank Fusion (RRF with constant 60)
    - Reranker (lexical density proximity boost)
    """

    def __init__(self, corpus: FrozenCorpus, precompute_embeddings: bool = True):
        self.corpus = corpus
        self.chunks: List[FrozenCorpusChunk] = corpus.chunks
        self.chunk_map: Dict[str, FrozenCorpusChunk] = {c.chunk_id: c for c in self.chunks}

        # Stopwords set identical to HybridSearcher._extract_keywords
        self.stopwords = {
            "what", "is", "the", "and", "to", "in", "of", "for", "on",
            "with", "as", "by", "an", "at", "from", "how", "why", "explain"
        }

        # Precompute chunk embeddings for dense search
        self.chunk_embeddings: Optional[np.ndarray] = None
        if precompute_embeddings:
            self._precompute_embeddings()

    def _precompute_embeddings(self) -> None:
        """Compute and cache normalized embeddings for all chunks in the frozen corpus."""
        if not self.chunks:
            self.chunk_embeddings = np.zeros((0, 384), dtype=np.float32)
            return

        model = get_embedding_model()
        texts = [c.content for c in self.chunks]
        embeddings = model.encode(texts, convert_to_numpy=True)
        # Normalize for fast cosine dot product
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self.chunk_embeddings = (embeddings / norms).astype(np.float32)

    def _extract_keywords(self, text: str) -> set[str]:
        """
        Exact keyword extraction logic from app.rag.hybrid_search.HybridSearcher._extract_keywords.
        """
        words = re.findall(r'\b\w{2,}\b', text.lower())
        return set(w for w in words if w not in self.stopwords)

    def dense_retrieval(
        self,
        query: str,
        limit: int = 15,
        subject: Optional[str] = None,
        unit: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Configuration A: Dense vector search.
        Encodes query using SentenceTransformer, computes cosine similarity against
        corpus chunk embeddings, and ranks candidates descending.
        """
        if not self.chunks or self.chunk_embeddings is None:
            return []

        model = get_embedding_model()
        query_emb = model.encode(query, convert_to_numpy=True)
        norm_q = np.linalg.norm(query_emb)
        if norm_q > 0:
            query_emb = query_emb / norm_q
        else:
            return []

        # Cosine similarity dot product with normalized embeddings
        sims = np.dot(self.chunk_embeddings, query_emb)

        results = []
        for idx, (chunk, sim) in enumerate(zip(self.chunks, sims)):
            # Optional metadata filter
            if subject and chunk.subject.lower() != subject.lower():
                continue
            if unit and chunk.unit.lower() != unit.lower():
                continue

            results.append({
                "chunk_id": chunk.chunk_id,
                "content": chunk.content,
                "unit_tag": chunk.unit,
                "subject": chunk.subject,
                "category": "notes",
                "metadata": {
                    "document_name": chunk.document_name,
                    "page": chunk.page,
                },
                "score": float(sim),
            })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    def lexical_retrieval(
        self,
        query: str,
        limit: int = 15,
        subject: Optional[str] = None,
        unit: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Configuration B: Lexical sparse search.
        Executes exact Jaccard/keyword overlap calculation from HybridSearcher.sparse_search.
        """
        query_words = self._extract_keywords(query)
        if not query_words:
            return []

        results = []
        for chunk in self.chunks:
            if subject and chunk.subject.lower() != subject.lower():
                continue
            if unit and chunk.unit.lower() != unit.lower():
                continue

            chunk_words = self._extract_keywords(chunk.content)
            intersection = query_words.intersection(chunk_words)
            overlap_score = len(intersection) / len(query_words)

            if overlap_score > 0:
                results.append({
                    "chunk_id": chunk.chunk_id,
                    "content": chunk.content,
                    "unit_tag": chunk.unit,
                    "subject": chunk.subject,
                    "category": "notes",
                    "metadata": {
                        "document_name": chunk.document_name,
                        "page": chunk.page,
                    },
                    "score": float(overlap_score),
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    def hybrid_rrf_retrieval(
        self,
        query: str,
        limit: int = 15,
        subject: Optional[str] = None,
        unit: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Configuration C: Hybrid search with Reciprocal Rank Fusion (RRF).
        Merges dense and sparse candidate lists using exact RRF formula:
        sum( 1.0 / (60.0 + rank + 1) ).
        """
        dense_results = self.dense_retrieval(query, limit=15, subject=subject, unit=unit)
        sparse_results = self.lexical_retrieval(query, limit=15, subject=subject, unit=unit)

        rrf_map: Dict[str, Dict[str, Any]] = {}

        def rrf_merge(results_list: list):
            for rank, item in enumerate(results_list):
                cid = item["chunk_id"]
                if cid not in rrf_map:
                    rrf_map[cid] = {
                        "chunk_id": item["chunk_id"],
                        "content": item["content"],
                        "unit_tag": item["unit_tag"],
                        "subject": item.get("subject"),
                        "category": item.get("category"),
                        "metadata": item.get("metadata", {}),
                        "rrf_score": 0.0,
                    }
                # RRF formula (constant = 60)
                rrf_map[cid]["rrf_score"] += 1.0 / (60.0 + (rank + 1))

        rrf_merge(dense_results)
        rrf_merge(sparse_results)

        merged_results = list(rrf_map.values())
        merged_results.sort(key=lambda x: x["rrf_score"], reverse=True)
        return merged_results[:limit]

    def hybrid_reranked_retrieval(
        self,
        query: str,
        expanded_query: Optional[str] = None,
        limit: int = 15,
        subject: Optional[str] = None,
        unit: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Configuration D: Hybrid + existing reranker.
        Runs hybrid RRF retrieval, then applies reranker.rerank(...) lexical density boost.
        Matches the exact sequence in RAGEngine.get_grounded_answer.
        """
        search_query = expanded_query or query
        rrf_results = self.hybrid_rrf_retrieval(search_query, limit=limit, subject=subject, unit=unit)

        # Apply production reranker
        reranked = reranker.rerank(search_query, rrf_results)
        return reranked[:limit]

    def retrieve(
        self,
        configuration: str,
        query: str,
        use_query_expansion: bool = True,
        limit: int = 15,
        subject: Optional[str] = None,
        unit: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Execute retrieval under specified configuration name:
        - 'dense': Configuration A
        - 'lexical': Configuration B
        - 'hybrid': Configuration C
        - 'hybrid_reranked': Configuration D
        """
        search_query = query_processor.rewrite_query(query) if use_query_expansion else query

        config_key = configuration.lower().strip()
        if config_key in ("dense", "a"):
            return self.dense_retrieval(search_query, limit=limit, subject=subject, unit=unit)
        elif config_key in ("lexical", "sparse", "b"):
            return self.lexical_retrieval(search_query, limit=limit, subject=subject, unit=unit)
        elif config_key in ("hybrid", "hybrid_rrf", "rrf", "c"):
            return self.hybrid_rrf_retrieval(search_query, limit=limit, subject=subject, unit=unit)
        elif config_key in ("hybrid_reranked", "reranked", "d"):
            return self.hybrid_reranked_retrieval(
                query=query,
                expanded_query=search_query,
                limit=limit,
                subject=subject,
                unit=unit,
            )
        else:
            raise ValueError(
                f"Unknown retrieval configuration '{configuration}'. "
                f"Expected one of: 'dense', 'lexical', 'hybrid', 'hybrid_reranked'."
            )
