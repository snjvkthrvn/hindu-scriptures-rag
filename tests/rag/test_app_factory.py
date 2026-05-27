import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from flask import Flask

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "rag"))

auth_backend_stub = types.ModuleType("auth_backend")
auth_backend_stub.register_auth = lambda app: None
sys.modules.setdefault("auth_backend", auth_backend_stub)

from app_factory import (
    _rag_warmup_enabled,
    _register_dual_warmup,
    _register_rag_routes,
    create_dual_app,
)
from config import RAGConfig


class _ImmediateThread:
    def __init__(self, target=None, daemon=None):
        self._target = target
        self.daemon = daemon

    def start(self):
        if self._target is not None:
            self._target()


class AppFactoryTests(unittest.TestCase):
    def test_register_routes_uses_injected_query_function(self):
        app = Flask(__name__)
        query_func = Mock(return_value={"answer": "ok", "sources": [], "retrieval_mode": "english"})
        run_agent_func = Mock(return_value={"answer": "agent"})
        run_agent_stream_func = Mock(return_value=iter(()))

        _register_rag_routes(
            app,
            RAGConfig(),
            {"sources": [], "categories": [], "traditions": [], "total_verses": 0},
            query_func=query_func,
            run_agent_func=run_agent_func,
            run_agent_stream_func=run_agent_stream_func,
        )

        response = app.test_client().post("/api/query", json={"question": "What is dharma?"})

        self.assertEqual(response.status_code, 200)
        query_func.assert_called_once()
        self.assertEqual(response.get_json()["retrieval_mode"], "english")

    def test_register_routes_uses_default_query_import_when_not_injected(self):
        app = Flask(__name__)
        query_stub = types.ModuleType("query")
        query_stub.query_rag = Mock(return_value={"answer": "default", "sources": []})

        with patch.dict(sys.modules, {"query": query_stub}):
            _register_rag_routes(
                app,
                RAGConfig(),
                {"sources": [], "categories": [], "traditions": [], "total_verses": 0},
            )

            response = app.test_client().post("/api/query", json={"question": "What is dharma?"})

        self.assertEqual(response.status_code, 200)
        query_stub.query_rag.assert_called_once()

    @patch("app_factory.threading.Thread", _ImmediateThread)
    @patch("app_factory._call_warmup")
    def test_register_dual_warmup_warms_both_corpora(self, mock_call_warmup):
        english_config = RAGConfig(qdrant_collection="hindu_scriptures_english")
        full_config = RAGConfig()

        with patch.dict(os.environ, {"RAG_WARMUP": "1"}, clear=False):
            _register_dual_warmup(Flask(__name__), english_config, full_config)

        self.assertEqual(mock_call_warmup.call_count, 2)
        mock_call_warmup.assert_any_call(english_config)
        mock_call_warmup.assert_any_call(full_config)

    def test_warmup_defaults_off_on_vercel_unless_explicit(self):
        with patch.dict(os.environ, {"VERCEL": "1"}, clear=True):
            self.assertFalse(_rag_warmup_enabled())

        with patch.dict(os.environ, {"VERCEL": "1", "RAG_WARMUP": "1"}, clear=True):
            self.assertTrue(_rag_warmup_enabled())

    @patch("app_factory._register_dual_warmup")
    @patch("app_factory._load_module", create=True)
    @patch("app_factory._load_module_attr")
    def test_create_dual_app_registers_dual_warmup(
        self,
        mock_load_module_attr,
        mock_load_module,
        mock_register_dual_warmup,
    ):
        mock_load_module_attr.side_effect = [
            Mock(return_value={"answer": "full", "sources": []}),
        ]
        mock_load_module.return_value = types.SimpleNamespace(
            run_agent=Mock(return_value={"answer": "agent"}),
            run_agent_stream=Mock(return_value=iter(())),
        )

        english_config = RAGConfig(qdrant_collection="hindu_scriptures_english")
        filters = {"sources": [], "categories": [], "traditions": [], "total_verses": 0}

        app = create_dual_app(english_config, filters)

        args, _kwargs = mock_register_dual_warmup.call_args
        self.assertIs(args[0], app)
        self.assertIs(args[1], english_config)
        self.assertIsInstance(args[2], RAGConfig)
        self.assertEqual(args[2].qdrant_collection, "hindu_scriptures")
        mock_load_module.assert_called_once()
