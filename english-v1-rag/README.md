# English-only RAG (v1)

This folder holds the English-translation-only variant of the Hindu Scriptures RAG. Only verses with `content.translation` are indexed — Sanskrit-only sources are excluded — and the corpus is roughly an order of magnitude smaller (~13,800 verses vs ~118k in the full corpus).

In production this app is **also the dual-app entrypoint**: `app.py` (port 5002) serves the full multilingual corpus at `/` and mounts the English UI as a Flask blueprint at `/beta`. To run only the English experience locally, use the dev paths below.

For technical detail (sources, parsers, indexer flow, schema), see [ENGLISH_RAG_SUMMARY.md](ENGLISH_RAG_SUMMARY.md). For the project-wide overview, see [../README.md](../README.md).

## Contents

- **`verses_english_only.json`** — ~13,800 verses from Rigveda, Ramayana, Bhagavad Gita, Isha + Mundaka Upanishads (Mueller), 10 Upanishads (Claude), Yoga Sutras, Bhagavad Gita (Arnold), Mahabharata (all English translations)
- **`build_english_verses.py`** — aggregates English sources into the verse JSON
- **`index_english.py`** — indexes into Qdrant collection `hindu_scriptures_english`
- **`app.py`** — Flask entrypoint (dual app in production; mounts English at `/beta`)
- **`query.py`**, **`agent/`**, **`prompt_templates.py`** — English-flavored RAG surface

## Usage

### 1. Build the English verse subset (only after corpus changes)

```bash
python english-v1-rag/build_english_verses.py
```

This regenerates `verses_english_only.json` from the main corpus (`final/verses_enriched.json`) plus the extra Gutenberg/sacred-texts sources listed in [ENGLISH_RAG_SUMMARY.md](ENGLISH_RAG_SUMMARY.md).

### 2. Install RAG dependencies

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements-rag.txt
```

### 3. Set API keys

Create `.env` in the project root with at least `COHERE_API_KEY` (embeddings) and either `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` (answer generation).

### 4. Index into Qdrant

```bash
python english-v1-rag/index_english.py
```

Resumable: `python english-v1-rag/index_english.py --resume`.

For deployment via Docker Compose, `make deploy-index` runs the indexer inside the running container.

## Querying

The English collection is selected automatically by `english_config.py` — no manual config change needed when running `english-v1-rag/app.py` or `cli.py`.

If you want to query the English collection from the full-corpus code paths in `scripts/rag/`, override at construction time:

```python
from dataclasses import replace
from scripts.rag.config import RAGConfig

config = replace(RAGConfig(), qdrant_collection="hindu_scriptures_english")
```

## Embedding model

Default: `embed-multilingual-v3.0` (1,024 dims) — the multilingual model is chosen for parity with the full corpus. For an English-only deployment, `embed-english-v3.0` is a better fit; change it in `scripts/rag/config.py` and reindex (embeddings must match between index and query).

## Troubleshooting

**Indexing crashes with exit 139 / segfault.** Known issue with Python 3.14 + fastembed on some platforms. Pin to Python 3.11 or 3.12 (`pyenv install 3.12 && pyenv local 3.12`) or run the indexer inside Docker.

**`/beta` returns 404 in dev.** `python english-v1-rag/app.py` is the dual-app entrypoint that mounts `/beta`. `python scripts/rag/app.py` is full-corpus-only and won't serve `/beta`.

**Qdrant collection not found.** The collection name is `hindu_scriptures_english` (separate from the full corpus's `hindu_scriptures`). Run `python english-v1-rag/index_english.py` to create and populate it.
