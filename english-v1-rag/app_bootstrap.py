"""Shared bootstrap for the dual Flask app.

Used by both ``english-v1-rag/app.py`` for local/Docker runs and root
``app.py`` for Vercel's WSGI discovery.
"""

from __future__ import annotations

import json
from pathlib import Path

# Import english_config first: it inserts ``english-v1-rag`` and ``scripts/rag``
# on sys.path so the English beta can shadow shared prompt/agent modules.
from english_config import ENGLISH_VERSES_FILE, get_english_config

from app_factory import create_dual_app


def load_english_filters(path: Path = ENGLISH_VERSES_FILE) -> dict:
    filters = {"sources": [], "categories": [], "traditions": [], "total_verses": 0}

    try:
        with open(path, encoding="utf-8") as f:
            verses = json.load(f)
    except FileNotFoundError:
        return filters

    sources, categories, traditions = set(), set(), set()
    for verse in verses:
        source = verse.get("source", {}).get("text", "")
        category = verse.get("metadata", {}).get("category", "")
        tradition = verse.get("metadata", {}).get("tradition", "")
        if source:
            sources.add(source)
        if category:
            categories.add(category)
        if tradition:
            traditions.add(tradition)

    return {
        "sources": sorted(sources),
        "categories": sorted(categories),
        "traditions": sorted(traditions),
        "total_verses": len(verses),
    }


def create_app():
    return create_dual_app(get_english_config(), load_english_filters())
