import uuid
import re
from typing import List, Dict, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chunk import Chunk
from app.models.document import Document
from app.rag.vector_store import vector_store_manager


class HybridSearcher:
    """
    Combines lexical sparse matching (keyword overlap) with dense vector searches,
    running Reciprocal Rank Fusion (RRF) to merge candidate lists.
    """

    def _extract_keywords(self, text: str) -> set[str]:
        """Convert a text block to a filtered set of lowercase words."""
        words = re.findall(r'\b\w{2,}\b', text.lower())
        stopwords = {
            "what", "is", "the", "and", "to", "in", "of", "for", "on", 
            "with", "as", "by", "an", "at", "from", "how", "why", "explain"
        }
        return set(w for w in words if w not in stopwords)

    async def sparse_search(
        self,
        db: AsyncSession,
        query: str,
        subject_id: uuid.UUID,
        category: Optional[str] = None,
        unit_tag: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict]:
        """
        Queries raw chunks from the database matching the subject scope,
        and scores their lexical overlap with the query.
        """
        query_words = self._extract_keywords(query)
        if not query_words:
            return []

        # Query chunk records linked to subject_id, applying optional filters
        stmt = (
            select(Chunk, Document.category)
            .join(Document, Chunk.document_id == Document.id)
            .where(Document.subject_id == subject_id)
        )
        
        if category:
            stmt = stmt.where(Document.category == category)
        if unit_tag:
            stmt = stmt.where(Chunk.unit_tag == unit_tag)

        result = await db.execute(stmt)
        records = result.all()
        
        scored_chunks = []
        for chunk, doc_category in records:
            chunk_words = self._extract_keywords(chunk.content)
            intersection = query_words.intersection(chunk_words)
            
            # Simple Jaccard/overlap metric
            overlap_score = len(intersection) / len(query_words)
            
            if overlap_score > 0:
                scored_chunks.append({
                    "chunk_id": str(chunk.id),
                    "content": chunk.content,
                    "unit_tag": chunk.unit_tag,
                    "category": doc_category,
                    "metadata": {
                        "page": chunk.metadata_json.get("page") if chunk.metadata_json else 1
                    },
                    "score": overlap_score
                })

        # Sort and limit
        scored_chunks.sort(key=lambda x: x["score"], reverse=True)
        return scored_chunks[:limit]

    async def search(
        self,
        db: AsyncSession,
        query: str,
        subject_id: uuid.UUID,
        limit: int = 5,
        category: Optional[str] = None,
        unit_tag: Optional[str] = None
    ) -> List[Dict]:
        """
        Merges dense search (Vector Store) and sparse search (DB Overlap)
        using Reciprocal Rank Fusion (RRF).
        """
        # 1. Execute vector search (dense)
        dense_results = vector_store_manager.search(
            query=query,
            subject_id=subject_id,
            limit=15,
            category=category,
            unit_tag=unit_tag
        )

        # 2. Execute database Jaccard search (sparse)
        sparse_results = await self.sparse_search(
            db=db,
            query=query,
            subject_id=subject_id,
            category=category,
            unit_tag=unit_tag,
            limit=15
        )

        # 3. Apply Reciprocal Rank Fusion (RRF)
        # RRF_score = sum( 1 / (60 + rank) )
        rrf_map: Dict[str, Dict] = {}
        
        # Helper to compute rank weights
        def rrf_merge(results: list, rank_key: str):
            for rank, item in enumerate(results):
                cid = item["chunk_id"]
                if cid not in rrf_map:
                    rrf_map[cid] = {
                        "chunk_id": item["chunk_id"],
                        "content": item["content"],
                        "unit_tag": item["unit_tag"],
                        "category": item["category"],
                        "metadata": item["metadata"],
                        "rrf_score": 0.0
                    }
                # RRF formula (default constant constant = 60)
                rrf_map[cid]["rrf_score"] += 1.0 / (60.0 + (rank + 1))

        rrf_merge(dense_results, "dense")
        rrf_merge(sparse_results, "sparse")

        # 4. Sort map values by RRF score descending
        merged_results = list(rrf_map.values())
        merged_results.sort(key=lambda x: x["rrf_score"], reverse=True)

        return merged_results[:limit]


# Singleton instance
hybrid_searcher = HybridSearcher()
