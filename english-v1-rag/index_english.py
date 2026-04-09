#!/usr/bin/env python3
"""Index English-only verses into Qdrant for the english-v1-rag.

Uses a separate collection (hindu_scriptures_english) to avoid conflicts.
Run from project root:

  python english-v1-rag/index_english.py
  python english-v1-rag/index_english.py --resume
"""

import sys
from pathlib import Path

# Add scripts/rag for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "rag"))

from config import RAGConfig
from indexer import index


def main():
    verses_file = PROJECT_ROOT / "english-v1-rag" / "verses_english_only.json"
    if not verses_file.exists():
        print(f"Error: {verses_file} not found. Run build_english_verses.py first.")
        sys.exit(1)

    config = RAGConfig(
        verses_file=verses_file,
        qdrant_collection="hindu_scriptures_english",
        cohere_model="embed-english-v3.0",
    )
    resume = "--resume" in sys.argv
    index(config=config, resume=resume)


if __name__ == "__main__":
    main()
