import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "rag"))

from hybrid_router import RetrievalMode, route_question, should_escalate


class HybridRouterTests(unittest.TestCase):
    def test_plain_english_defaults_to_english(self):
        self.assertEqual(
            route_question("What does the Gita say about anxiety?"),
            RetrievalMode.ENGLISH,
        )

    def test_story_substring_does_not_force_full_route(self):
        self.assertEqual(route_question("What is Arjuna's backstory?"), RetrievalMode.ENGLISH)

    def test_plural_keyword_routes_to_full(self):
        self.assertEqual(route_question("What do the schools say about dharma?"), RetrievalMode.FULL)

    def test_verse_ref_routes_to_full(self):
        self.assertEqual(route_question("Explain BG 2.47"), RetrievalMode.FULL)

    def test_compact_verse_ref_routes_to_full(self):
        self.assertEqual(route_question("Explain BG2.47"), RetrievalMode.FULL)

    def test_named_gita_ref_routes_to_full(self):
        self.assertEqual(route_question("Explain Bhagavad Gita 2.47"), RetrievalMode.FULL)

    def test_mixed_ys_and_gita_refs_route_to_full(self):
        self.assertEqual(route_question("Compare YS 1.2 and BG 2.47"), RetrievalMode.FULL)

    def test_yoga_sutra_ref_stays_english(self):
        self.assertEqual(route_question("Explain YS 1.2"), RetrievalMode.ENGLISH)

    def test_compact_yoga_sutra_ref_stays_english(self):
        self.assertEqual(route_question("Explain YS1.2"), RetrievalMode.ENGLISH)

    def test_devanagari_routes_to_full(self):
        self.assertEqual(route_question("कर्मण्येवाधिकारस्ते"), RetrievalMode.FULL)

    def test_weak_results_escalate(self):
        weak_results = [{"source_text": "Bhagavad Gita"}]
        self.assertTrue(
            should_escalate(
                question="What is dharma?",
                mode=RetrievalMode.ENGLISH,
                results=weak_results,
                top_k=8,
            )
        )

    def test_full_mode_strong_results_do_not_escalate_on_compare_keyword(self):
        strong_results = [
            {"source_text": "Bhagavad Gita"},
            {"source_text": "Mahabharata"},
            {"source_text": "Yoga Sutras of Patanjali"},
        ]
        self.assertFalse(
            should_escalate(
                question="Compare BG 2.47 and BG 2.48",
                mode=RetrievalMode.FULL,
                results=strong_results,
                top_k=8,
            )
        )
