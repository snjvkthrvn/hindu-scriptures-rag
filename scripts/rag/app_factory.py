"""Shared Flask application factory for the RAG web UI.

- ``create_full_app``: full corpus only at ``/`` (replaces standalone ``scripts/rag/app.py``).
- ``create_dual_app``: full multilingual corpus at ``/``, English beta at ``/beta`` (production / Railway).
"""

from __future__ import annotations

import importlib.util
import json
import os
import secrets
import sys
import threading
from dataclasses import replace
from pathlib import Path
from types import ModuleType

import secrets as secrets_mod

from auth_backend import register_auth
from config import PROJECT_ROOT, RAGConfig
from api_security import (
    UserInputError,
    build_json_error,
    get_required_api_key,
    get_session_password,
    is_browser_key_exposure_enabled,
    load_history_into_memory,
    auth_allows_request,
    validate_and_prepare_question,
)
from flask import Blueprint, Flask, Response, current_app, jsonify, render_template, request, session, stream_with_context
from voices import VOICES
from werkzeug.middleware.proxy_fix import ProxyFix


def _build_sources_response(result):
    sources = []
    total_sources = max(len(result.get("sources", [])), 1)
    for i, src in enumerate(result.get("sources", [])):
        header = src.get("source_text", "")
        if src.get("chapter_name"):
            header += f" - {src['chapter_name']}"
        if src.get("verse_num"):
            header += f", Verse {src['verse_num']}"
        similarity = round((1 - (i / total_sources)) * 100, 1)
        sources.append(
            {
                "header": header,
                "sanskrit": src.get("sanskrit", ""),
                "transliteration": src.get("transliteration", ""),
                "translation": src.get("translation", ""),
                "commentary_text": src.get("commentary_text", ""),
                "author": src.get("author", ""),
                "chunk_type": src.get("chunk_type", "verse"),
                "metadata": {
                    "source_text": src.get("source_text", ""),
                    "category": src.get("category", ""),
                    "tradition": src.get("tradition", ""),
                    "chapter": src.get("chapter", 0),
                    "verse": src.get("verse_num", 0),
                },
                "similarity": similarity,
            }
        )
    return sources


def _call_warmup(config: RAGConfig) -> None:
    from search import warmup

    warmup(config)


def _env_truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in ("1", "true", "yes", "on")


def _rag_warmup_enabled() -> bool:
    raw = os.environ.get("RAG_WARMUP")
    if raw is not None:
        return _env_truthy(raw)
    return not os.environ.get("VERCEL")


