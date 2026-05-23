# English RAG v1 — Technical Reference

## Overview

The **English-only RAG** is a parallel pipeline that indexes only verses with English translations into a separate Qdrant collection (`hindu_scriptures_english`). The retrieval primitives (indexer, vector store, embeddings, hybrid search) come from `scripts/rag/`; the corpus, query path, prompts, and agent live here.

In production, `english-v1-rag/app.py` is the dual-app entrypoint: it serves the full multilingual corpus at `/` and mounts the English UI as a Flask blueprint at `/beta`. Local dev can run this file directly on port 5002.

**Corpus size:** ~13,800 verses (vs ~118k in the full corpus with Sanskrit, commentaries, and additional sources).

For setup and quick commands see [README.md](README.md); for the project overview see [../README.md](../README.md).

---

## Architecture

```
english-v1-rag/
├── app.py                    # Dual-app Flask entrypoint (port 5002, mounts /beta)
├── cli.py                    # Interactive Q&A
├── build_english_verses.py   # Aggregates all English sources → verses_english_only.json
├── index_english.py          # Indexes into Qdrant (calls scripts/rag/indexer.py)
├── english_config.py         # RAGConfig override (collection, top_k, prompts)
├── query.py                  # One-shot RAG (English prompts + hybrid query)
├── prompt_templates.py       # English-flavored system prompts
├── agent/                    # ReAct agent (mirrors scripts/rag/agent/ with English tools)
├── parsers/                  # Source-specific parsers
│   ├── yoga_sutras.py        # raw/sacred-texts/yoga_sutras.html
│   ├── gutenberg_gita.py     # raw/gutenberg/pg2388_bhagavad_gita.txt (Arnold)
│   └── gutenberg_mahabharata.py  # raw/gutenberg/pg15474_mahabharata.txt (Ganguli)
├── verses_english_only.json  # Output corpus (built by build_english_verses.py)
└── templates/beta/, static/  # /beta UI assets
```

**Shared from `scripts/rag/`:** `indexer.py`, `search.py`, `vector_store.py`, `embeddings.py`, `hybrid_query.py`, `hybrid_router.py`, `config.py`, `api_security.py`, `moderation.py`, `auth_backend.py`. The English side imports these directly — only the corpus, collection name, and prompts diverge.

---

## Data Sources (build_english_verses.py)

| Source | Location | Loader | Verses |
|--------|----------|--------|--------|
| Rigveda | raw/sacred-texts/rigveda.json | load_rigveda() | 9,538 |
| Ramayana | raw/gutenberg/ramayana.json | load_ramayana() | 1,830 |
| Bhagavad Gita | processed/tier1-essential/parsed_verses.json | load_bhagavad_gita() | 701 |
| Isha Upanishad | translations/isha_upanishad_mueller.csv | load_upanishad_csv() | 18 |
| Mundaka Upanishad | translations/mundaka_upanishad_mueller.csv | load_upanishad_csv() | 13 |
| **Upanishads (Claude)** | final/verses_enriched.json | load_claude_upanishads() | 546 |
| Yoga Sutras | raw/sacred-texts/yoga_sutras.html | parse_yoga_sutras_html() | 194 |
| Bhagavad Gita (Arnold) | raw/gutenberg/pg2388_bhagavad_gita.txt | parse_arnold_gita() | 56 |
| Mahabharata | raw/gutenberg/pg15474_mahabharata.txt | parse_mahabharata_ganguli() | 2,753 |

**Claude Upanishads** (from translate_verses.py → translations_cache → merge into verses_enriched): Isha, Kena, Katha, Prashna, Mundaka, Mandukya, Taittiriya, Aitareya, Brihadaranyaka, Svetasvatara. Filtered by `_is_english_text()` to exclude Devanagari.

---

## Parsers

- **yoga_sutras.py**: Parses sacred-texts HTML; regex `SUTRA_PATTERN` finds `N.M.` sutras; handles multiple sutras per `<p>`.
- **gutenberg_gita.py**: Splits by `CHAPTER N`, then by speaker blocks (Arjuna., Krishna., Sanjaya, Dhritirashtra).
- **gutenberg_mahabharata.py**: Splits by `SECTION N` (Roman numerals), then paragraphs. Tracks parva from `BOOK N` headers.

---

## Build Pipeline

1. **Build verses:** `python english-v1-rag/build_english_verses.py`
   - Loads all sources, normalizes schema, deduplicates by id (later overwrites earlier), sorts, writes `verses_english_only.json`.

2. **Index:** `python english-v1-rag/index_english.py`
   - Uses `RAGConfig(verses_file=verses_english_only.json, qdrant_collection="hindu_scriptures_english")`
   - Calls `index()` from `scripts/rag/indexer.py`
   - Cohere embed-multilingual-v3.0 (or embed-english-v3.0 if switched), Qdrant hybrid (dense + BM25)
   - Resumable: `--resume`

---

## Using the English RAG

Point the RAG at the English collection:

- **config.py:** `qdrant_collection: str = "hindu_scriptures_english"`
- Or per-call: `config = replace(RAGConfig(), qdrant_collection="hindu_scriptures_english")`

App (`app.py`) and CLI (`cli.py`) use `RAGConfig()`; change the default or override where config is created.

---

## Embedding Model

Default: `embed-multilingual-v3.0` (1024 dims). For English-only corpus, `embed-english-v3.0` is a better fit. Switch in `config.py`:

```python
cohere_model: str = "embed-english-v3.0"
```

Reindex after changing; embeddings must match between index and query.

---

## Verse Schema

```python
{
  "id": str,
  "source": {"text": str, "chapter": int, "chapter_name": str, "verse": int},
  "content": {"sanskrit": str, "transliteration": str, "translation": str},
  "metadata": {"category": str, "tradition": str, "themes": []},
  "commentaries": [],
  "provenance": {"download_source": str, "license": str, ...}
}
```

---

## Files NOT Used (Index Pages / Wrong Content)

- upanishads_part_i_sbe.html, upanishads_part_ii_sbe.html — index pages, link out
- pg42541_yoga_sutras.txt — Italian (Ricordi), not Yoga Sutras
- pg34125_vedanta_sutras.txt — Sarva-Darsana-Samgraha, not Vedanta Sutras
- vishnu_purana.html, viveka_chudamani.html, thirty_minor_upanishads.html — index pages

---

## Key Paths

| Path | Purpose |
|------|---------|
| english-v1-rag/verses_english_only.json | English corpus output |
| english-v1-rag/build_english_verses.py | Build script |
| english-v1-rag/index_english.py | Index script |
| final/verses_enriched.json | Source for Claude Upanishads |
| final/translations_cache.json | Claude translations (idx_NNN → text) |
| scripts/rag/config.py | RAG config (collection, model, etc.) |
| scripts/rag/indexer.py | Shared indexer |

---

## Quick Commands

```bash
# Build
python english-v1-rag/build_english_verses.py

# Index (requires COHERE_API_KEY in .env)
python english-v1-rag/index_english.py
python english-v1-rag/index_english.py --resume

# Query (after setting qdrant_collection in config)
python scripts/rag/cli.py
# or
python scripts/rag/app.py
```
