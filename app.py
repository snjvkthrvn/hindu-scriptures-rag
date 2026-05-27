"""Vercel WSGI entrypoint for the dual Hindu Scriptures RAG app.

Vercel discovers a top-level ``app`` object in ``app.py``. The actual Flask app
is still assembled by the existing English/full-corpus bootstrap.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
ENGLISH_RAG_DIR = PROJECT_ROOT / "english-v1-rag"
RAG_DIR = PROJECT_ROOT / "scripts" / "rag"

for path in (str(RAG_DIR), str(ENGLISH_RAG_DIR)):
    if path in sys.path:
        sys.path.remove(path)
    sys.path.insert(0, path)

from app_bootstrap import create_app  # noqa: E402

app = create_app()
