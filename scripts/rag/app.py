"""Flask web interface for the Hindu Scriptures RAG system.

Usage:
    python scripts/rag/app.py
    # or: make web
"""

import json
import sys
from dataclasses import replace
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request, stream_with_context

from config import RAGConfig, PROJECT_ROOT

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Load filter options from metadata.json at startup
# ---------------------------------------------------------------------------
_metadata_path = PROJECT_ROOT / "final" / "metadata.json"

try:
    with open(_metadata_path) as f:
        _corpus_meta = json.load(f)
except FileNotFoundError:
    _corpus_meta = {}

FILTER_OPTIONS = {
    "sources": sorted(_corpus_meta.get("by_source", {}).keys()),
    "categories": sorted(_corpus_meta.get("by_category", {}).keys()),
    "traditions": sorted(_corpus_meta.get("by_tradition", {}).keys()),
    "total_verses": _corpus_meta.get("total_verses", 0),
}

# Shared base config (immutable — each request gets a copy)
_base_config = RAGConfig()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/sources")
def api_sources():
    return jsonify(FILTER_OPTIONS)


@app.route("/api/query", methods=["POST"])
def api_query():
    """Non-agentic RAG query (direct search + LLM)."""
    from query import query_rag

    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()

    if not question:
        return jsonify({"error": "No question provided"}), 400

    # Build per-request config
    top_k = data.get("top_k", _base_config.top_k)
    try:
        top_k = max(1, min(int(top_k), 20))
    except (ValueError, TypeError):
        top_k = _base_config.top_k

    config = replace(_base_config, top_k=top_k)

    # Build filters
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

    # Format sources for the frontend
    sources = []
    total_sources = max(len(result.get("sources", [])), 1)
    for i, src in enumerate(result.get("sources", [])):
        header = src.get("source_text", "")
        if src.get("chapter_name"):
            header += f" - {src['chapter_name']}"
        if src.get("verse_num"):
            header += f", Verse {src['verse_num']}"

        # RRF fusion scores are small fractions; show ordinal relevance rank instead
        similarity = round((1 - (i / total_sources)) * 100, 1)

        sources.append({
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
        })

    return jsonify({
        "answer": result["answer"],
        "sources": sources,
    })


@app.route("/api/agent", methods=["POST"])
def api_agent():
    """Agentic RAG query — Claude reasons, calls tools, synthesizes."""
    from agent.react_loop import run_agent
    from agent.conversation import ConversationMemory

    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    history = data.get("history") or []

    if not question:
        return jsonify({"error": "No question provided"}), 400

    config = replace(_base_config)

    # Build conversation memory from history
    memory = ConversationMemory(window=config.conversation_window)
    for msg in history:
        memory.add(msg.get("role", "user"), msg.get("content", ""))

    try:
        result = run_agent(question, config=config, memory=memory)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify(result)


@app.route("/api/agent/stream", methods=["POST"])
def api_agent_stream():
    """Streaming agentic query — SSE events for thinking steps + answer."""
    from agent.react_loop import run_agent_stream

    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    history = data.get("history") or []

    if not question:
        return jsonify({"error": "No question provided"}), 400

    config = replace(_base_config)

    def event_stream():
        try:
            for event in run_agent_stream(question, config=config, history=history):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return Response(
        stream_with_context(event_stream()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)
