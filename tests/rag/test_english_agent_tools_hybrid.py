import sys
import unittest
from pathlib import Path
from unittest.mock import patch

repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo_root / "english-v1-rag"))
sys.path.insert(1, str(repo_root / "scripts" / "rag"))

from agent.tools import _exec_get_verse, _exec_search_commentaries, _exec_search_scriptures
from english_config import get_english_config


class EnglishAgentHybridToolTests(unittest.TestCase):
    @patch("agent.tools.format_context", return_value="formatted scriptures")
    @patch(
        "agent.tools.hybrid_search",
        return_value=([{"id": "e1", "translation": "test"}], "english"),
        create=True,
    )
    def test_search_scriptures_uses_hybrid_search(
        self,
        mock_hybrid_search,
        mock_format_context,
    ):
        with patch(
            "agent.tools.search",
            side_effect=AssertionError("direct search should not be called"),
            create=True,
        ):
            result = _exec_search_scriptures({"query": "What is dharma?"}, config=get_english_config())

        self.assertEqual(result, "formatted scriptures")
        mock_hybrid_search.assert_called_once()
        mock_format_context.assert_called_once()

    @patch("agent.tools.format_context", return_value="formatted commentaries")
    @patch(
        "agent.tools.hybrid_search",
        return_value=([{"id": "c1", "commentary_text": "commentary"}], "both"),
        create=True,
    )
    def test_search_commentaries_uses_hybrid_search(
        self,
        mock_hybrid_search,
        mock_format_context,
    ):
        with patch(
            "agent.tools.search",
            side_effect=AssertionError("direct search should not be called"),
            create=True,
        ):
            result = _exec_search_commentaries({"query": "Advaita on duty"}, config=get_english_config())

        self.assertEqual(result, "formatted commentaries")
        mock_hybrid_search.assert_called_once()
        mock_format_context.assert_called_once()

    @patch("agent.tools.format_context", return_value="formatted scriptures")
    @patch(
        "agent.tools.hybrid_search",
        return_value=([{"id": "e1", "translation": "test"}], "english"),
        create=True,
    )
    def test_search_scriptures_preserves_transport_settings_for_full_corpus(
        self,
        mock_hybrid_search,
        _mock_format_context,
    ):
        custom_config = get_english_config(
            qdrant_url="http://example.com:6333",
            qdrant_path=Path("/tmp/custom-qdrant"),
        )

        _exec_search_scriptures({"query": "What is dharma?"}, config=custom_config)

        full_config = mock_hybrid_search.call_args.kwargs["full_config"]
        self.assertEqual(full_config.qdrant_url, custom_config.qdrant_url)
        self.assertEqual(full_config.qdrant_path, custom_config.qdrant_path)
        self.assertEqual(full_config.qdrant_collection, "hindu_scriptures")

    @patch("agent.tools.format_context", return_value="formatted verse")
    @patch("agent.tools.search_by_verse_id", return_value=[{"id": "bg_2_47"}])
    def test_get_verse_stays_precise(self, mock_search_by_verse_id, mock_format_context):
        result = _exec_get_verse({"verse_ref": "BG 2.47"}, config=get_english_config())

        self.assertEqual(result, "formatted verse")
        mock_search_by_verse_id.assert_called_once()
        mock_format_context.assert_called_once()
