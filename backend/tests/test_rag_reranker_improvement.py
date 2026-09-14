"""
Unit and regression tests for Phase 5C:
Reranker evaluation, keyword filtering, and ranking behavior.
"""

import unittest
from app.rag.reranker import reranker
from app.evals import (
    load_frozen_corpus,
    load_eval_dataset,
    EvalRetrievalAdapter,
    RetrievalEvalRunner,
)


class TestPhase5CReranker(unittest.TestCase):
    """Test reranker keyword extraction and ranking improvements."""

    def test_reranker_extract_keywords_filters_stopwords(self):
        query = "What are the main differences between TCP and UDP protocols?"
        keywords = reranker._extract_keywords(query)
        # Conversational template words should be filtered out
        self.assertNotIn("what", keywords)
        self.assertNotIn("are", keywords)
        self.assertNotIn("the", keywords)
        self.assertNotIn("main", keywords)
        self.assertNotIn("differences", keywords)
        self.assertNotIn("between", keywords)
        self.assertNotIn("and", keywords)
        # Genuine technical terms must remain
        self.assertIn("tcp", keywords)
        self.assertIn("udp", keywords)
        self.assertIn("protocols", keywords)

    def test_reranker_scoring_boost(self):
        # Verify that lexical overlap boost adds up to (overlap_ratio * 0.05)
        candidates = [
            {
                "chunk_id": "c1",
                "content": "TCP is connection-oriented while UDP is datagram protocols.",
                "rrf_score": 0.030,
            },
            {
                "chunk_id": "c2",
                "content": "Differences between subroutines and macros in assembly.",
                "rrf_score": 0.031,
            },
        ]
        query = "What are the main differences between TCP and UDP protocols?"
        reranked = reranker.rerank(query, candidates)

        # c1 has tcp, udp, protocols (3/3 = 1.0 overlap) -> score = 0.030 + 0.05 = 0.080
        # c2 has 0/3 technical words -> score = 0.031 + 0 = 0.031
        self.assertEqual(reranked[0]["chunk_id"], "c1")
        self.assertAlmostEqual(reranked[0]["score"], 0.080, places=3)
        self.assertEqual(reranked[1]["chunk_id"], "c2")
        self.assertAlmostEqual(reranked[1]["score"], 0.031, places=3)

    def test_reranker_maintains_perfect_recall_at_3_and_5(self):
        corpus = load_frozen_corpus()
        dataset = load_eval_dataset()
        adapter = EvalRetrievalAdapter(corpus, precompute_embeddings=True)
        runner = RetrievalEvalRunner()

        benchmark = runner.evaluate_multi_configurations(
            dataset=dataset,
            adapter=adapter,
            configurations=("hybrid_reranked",),
            limit=5,
        )

        rep = benchmark.configuration_reports["hybrid_reranked"]
        agg = rep.aggregate_metrics

        # Must achieve 1.0000 Recall@3 and 1.0000 Recall@5 on benchmark
        self.assertEqual(agg.mean_recall_at_3, 1.0000)
        self.assertEqual(agg.mean_recall_at_5, 1.0000)
        self.assertEqual(agg.zero_mrr_count, 0)
        self.assertTrue(agg.mean_mrr >= 0.9800)


if __name__ == "__main__":
    unittest.main()
