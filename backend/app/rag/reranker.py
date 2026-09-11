from typing import List, Dict


class Reranker:
    """
    Reranks candidate retrieved chunks by combining Reciprocal Rank Fusion (RRF) scores
    with a lexical term proximity and overlap boost.
    """

    def rerank(self, query: str, results: List[Dict]) -> List[Dict]:
        """
        Adjust scores based on query word occurrence density in chunk text content,
        and sort matching entities.
        """
        query_words = [w.lower() for w in query.split() if len(w) > 2]
        if not query_words or not results:
            return results

        for item in results:
            content_lower = item["content"].lower()
            
            # Count occurrences of query words
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
