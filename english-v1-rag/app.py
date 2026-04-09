"""Flask web interface for the English-only Hindu Scriptures RAG system.

Usage:
    python english-v1-rag/app.py
"""

import json
import sys
from dataclasses import replace
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request, stream_with_context

# english_config sets up sys.path (eng_dir first, then rag_dir)
from english_config import get_english_config, ENGLISH_VERSES_FILE

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Build filter options from verses_english_only.json at startup
# ---------------------------------------------------------------------------
FILTER_OPTIONS = {"sources": [], "categories": [], "traditions": [], "total_verses": 0}

try:
    with open(ENGLISH_VERSES_FILE) as f:
        _verses = json.load(f)
    _sources = set()
    _categories = set()
    _traditions = set()
    for v in _verses:
        src = v.get("source", {}).get("text", "")
        cat = v.get("metadata", {}).get("category", "")
        trad = v.get("metadata", {}).get("tradition", "")
        if src:
            _sources.add(src)
        if cat:
            _categories.add(cat)
        if trad:
            _traditions.add(trad)
    FILTER_OPTIONS = {
        "sources": sorted(_sources),
        "categories": sorted(_categories),
        "traditions": sorted(_traditions),
        "total_verses": len(_verses),
    }
    del _verses, _sources, _categories, _traditions
except FileNotFoundError:
    pass

# Shared base config (immutable -- each request gets a copy)
_base_config = get_english_config()


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

    top_k = data.get("top_k", _base_config.top_k)
    try:
        top_k = max(1, min(int(top_k), 20))
    except (ValueError, TypeError):
        top_k = _base_config.top_k

    config = replace(_base_config, top_k=top_k)

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

    sources = []
    total_sources = max(len(result.get("sources", [])), 1)
    for i, src in enumerate(result.get("sources", [])):
        header = src.get("source_text", "")
        if src.get("chapter_name"):
            header += f" - {src['chapter_name']}"
        if src.get("verse_num"):
            header += f", Verse {src['verse_num']}"

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
    """Agentic RAG query -- Claude reasons, calls tools, synthesizes."""
    from agent.react_loop import run_agent
    from agent.conversation import ConversationMemory

    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    history = data.get("history") or []

    if not question:
        return jsonify({"error": "No question provided"}), 400

    config = replace(_base_config)

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
    """Streaming agentic query -- SSE events for thinking steps + answer."""
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
    app.run(debug=True, host="0.0.0.0", port=5002)
