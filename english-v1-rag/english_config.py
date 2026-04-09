"""Configuration helper for the English-only RAG system.

Reuses RAGConfig from scripts/rag but overrides collection name and verses file
to point at the English-only corpus.
"""

import sys
from pathlib import Path

# Ensure our own directory is first on sys.path so local modules (agent/,
# prompt_templates, etc.) shadow the shared ones.
_eng_dir = str(Path(__file__).resolve().parent)
_rag_dir = str(Path(__file__).resolve().parent.parent / "scripts" / "rag")

if _eng_dir not in sys.path:
    sys.path.insert(0, _eng_dir)
if _rag_dir not in sys.path:
    # Insert _after_ _eng_dir so local modules take priority
    idx = sys.path.index(_eng_dir) + 1
    sys.path.insert(idx, _rag_dir)

from config import RAGConfig, PROJECT_ROOT  # noqa: E402

ENGLISH_RAG_DIR = Path(__file__).resolve().parent
ENGLISH_VERSES_FILE = ENGLISH_RAG_DIR / "verses_english_only.json"


def get_english_config(**overrides) -> RAGConfig:
    """Return a RAGConfig pre-configured for the English-only collection."""
    defaults = {
        "qdrant_collection": "hindu_scriptures_english",
        "verses_file": ENGLISH_VERSES_FILE,
        "cohere_model": "embed-english-v3.0",
    }
    defaults.update(overrides)
    return RAGConfig(**defaults)
