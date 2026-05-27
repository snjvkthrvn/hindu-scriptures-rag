"""Run the Qdrant indexer against embedded local storage.

Use this when Docker/Qdrant server is unavailable but `QDRANT_URL` is present
in `.env`. The normal `indexer.py` entrypoint remains the server/default path.
"""

from __future__ import annotations

import os
import sys

# Must happen before importing indexer/config-driven RAGConfig creation.
# Set in-process (not via shell) so dotenv's override=False keeps it empty;
# on Windows an empty shell env var is dropped and .env would re-add QDRANT_URL.
os.environ["QDRANT_URL"] = ""

from indexer import index  # noqa: E402


if __name__ == "__main__":
    # Pass --resume to continue from the per-batch checkpoint after an
    # interruption; without it the collection is dropped and rebuilt fresh.
    index(resume="--resume" in sys.argv)