def _load_module(module_name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module {module_name} from {path}")

    module = importlib.util.module_from_spec(spec)
    preferred_dir = str(path.parent.parent if path.parent.name == "agent" else path.parent)
    original_sys_path = list(sys.path)
    sys.path = [preferred_dir] + [entry for entry in sys.path if entry != preferred_dir]
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path = original_sys_path
    return module


def _load_module_attr(module_name: str, path: Path, attr_name: str):
    module = _load_module(module_name, path)
    return getattr(module, attr_name)


def _register_rag_routes(
    bp_or_app,
    base_config,
    filter_options,
    *,
    query_func=None,
    run_agent_func=None,
    run_agent_stream_func=None,
):
    """Register /api/sources, /api/query, /api/agent, /api/agent/stream, /api/voices."""

    if query_func is None:
        from query import query_rag as query_func

    if run_agent_func is None:
        from agent.react_loop import run_agent as run_agent_func

    if run_agent_stream_func is None:
        from agent.react_loop import run_agent_stream as run_agent_stream_func

    @bp_or_app.route("/api/health")
    def api_health():
        return jsonify({"ok": True})

    @bp_or_app.route("/api/auth/config", methods=["GET"])
    def api_rag_auth_config():
        k = get_required_api_key()
        return jsonify(
            {
                "api_key_configured": bool(k),
                "password_login_configured": bool(get_session_password()),
                "expose_key_to_ui": bool(is_browser_key_exposure_enabled() and k),
            }
        )

    @bp_or_app.route("/api/login", methods=["POST"])
    def api_rag_password_login():
        expected = get_session_password()
        if not expected:
            return jsonify({"error": "Session password login is not enabled"}), 400
        data = request.get_json(silent=True) or {}
        got = data.get("password") or ""
        if len(got) != len(expected):
            return jsonify({"error": "Invalid credentials"}), 401
        if not secrets_mod.compare_digest(got, expected):
            return jsonify({"error": "Invalid credentials"}), 401
        session["rag_ok"] = True
        return jsonify({"ok": True})

    @bp_or_app.route("/api/logout", methods=["POST"])
    def api_rag_logout():
        session.pop("rag_ok", None)
        return jsonify({"ok": True})

    @bp_or_app.route("/api/sources")
    def api_sources():
        return jsonify(filter_options)

    @bp_or_app.route("/api/query", methods=["POST"])
    def api_query():
        data = request.get_json(silent=True) or {}
        question = (data.get("question") or "").strip()
        if not question:
            return jsonify({"error": "No question provided"}), 400

        top_k = data.get("top_k", base_config.top_k)
        try:
            top_k = max(1, min(int(top_k), 20))
        except (ValueError, TypeError):
            top_k = base_config.top_k

        config = replace(base_config, top_k=top_k)

        filters = data.get("filters") or {}
        filter_dict = {}
        if filters.get("source"):
            filter_dict["source_text"] = filters["source"]
        if filters.get("category"):
            filter_dict["category"] = filters["category"]
        if filters.get("tradition"):
            filter_dict["tradition"] = filters["tradition"]

        try:
            result = query_func(question, config=config, filter_dict=filter_dict or None)
        except UserInputError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            return build_json_error("Request could not be completed", 500, e)
        response = {
            "answer": result["answer"],
            "sources": _build_sources_response(result),
        }
        if "retrieval_mode" in result:
            response["retrieval_mode"] = result["retrieval_mode"]
        return jsonify(response)

    @bp_or_app.route("/api/agent", methods=["POST"])
    def api_agent():
        from agent.conversation import ConversationMemory

        data = request.get_json(silent=True) or {}
        question = (data.get("question") or "").strip()
        history = data.get("history") or []
        voice = (data.get("voice") or "").strip() or None
        if not question:
            return jsonify({"error": "No question provided"}), 400

        config = replace(base_config)
        memory = ConversationMemory(window=config.conversation_window)
        try:
            load_history_into_memory(memory, history, config)
            question = validate_and_prepare_question(question, config)
        except UserInputError as e:
            return jsonify({"error": str(e)}), 400

        try:
            result = run_agent_func(question, config=config, memory=memory, voice=voice)
        except Exception as e:
            return build_json_error("Request could not be completed", 500, e)
        return jsonify(result)

    @bp_or_app.route("/api/agent/stream", methods=["POST"])
    def api_agent_stream():
        data = request.get_json(silent=True) or {}
        question = (data.get("question") or "").strip()
        history = data.get("history") or []
        voice = (data.get("voice") or "").strip() or None
        if not question:
            return jsonify({"error": "No question provided"}), 400

        config = replace(base_config)
        try:
            q = validate_and_prepare_question(question, config)
        except UserInputError as e:
            return jsonify({"error": str(e)}), 400

        def event_stream():
            try:
                for event in run_agent_stream_func(
                    q,
                    config=config,
                    history=history,
                    voice=voice,
                ):
                    yield f"data: {json.dumps(event)}\n\n"
            except Exception as e:
                current_app.logger.exception("agent stream failed")
                msg = "Request failed" if not current_app.debug else f"Request failed: {type(e).__name__}"
                yield f"data: {json.dumps({'type': 'error', 'content': msg})}\n\n"

        return Response(
            stream_with_context(event_stream()),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @bp_or_app.route("/api/voices")
    def api_voices():
        return jsonify(
            {
                key: {"name": v["name"], "is_default": v.get("is_default", False)}
                for key, v in VOICES.items()
            }
        )


def _register_warmup(app, config: RAGConfig) -> None:
    def _warmup_rag():
        if not _rag_warmup_enabled():
            return
        try:
            _call_warmup(config)
        except Exception:
            pass

    if _rag_warmup_enabled():
        threading.Thread(target=_warmup_rag, daemon=True).start()


def _register_dual_warmup(app, english_config: RAGConfig, full_config: RAGConfig) -> None:
    def _warmup_both():
        if not _rag_warmup_enabled():
            return
        for config in (english_config, full_config):
            try:
                _call_warmup(config)
            except Exception:
                pass

    if _rag_warmup_enabled():
        threading.Thread(target=_warmup_both, daemon=True).start()


def _rag_api_relpath(path: str) -> str | None:
    """Map ``/api/...`` and blueprint ``/beta/api/...`` to the same ``/api/...`` key."""

    if not path:
        return None
    if path.startswith("/beta/api/"):
        return "/api/" + path[len("/beta/api/") :]
    if path.startswith("/api/"):
        return path
    return None


def _register_rag_api_key_gate(app: Flask) -> None:
    """Optional RAG_API_KEY / RAG_SESSION_PASSWORD, or session user_id (SQLite auth)."""

    @app.before_request
    def _rag_api_key_gate():
        path = _rag_api_relpath(request.path or "")
        if path is None:
            return
        if path in (
            "/api/health",
            "/api/auth/config",
            "/api/auth/me",
            "/api/auth/status",
            "/api/login",
            "/api/logout",
        ):
            return
        if not get_required_api_key() and not get_session_password():
            return
        ok, err = auth_allows_request(request, session)
        if not ok:
            return (
                jsonify(
                    {
                        "error": err or "Unauthorized",
                        "password_login_available": bool(get_session_password()),
                    }
                ),
                401,
            )
        return None


def _apply_cors_and_limits(app: Flask) -> None:
    app.config["MAX_CONTENT_LENGTH"] = int(
        os.environ.get("RAG_MAX_BODY_BYTES", str(2 * 1024 * 1024))
    )
    cors_raw = (os.environ.get("CORS_ORIGINS") or "").strip()
    if cors_raw and cors_raw != "*":
        try:
            from flask_cors import CORS
        except ImportError:
            return
        origins = [o.strip() for o in cors_raw.split(",") if o.strip()]
        if origins:
            CORS(
                app,
                resources={
                    r"/api/*": {"origins": origins},
                    r"/beta/api/*": {"origins": origins},
                },
                supports_credentials=True,
                allow_headers=["Content-Type", "Authorization", "X-API-Key", "X-CSRFToken"],
            )


def create_full_app() -> Flask:
    """Single corpus (full) at ``/`` — same behavior as legacy ``scripts/rag/app.py``."""
    rag_root = PROJECT_ROOT / "scripts" / "rag"
    app = Flask(
        __name__,
        template_folder=str(rag_root / "templates"),
        static_folder=str(rag_root / "static"),
        static_url_path="/static",
    )
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)
    app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)
    _apply_cors_and_limits(app)
    register_auth(app)
    _register_rag_api_key_gate(app)

    metadata_path = PROJECT_ROOT / "final" / "metadata.json"
    try:
        with open(metadata_path, encoding="utf-8") as f:
            corpus_meta = json.load(f)
    except FileNotFoundError:
        corpus_meta = {}

    filter_options = {
        "sources": sorted(corpus_meta.get("by_source", {}).keys()),
        "categories": sorted(corpus_meta.get("by_category", {}).keys()),
        "traditions": sorted(corpus_meta.get("by_tradition", {}).keys()),
        "total_verses": corpus_meta.get("total_verses", 0),
    }

    base_config = RAGConfig()

    k = get_required_api_key()
    show_key = k if (is_browser_key_exposure_enabled() and k) else None

    @app.route("/")
    def index():
        return render_template(
            "index.html",
            api_base="",
            browser_api_key=show_key,
            session_login_enabled=bool(get_session_password()),
        )

    _register_rag_routes(app, base_config, filter_options)
    _register_warmup(app, base_config)
    return app


