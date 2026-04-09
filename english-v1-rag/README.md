# English-only RAG (v1)

This folder holds the English-translation-only variant of the Hindu Scriptures RAG.

Only verses with `content.translation` are indexed — Sanskrit-only sources are excluded.

## Contents

- **verses_english_only.json** — ~13,800 verses from Rigveda, Ramayana, Bhagavad Gita, Isha/Mundaka Upanishads (Mueller), 10 Upanishads (Claude), Yoga Sutras, Bhagavad Gita (Arnold), Mahabharata (all English translations)
- **build_english_verses.py** — Aggregates English sources into RAG verse format
- **index_english.py** — Indexes into Qdrant collection `hindu_scriptures_english`

## Usage

### 1. Build verses (already done)

```bash
python english-v1-rag/build_english_verses.py
```

### 2. Install RAG dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-rag.txt python-dotenv fastembed
```

### 3. Set API keys

Create `.env` in project root with `COHERE_API_KEY` (required for embeddings).

### 4. Index

```bash
source .venv/bin/activate
python english-v1-rag/index_english.py
```

To resume after interrupt: `python english-v1-rag/index_english.py --resume`

## Querying the English RAG

Update `scripts/rag/config.py` or pass `qdrant_collection="hindu_scriptures_english"` when querying to use this index instead of the full corpus.

## Troubleshooting

**Indexing crashes (exit 139 / segfault):** This can happen with Python 3.14 and fastembed. Try:
- Use Python 3.11 or 3.12: `pyenv install 3.12 && pyenv local 3.12`
- Or run indexing in a separate process/Docker
