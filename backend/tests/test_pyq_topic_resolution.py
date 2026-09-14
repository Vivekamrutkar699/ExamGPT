import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from app.services.pyq_topic_resolution import QuestionNormalizer, TopicCandidate, TopicMatchPolicy


class TopicResolutionUnitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_threshold = settings.PYQ_TOPIC_MATCH_THRESHOLD
        self.original_margin = settings.PYQ_TOPIC_AMBIGUITY_MARGIN
        settings.PYQ_TOPIC_MATCH_THRESHOLD = 0.80
        settings.PYQ_TOPIC_AMBIGUITY_MARGIN = 0.05

    def tearDown(self) -> None:
        settings.PYQ_TOPIC_MATCH_THRESHOLD = self.original_threshold
        settings.PYQ_TOPIC_AMBIGUITY_MARGIN = self.original_margin

    def test_normalization_hashes_formatting_equivalents_identically(self) -> None:
        normalizer = QuestionNormalizer()
        left = normalizer.normalize("Q1. Explain Dynamic Linking. [10M]")
        right = normalizer.normalize(" explain dynamic linking ")
        self.assertEqual(left, right)
        self.assertEqual(normalizer.digest(left), normalizer.digest(right))

    def test_policy_accepts_clear_existing_topic(self) -> None:
        result = TopicMatchPolicy().decide([TopicCandidate("topic-a", 0.92), TopicCandidate("topic-b", 0.84)])
        self.assertEqual(result.resolution_type, "semantic_match")
        self.assertEqual(result.topic_id, "topic-a")

    def test_policy_keeps_close_candidates_unresolved(self) -> None:
        result = TopicMatchPolicy().decide([TopicCandidate("topic-a", 0.92), TopicCandidate("topic-b", 0.90)])
        self.assertEqual(result.resolution_type, "ambiguous")
        self.assertIsNone(result.topic_id)

    def test_policy_creates_new_topic_below_threshold(self) -> None:
        result = TopicMatchPolicy().decide([TopicCandidate("topic-a", 0.79)])
        self.assertEqual(result.resolution_type, "new_topic")


if __name__ == "__main__":
    unittest.main()