def create_dual_app(english_config: RAGConfig, english_filters: dict) -> Flask:
    """Full multilingual corpus at ``/``, English beta at ``/beta``.

    The Flask app's template/static folders point at ``scripts/rag/`` (the main corpus).
    English templates/static live on a blueprint mounted at ``/beta``; the English
    template qualifies asset URLs with ``url_for('beta.static', ...)`` so they load
    from the blueprint's static folder rather than the app's.
    """
    rag_root = PROJECT_ROOT / "scripts" / "rag"
    eng_root = PROJECT_ROOT / "english-v1-rag"
    app = Flask(
        __name__,
        template_folder=str(rag_root / "templates"),
        static_folder=str(rag_root / "static"),
        static_url_path="/static",
    )
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)
    app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)
    _apply_cors_and_limits(app)
    register_auth(app)
    _register_rag_api_key_gate(app)

    metadata_path = PROJECT_ROOT / "final" / "metadata.json"
    try:
        with open(metadata_path, encoding="utf-8") as f:
            corpus_meta = json.load(f)
    except FileNotFoundError:
        corpus_meta = {}

    main_filters = {
        "sources": sorted(corpus_meta.get("by_source", {}).keys()),
        "categories": sorted(corpus_meta.get("by_category", {}).keys()),
        "traditions": sorted(corpus_meta.get("by_tradition", {}).keys()),
        "total_verses": corpus_meta.get("total_verses", 0),
    }
    main_config = RAGConfig()

    # english_config.py inserts english-v1-rag first on sys.path, so explicitly load
    # the full-corpus query/agent modules from scripts/rag — otherwise `from query
    # import query_rag` inside _register_rag_routes would resolve to the English one.
    full_query_func = _load_module_attr(
        "_full_query_module",
        rag_root / "query.py",
        "query_rag",
    )
    full_agent_module = _load_module(
        "_full_agent_module",
        rag_root / "agent" / "react_loop.py",
    )
    full_run_agent_func = full_agent_module.run_agent
    full_run_agent_stream_func = full_agent_module.run_agent_stream

    k = get_required_api_key()
    show_key = k if (is_browser_key_exposure_enabled() and k) else None

    @app.route("/")
    def index():
        return render_template(
            "index.html",
            api_base="",
            browser_api_key=show_key,
            session_login_enabled=bool(get_session_password()),
        )

    _register_rag_routes(
        app,
        main_config,
        main_filters,
        query_func=full_query_func,
        run_agent_func=full_run_agent_func,
        run_agent_stream_func=full_run_agent_stream_func,
    )

    beta_bp = Blueprint(
        "beta",
        __name__,
        url_prefix="/beta",
        template_folder=str(eng_root / "templates"),
        static_folder=str(eng_root / "static"),
        static_url_path="/static",
    )

    @beta_bp.route("/")
    def beta_index():
        # Blueprint templates are namespaced under beta/ so the file name does not
        # collide with the app-level scripts/rag/templates/index.html.
        return render_template("beta/index.html", api_base="/beta")

    # English query/agent come from sys.path resolution (english_config.py inserted
    # english-v1-rag first), so the default imports inside _register_rag_routes pick
    # them up — no explicit module loading needed here.
    _register_rag_routes(beta_bp, english_config, english_filters)
    app.register_blueprint(beta_bp)

    _register_dual_warmup(app, english_config, main_config)
    return app
