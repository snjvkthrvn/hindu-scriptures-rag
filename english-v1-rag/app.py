"""Flask web interface for the Hindu Scriptures RAG system.

Serves two corpora from a single app:
  /           — English-only corpus  (14k verses, always available)
  /main       — Full corpus with Sanskrit  (118k verses, when data exists)

Usage:
    python english-v1-rag/app.py   # http://0.0.0.0:5002 — English at /, full corpus at /main
"""

import json
import os
import secrets
import threading
from dataclasses import replace

from auth_backend import register_auth
from config import PROJECT_ROOT, RAGConfig
from flask import Blueprint, Flask, Response, jsonify, render_template, request, stream_with_context
from voices import VOICES
from werkzeug.middleware.proxy_fix import ProxyFix

from english_config import ENGLISH_VERSES_FILE, get_english_config

app = Flask(__name__)
# Railway / reverse proxies send X-Forwarded-Proto; without this, url_for(..., _external=True)
# can be http:// and Google OAuth returns redirect_uri_mismatch for https://-only URIs.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)
register_auth(app)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
def _build_sources_response(result):
    """Format search results for the frontend."""
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


def _make_rag_routes(bp_or_app, base_config, filter_options):
    """Register /api/sources, /api/query, /api/agent, /api/agent/stream on a Flask app or Blueprint."""

    @bp_or_app.route("/api/sources")
    def api_sources():
        return jsonify(filter_options)

    @bp_or_app.route("/api/query", methods=["POST"])
    def api_query():
        from query import query_rag

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
            result = query_rag(question, config=config, filter_dict=filter_dict or None)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

        return jsonify({"answer": result["answer"], "sources": _build_sources_response(result)})

    @bp_or_app.route("/api/agent", methods=["POST"])
    def api_agent():
        from agent.conversation import ConversationMemory
        from agent.react_loop import run_agent

        data = request.get_json(silent=True) or {}
        question = (data.get("question") or "").strip()
        history = data.get("history") or []
        voice = (data.get("voice") or "").strip() or None
        if not question:
            return jsonify({"error": "No question provided"}), 400

        config = replace(base_config)
        memory = ConversationMemory(window=config.conversation_window)
        for msg in history:
            memory.add(msg.get("role", "user"), msg.get("content", ""))

        try:
            result = run_agent(question, config=config, memory=memory, voice=voice)
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        return jsonify(result)

    @bp_or_app.route("/api/agent/stream", methods=["POST"])
    def api_agent_stream():
        from agent.react_loop import run_agent_stream

        data = request.get_json(silent=True) or {}
        question = (data.get("question") or "").strip()
        history = data.get("history") or []
        voice = (data.get("voice") or "").strip() or None
        if not question:
            return jsonify({"error": "No question provided"}), 400

        config = replace(base_config)

        def event_stream():
            try:
                for event in run_agent_stream(
                    question,
                    config=config,
                    history=history,
                    voice=voice,
                ):
                    yield f"data: {json.dumps(event)}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

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


# ---------------------------------------------------------------------------
# English corpus (root: /)
# ---------------------------------------------------------------------------
ENGLISH_FILTERS = {"sources": [], "categories": [], "traditions": [], "total_verses": 0}

try:
    with open(ENGLISH_VERSES_FILE) as f:
        _verses = json.load(f)
    _sources, _categories, _traditions = set(), set(), set()
    for v in _verses:
        s = v.get("source", {}).get("text", "")
        c = v.get("metadata", {}).get("category", "")
        t = v.get("metadata", {}).get("tradition", "")
        if s:
            _sources.add(s)
        if c:
            _categories.add(c)
        if t:
            _traditions.add(t)
    ENGLISH_FILTERS = {
        "sources": sorted(_sources),
        "categories": sorted(_categories),
        "traditions": sorted(_traditions),
        "total_verses": len(_verses),
    }
    del _verses, _sources, _categories, _traditions
except FileNotFoundError:
    pass

_english_config = get_english_config()


@app.route("/")
def index():
    return render_template("index.html", api_base="")


_make_rag_routes(app, _english_config, ENGLISH_FILTERS)


# ---------------------------------------------------------------------------
# Full corpus Blueprint (prefix: /main)
# ---------------------------------------------------------------------------
_main_templates = PROJECT_ROOT / "scripts" / "rag" / "templates"
_main_static = PROJECT_ROOT / "scripts" / "rag" / "static"

main_bp = Blueprint(
    "main",
    __name__,
    url_prefix="/main",
    template_folder=str(_main_templates),
    static_folder=str(_main_static),
    static_url_path="/static",
)

_metadata_path = PROJECT_ROOT / "final" / "metadata.json"
try:
    with open(_metadata_path) as f:
        _corpus_meta = json.load(f)
except FileNotFoundError:
    _corpus_meta = {}

MAIN_FILTERS = {
    "sources": sorted(_corpus_meta.get("by_source", {}).keys()),
    "categories": sorted(_corpus_meta.get("by_category", {}).keys()),
    "traditions": sorted(_corpus_meta.get("by_tradition", {}).keys()),
    "total_verses": _corpus_meta.get("total_verses", 0),
}

_main_config = RAGConfig()


@main_bp.route("/")
def main_index():
    return render_template("index.html", api_base="/main")


_make_rag_routes(main_bp, _main_config, MAIN_FILTERS)
app.register_blueprint(main_bp)


# ---------------------------------------------------------------------------
# Background warmup
# ---------------------------------------------------------------------------
def _warmup_rag():
    if os.environ.get("RAG_WARMUP", "1") != "1":
        return
    try:
        from search import warmup

        warmup(_english_config)
    except Exception:
        pass


if os.environ.get("RAG_WARMUP", "1") == "1":
    threading.Thread(target=_warmup_rag, daemon=True).start()


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5002)
