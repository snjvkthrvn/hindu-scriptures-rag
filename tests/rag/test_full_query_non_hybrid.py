import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo_root / "scripts" / "rag"))

_query_path = repo_root / "scripts" / "rag" / "query.py"
_spec = importlib.util.spec_from_file_location("full_query_module", _query_path)
full_query = importlib.util.module_from_spec(_spec)
assert _spec is not None and _spec.loader is not None
_spec.loader.exec_module(full_query)


class FullQueryDirectSearchTests(unittest.TestCase):
    @patch.object(full_query.llm_module, "generate", return_value="answer")
    @patch.object(full_query, "augment_context_with_sanskrit_gloss", return_value="glossed context")
    @patch.object(full_query, "format_context", return_value="formatted context")
    @patch.object(full_query, "search", return_value=[{"id": "f1", "translation": "verse"}])
    def test_query_rag_uses_direct_search_for_full_corpus(
        self,
        mock_search,
        _mock_format_context,
        _mock_gloss,
        _mock_generate,
    ):
        result = full_query.query_rag("What is dharma?", config=full_query.RAGConfig())

        self.assertEqual(result["answer"], "answer")
        self.assertEqual(result["sources"], [{"id": "f1", "translation": "verse"}])
        self.assertNotIn("retrieval_mode", result)
        mock_search.assert_called_once()
