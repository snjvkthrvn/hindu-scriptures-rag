import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "rag"))

from config import RAGConfig
from search import _rank_chunk_results, search


def _point(point_id: str, score: float, **payload):
    return SimpleNamespace(payload={"_point_id": point_id, **payload}, score=score, id=point_id)


class SearchRankingTests(unittest.TestCase):
    def test_base_verse_precedes_commentary_for_same_verse_id(self):
        results = [
            {"id": "bg_2_47_comm_16", "verse_id": "bg_2_47", "chunk_type": "commentary"},
            {"id": "bg_18_66", "verse_id": "bg_18_66", "chunk_type": "verse"},
            {"id": "bg_2_47", "verse_id": "bg_2_47", "chunk_type": "verse"},
        ]

        ranked = _rank_chunk_results(results, top_k=3)

        self.assertEqual(
            [result["id"] for result in ranked],
            ["bg_2_47", "bg_18_66", "bg_2_47_comm_16"],
        )

    def test_search_fetches_wider_candidates_and_caps_to_top_k(self):
        fake_embedder = SimpleNamespace(embed_query=lambda query: [0.1], batch_size=50)
        fake_store = SimpleNamespace()
        fake_store.search_hybrid = lambda **kwargs: [
            _point(
                "bg_2_47_comm_16",
                0.8,
                verse_id="bg_2_47",
                chunk_type="commentary",
                source_text="Bhagavad Gita",
                chapter=2,
                verse_num=47,
                commentary_text="commentary",
            ),
            _point(
                "bg_18_66",
                0.7,
                verse_id="bg_18_66",
                chunk_type="verse",
                source_text="Bhagavad Gita",
                chapter=18,
                verse_num=66,
                sanskrit="सर्वधर्मान्",
            ),
            _point(
                "bg_2_47",
                0.6,
                verse_id="bg_2_47",
                chunk_type="verse",
                source_text="Bhagavad Gita",
                chapter=2,
                verse_num=47,
                sanskrit="कर्मण्येवाधिकारस्ते",
            ),
        ]

        with (
            patch("search._get_embedder", return_value=fake_embedder),
            patch("search._get_store", return_value=fake_store),
        ):
            results = search("karmany evadhikaras te", config=RAGConfig(), top_k=3)

        self.assertEqual(
            [result["id"] for result in results],
            ["bg_2_47", "bg_18_66", "bg_2_47_comm_16"],
        )


if __name__ == "__main__":
    unittest.main()
