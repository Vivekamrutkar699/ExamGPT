import re
from typing import List, Dict, Set


class Reranker:
    """
    Reranks candidate retrieved chunks by combining Reciprocal Rank Fusion (RRF) scores
    with a lexical term proximity and overlap boost.
    """

    # Stopwords consistent with lexical sparse retrieval and conversational query phrasing
    STOPWORDS: Set[str] = {
        "what", "is", "the", "and", "to", "in", "of", "for", "on",
        "with", "as", "by", "an", "at", "from", "how", "why", "explain",
        "are", "between", "difference", "differences", "main", "compare",
    }

    def _extract_keywords(self, text: str) -> Set[str]:
        """Convert a text block to a filtered set of lowercase content words."""
        words = re.findall(r'\b\w{2,}\b', text.lower())
        return set(w for w in words if w not in self.STOPWORDS)

    def rerank(self, query: str, results: List[Dict]) -> List[Dict]:
        """
        Adjust scores based on query keyword occurrence density in chunk text content,
        and sort matching entities.
        """
        query_words = self._extract_keywords(query)
        if not query_words or not results:
            return results

        for item in results:
            content_lower = item["content"].lower()
            
            # Count occurrences of distinctive query words
            matches = sum(1 for word in query_words if word in content_lower)
            
            # Compute lexical density overlap ratio
            overlap_ratio = matches / len(query_words)
            
            # Apply a normalized boost to the base RRF score
            base_rrf = item.get("rrf_score", 0.0)
            item["score"] = base_rrf + (overlap_ratio * 0.05)

        # Re-sort lists by updated score descending
        results.sort(key=lambda x: x["score"], reverse=True)
        return results


# Singleton instance
reranker = Reranker()
