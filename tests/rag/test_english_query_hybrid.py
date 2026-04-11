import sys
import unittest
from pathlib import Path
from unittest.mock import patch

repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo_root / "english-v1-rag"))
sys.path.insert(1, str(repo_root / "scripts" / "rag"))

import query


class EnglishQueryHybridTests(unittest.TestCase):
    @patch.object(query.llm_module, "generate", return_value="answer")
    @patch("query.augment_context_with_sanskrit_gloss", return_value="glossed context")
    @patch("query.format_context", return_value="formatted context")
    def test_query_rag_uses_hybrid_search_for_retrieval(
        self,
        _mock_format_context,
        _mock_gloss,
        _mock_generate,
    ):
        with patch(
            "query.hybrid_search",
            return_value=([{"id": "e1", "translation": "verse"}], "english"),
            create=True,
        ) as mock_hybrid_search:
            result = query.query_rag("What is dharma?", config=query.get_english_config())

        self.assertEqual(result["answer"], "answer")
        self.assertEqual(result["sources"], [{"id": "e1", "translation": "verse"}])
        mock_hybrid_search.assert_called_once()

    def test_query_rag_returns_retrieval_mode_when_no_results(self):
        with patch(
            "query.hybrid_search",
            return_value=([], "english"),
            create=True,
        ):
            result = query.query_rag("What is dharma?", config=query.get_english_config())

        self.assertEqual(result["retrieval_mode"], "english")
        self.assertEqual(result["sources"], [])

    @patch.object(query.llm_module, "generate", return_value="answer")
    @patch("query.augment_context_with_sanskrit_gloss", return_value="glossed context")
    @patch("query.format_context", return_value="formatted context")
    def test_query_rag_preserves_transport_settings_for_full_corpus(
        self,
        _mock_format_context,
        _mock_gloss,
        _mock_generate,
    ):
        custom_config = query.get_english_config(
            qdrant_url="http://example.com:6333",
            qdrant_path=Path("/tmp/custom-qdrant"),
            ollama_base_url="http://ollama.internal:11434",
            temperature=0.77,
        )

        with patch(
            "query.hybrid_search",
            return_value=([{"id": "e1", "translation": "verse"}], "english"),
            create=True,
        ) as mock_hybrid_search:
            query.query_rag("What is dharma?", config=custom_config)

        full_config = mock_hybrid_search.call_args.kwargs["full_config"]
        self.assertEqual(full_config.qdrant_url, custom_config.qdrant_url)
        self.assertEqual(full_config.qdrant_path, custom_config.qdrant_path)
        self.assertEqual(full_config.ollama_base_url, custom_config.ollama_base_url)
        self.assertEqual(full_config.temperature, custom_config.temperature)
        self.assertEqual(full_config.qdrant_collection, "hindu_scriptures")
