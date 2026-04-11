import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "rag"))

from hybrid_router import RetrievalMode
from hybrid_query import dedupe_results, fuse_ranked_results, hybrid_search


class HybridQueryTests(unittest.TestCase):
    def test_duplicate_verse_prefers_richer_result(self):
        english = [
            {
                "id": "e1",
                "verse_id": "bg_2_47",
                "chunk_type": "verse",
                "author": "",
                "translation": "A",
                "sanskrit": "",
            }
        ]
        full = [
            {
                "id": "f1",
                "verse_id": "bg_2_47",
                "chunk_type": "verse",
                "author": "",
                "translation": "A",
                "sanskrit": "कर्मण्येवाधिकारस्ते",
            }
        ]
        merged = dedupe_results(english + full)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["sanskrit"], "कर्मण्येवाधिकारस्ते")

    def test_missing_ids_do_not_collapse_distinct_results(self):
        english = [
            {
                "chunk_type": "verse",
                "author": "",
                "source_text": "Bhagavad Gita",
                "translation": "Act without attachment.",
            }
        ]
        full = [
            {
                "chunk_type": "verse",
                "author": "",
                "source_text": "Mahabharata",
                "translation": "Steady wisdom arises from discipline.",
            }
        ]

        merged = dedupe_results(english + full)

        self.assertEqual(len(merged), 2)

    def test_rrf_caps_to_requested_top_k(self):
        english = [
            {"id": f"e{i}", "verse_id": f"e{i}", "chunk_type": "verse", "author": ""}
            for i in range(8)
        ]
        full = [
            {"id": f"f{i}", "verse_id": f"f{i}", "chunk_type": "verse", "author": ""}
            for i in range(8)
        ]
        merged = fuse_ranked_results(english, full, top_k=8)
        self.assertLessEqual(len(merged), 8)

    @patch("hybrid_query.search")
    @patch("hybrid_query.should_escalate", return_value=False)
    @patch("hybrid_query.route_question", return_value=RetrievalMode.ENGLISH)
    def test_hybrid_search_returns_english_results_without_escalation(
        self,
        _mock_route,
        _mock_escalate,
        mock_search,
    ):
        mock_search.return_value = [{"id": "e1", "verse_id": "bg_2_47", "chunk_type": "verse"}]

        english_config = SimpleNamespace(top_k=8)
        full_config = SimpleNamespace(top_k=8)

        results, mode = hybrid_search(
            "What is dharma?",
            english_config=english_config,
            full_config=full_config,
        )

        self.assertEqual(mode, RetrievalMode.ENGLISH.value)
        self.assertEqual(results, mock_search.return_value)

    @patch("hybrid_query.search")
    @patch("hybrid_query.route_question", return_value=RetrievalMode.BOTH)
    def test_hybrid_search_falls_back_when_one_corpus_errors(self, _mock_route, mock_search):
        english_results = [{"id": "e1", "verse_id": "bg_2_47", "chunk_type": "verse", "author": ""}]
        mock_search.side_effect = [english_results, RuntimeError("full search failed")]

        english_config = SimpleNamespace(top_k=8)
        full_config = SimpleNamespace(top_k=8)

        results, mode = hybrid_search(
            "What is dharma?",
            english_config=english_config,
            full_config=full_config,
        )

        self.assertEqual(mode, RetrievalMode.ENGLISH.value)
        self.assertEqual(results, english_results)

    @patch("hybrid_query.search")
    @patch("hybrid_query.route_question", return_value=RetrievalMode.ENGLISH)
    def test_hybrid_search_falls_back_when_primary_english_search_errors(
        self,
        _mock_route,
        mock_search,
    ):
        full_results = [{"id": "f1", "verse_id": "bg_2_48", "chunk_type": "verse", "author": ""}]
        mock_search.side_effect = [RuntimeError("english search failed"), full_results]

        english_config = SimpleNamespace(top_k=8)
        full_config = SimpleNamespace(top_k=8)

        results, mode = hybrid_search(
            "What is dharma?",
            english_config=english_config,
            full_config=full_config,
        )

        self.assertEqual(mode, RetrievalMode.FULL.value)
        self.assertEqual(results, full_results)

    @patch("hybrid_query.search")
    @patch("hybrid_query.should_escalate", return_value=True)
    @patch("hybrid_query.route_question", return_value=RetrievalMode.ENGLISH)
    def test_hybrid_search_reuses_first_pass_results_on_escalation(
        self,
        _mock_route,
        _mock_escalate,
        mock_search,
    ):
        english_results = [{"id": "e1", "verse_id": "bg_2_47", "chunk_type": "verse", "author": ""}]
        full_results = [{"id": "f1", "verse_id": "bg_2_48", "chunk_type": "verse", "author": ""}]
        mock_search.side_effect = [english_results, full_results]

        english_config = SimpleNamespace(top_k=8)
        full_config = SimpleNamespace(top_k=8)

        results, mode = hybrid_search(
            "What is dharma?",
            english_config=english_config,
            full_config=full_config,
        )

        self.assertEqual(mode, RetrievalMode.BOTH.value)
        self.assertEqual(mock_search.call_count, 2)
        self.assertLessEqual(len(results), 8)

    @patch("hybrid_query.search")
    @patch("hybrid_query.should_escalate", return_value=True)
    @patch("hybrid_query.route_question", return_value=RetrievalMode.ENGLISH)
    def test_hybrid_search_drops_source_text_filter_on_secondary_corpus(
        self,
        _mock_route,
        _mock_escalate,
        mock_search,
    ):
        english_results = [{"id": "e1", "verse_id": "ys_1_2", "chunk_type": "verse", "author": ""}]
        full_results = [{"id": "f1", "verse_id": "bg_2_47", "chunk_type": "verse", "author": ""}]
        mock_search.side_effect = [english_results, full_results]

        english_config = SimpleNamespace(top_k=8)
        full_config = SimpleNamespace(top_k=8)

        hybrid_search(
            "Explain Yoga Sutra 1.2",
            english_config=english_config,
            full_config=full_config,
            filter_dict={
                "source_text": "Yoga Sutras of Patanjali",
                "category": "sutra",
                "tradition": "yoga",
                "chunk_type": "verse",
            },
        )

        self.assertEqual(
            mock_search.call_args_list[0].kwargs["filters"],
            {
                "source_text": "Yoga Sutras of Patanjali",
                "category": "sutra",
                "tradition": "yoga",
                "chunk_type": "verse",
            },
        )
        self.assertEqual(
            mock_search.call_args_list[1].kwargs["filters"],
            {"chunk_type": "verse"},
        )
