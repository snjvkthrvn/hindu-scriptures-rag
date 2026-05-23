# Hindu Scriptures RAG

A retrieval-augmented chat interface over a 118k-verse corpus of Hindu scripture (Vedas, Upanishads, Gita, Mahabharata, Ramayana, Ramcharitmanas), with both a full multilingual experience and an English-only beta. Two pieces:

1. A **data pipeline** that builds a unified verse corpus from public-domain GitHub repos and Project Gutenberg.
2. A **Flask web app** that indexes the corpus into Qdrant, retrieves with hybrid (dense + BM25) search, and answers questions via Anthropic Claude or OpenAI.

## Corpus

`final/verses_enriched.json` — 118,358 verses, schema-validated.

| Scripture | Verses | Source |
|---|---:|---|
| Bhagavad Gita | 701 | DharmicData (GitHub) |
| 10 Principal Upanishads | 546 | indian-scriptures (GitHub) — partial; see caveat below |
| Rigveda | 10,200 | DharmicData |
| Atharvaveda | 6,079 | DharmicData |
| Yajurveda | 2,027 | DharmicData |
| Mahabharata (Critical Edition) | 73,816 | DharmicData |
| Valmiki Ramayana | 22,742 | DharmicData |
| Ramcharitmanas | 2,247 | DharmicData |
| **Total** | **118,358** | |

The pipeline also extracts **13,947 commentary entries** alongside the verses.

**Upanishad caveat.** The `indian-scriptures` source CSVs are incomplete. Chandogya is entirely absent (0/630), Brihadaranyaka has 104 of 891 verses, Taittiriya 20 of 71, Katha 71 of 119. The other six principal Upanishads are complete. This is a source data limitation, not a pipeline defect.

## Web app

Two Flask processes share a backend in `scripts/rag/`. In production both serve through one Docker container on port 5002, routed by Caddy:

| URL | Serves | Code path |
|---|---|---|
| `/` | Full multilingual corpus | `scripts/rag/templates/index.html` |
| `/beta` | English-only beta | `english-v1-rag/templates/beta/index.html` (mounted as a Flask blueprint) |

Both routes hit the same `/api/query` and `/api/agent/stream` endpoints (the beta proxies via `/beta/api/...`). Shared application factory lives in [`scripts/rag/app_factory.py`](scripts/rag/app_factory.py); `english-v1-rag/app.py` and `scripts/rag/app.py` are thin entrypoints.

**Dev (no Docker):** `python english-v1-rag/app.py` (port 5002, dual-app) or `python scripts/rag/app.py` (port 5001, full corpus only).

### Retrieval

- **Vector store:** Qdrant (hybrid: dense + BM25 sparse). The free Cohere embedding model `embed-multilingual-v3.0` (1,024 dims) is the default; English-only deployments can swap to `embed-english-v3.0`.
- **Hybrid router** in [`scripts/rag/hybrid_router.py`](scripts/rag/hybrid_router.py): plain-English questions default to the English corpus; verse refs, Devanagari, transliteration, commentary/school signals route to the full corpus. Weak first-pass evidence escalates to both, fused with Reciprocal Rank Fusion.
- **Two query modes:** one-shot RAG (`query.py` — retrieve once, answer) and ReAct agent (`agent/react_loop.py` — iterative tool use across `search_scriptures`, `search_commentaries`, `get_verse`, `compare_schools`, `search_story`).

### Security

User input and tool results are wrapped in `<<<UNTRUSTED_USER ...>>>` and `<<<TOOL_RESULT name=... END_TOOL_RESULT>>>` delimiters; the system prompt instructs the model to treat both as data, never as instructions. Delimiter break-out attempts are scrubbed in [`scripts/rag/api_security.py`](scripts/rag/api_security.py). Auth (session + API key), CORS, rate limiting, and OpenAI moderation are layered in `auth_backend.py`, `api_security.py`, and `moderation.py`. Tool arguments are bounded and category/school inputs are allowlisted.

## Quick start (web app)

```bash
git clone https://github.com/snjvkthrvn/hindu-scriptures-rag.git
cd hindu-scriptures-rag

cp .env.example .env       # set ANTHROPIC_API_KEY, COHERE_API_KEY (and optional auth vars)
make deploy                # docker compose up: Qdrant + rag service + Caddy
make deploy-index          # one-time: embed verses into Qdrant
```

Then open `http://localhost/` (full corpus) or `http://localhost/beta` (English).

Stop and inspect:

```bash
make deploy-down           # docker compose down
make deploy-logs           # tail logs
```

## Rebuilding the corpus

The current `final/verses_enriched.json` is already complete. You only need to rebuild if you've changed the parsers, added a source, or are starting from a fresh clone.

```bash
# Windows requires UTF-8 console (the parsers print emoji):
$env:PYTHONUTF8 = "1"    # PowerShell — or `set PYTHONUTF8=1` in cmd.exe

pip install -r requirements.txt

# 1. Download from GitHub (~2 min). Project Gutenberg downloads are optional.
python scripts/downloaders/download_github.py

# 2. Parse all sources into one verse list (~5 min).
python scripts/parse_all_scriptures.py        # → final/verses.json

# 3. Enrich with themes and life-domain tags (~1 min).
python scripts/formatters/add_metadata.py --input final/verses.json
# → final/verses_enriched.json   ← this is the RAG corpus

# 4. Optional: produce a deduplicated version (~10 sec).
python scripts/formatters/deduplicate.py --input final/verses.json
# → final/verses_deduped.json
```

The older orchestrator `scripts/main.py` (driven by the Makefile) chains the same stages but assumes a Unix layout and hardcodes `~/hindu-scriptures-rag` as the base path. Use it on Linux/macOS; on Windows, drive the scripts individually as shown above.

### What the pipeline does NOT do

- **Download from sacred-texts.com.** That source is blocked by Cloudflare and excludes ClaudeBot via robots.txt; the `download_sacred_texts.py` script remains in the tree but won't fetch anything new. The texts attributed to it in earlier versions of these docs are sourced from the GitHub repos instead.
- **Fuzzy deduplication.** The deduper merges exact duplicates after whitespace/punctuation normalization (the earlier O(n²) similarity-based dedup wouldn't finish at 118k verses). Indirect duplicates between e.g. Atharvaveda and Rigveda are caught; near-duplicates with varied phrasing are not. ~1,800 exact duplicates were found (1.5% of corpus) — those are real, attested cross-quotations.

## Repository layout

```
.
├── scripts/
│   ├── parse_all_scriptures.py    # primary parser (118k verses)
│   ├── main.py                    # legacy Unix-only orchestrator
│   ├── downloaders/               # GitHub + Project Gutenberg downloaders
│   ├── parsers/                   # per-source parsers
│   ├── formatters/                # normalize, enrich, deduplicate
│   ├── utils/                     # Unicode, verse boundary detection
│   └── rag/                       # web app + RAG core
│       ├── app.py, cli.py         # entrypoints
│       ├── app_factory.py         # shared Flask factory (dual app + blueprint)
│       ├── api_security.py        # input/output sanitization
│       ├── auth_backend.py        # session + API key auth
│       ├── config.py              # RAGConfig
│       ├── embeddings.py          # Cohere client
│       ├── vector_store.py        # Qdrant wrapper
│       ├── indexer.py, ingest.py  # build the Qdrant collection
│       ├── search.py              # hybrid retrieval
│       ├── hybrid_router.py       # English vs full-corpus routing
│       ├── hybrid_query.py        # parallel retrieval + RRF fusion
│       ├── query.py               # one-shot RAG
│       └── agent/                 # ReAct agent loop + tools
│
├── english-v1-rag/                # English-only beta (parallel corpus + UI)
│   ├── app.py                     # dual-app entrypoint (port 5002)
│   ├── build_english_verses.py    # English subset builder (~13.8k verses)
│   ├── index_english.py           # index into hindu_scriptures_english collection
│   ├── english_config.py          # RAGConfig override (different collection)
│   ├── query.py                   # English-flavored prompts + hybrid query
│   ├── agent/, parsers/           # mirrors of scripts/rag/{agent,parsers}
│   └── templates/beta/, static/   # /beta UI assets
│
├── final/                         # corpus output (git-ignored)
│   ├── verses_enriched.json       ← USE THIS for RAG
│   ├── verses.json                # pre-enrichment
│   ├── verses_deduped.json        # exact-dedup variant
│   └── metadata.json              # corpus statistics
│
├── raw/                           # downloaded source files (git-ignored)
├── Caddyfile, Dockerfile, docker-compose.yml
├── requirements.txt               # data pipeline deps
├── requirements-rag.txt           # web app deps
└── english-v1-rag/README.md, ENGLISH_RAG_SUMMARY.md
```

## Verse schema

```json
{
  "id": "bg_2_47",
  "source": {
    "text": "Bhagavad Gita",
    "chapter": 2,
    "chapter_name": "Sankhya Yoga",
    "verse": 47,
    "section": null
  },
  "content": {
    "sanskrit": "कर्मण्येवाधिकारस्ते मा फलेषु कदाचन।",
    "transliteration": "karmaṇy evādhikāras te mā phaleṣu kadācana",
    "translation": "You have a right to perform your prescribed duties, but you are not entitled to the fruits of your actions.",
    "translations": { "swami_sivananda": "...", "swami_gambhirananda": "..." },
    "word_by_word": {}
  },
  "metadata": {
    "category": "shruti | smriti | itihasa",
    "tradition": "vedanta",
    "themes": ["karma_yoga", "detachment", "duty"],
    "philosophical_schools": ["advaita", "dvaita", "vishishtadvaita"],
    "life_domains": ["work", "motivation"]
  },
  "commentaries": [
    { "author": "Shankaracharya", "school": "advaita", "text": "..." }
  ],
  "provenance": {
    "download_source": "dharmic-data",
    "original_url": "https://github.com/bhavykhatri/DharmicData",
    "license": "ODbL-1.0"
  }
}
```

`category`, `tradition`, `themes`, `philosophical_schools`, `life_domains` are auto-tagged during enrichment; coverage is partial (themes hit ~99.86% of verses, life-domain tagging is sparser by design — only verses with clear practical application get tagged).

## Configuration

`.env` (copy from `.env.example`):

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | LLM (default provider) |
| `OPENAI_API_KEY` | Alternative LLM, also used for moderation |
| `COHERE_API_KEY` | Embeddings (required for indexing and query) |
| `QDRANT_URL` | Vector store endpoint (default `http://localhost:6333` in Docker) |
| `SESSION_PASSWORD` | If set, enables session-based login |
| `RAG_API_KEY` | Required for raw `/api/*` access from clients without a session |
| `CORS_ORIGINS` | Comma-separated; also used by the CSRF origin guard |
| `DOMAIN` | Caddy uses this for the `localhost` → real-host swap |

## Licenses

Pipeline code: MIT. Source data inherits each repo's license:

- DharmicData — ODbL-1.0
- indian-scriptures — CC-BY-4.0
- Project Gutenberg — public domain

Respect those when redistributing the corpus.

## Subsystem docs

- [`english-v1-rag/README.md`](english-v1-rag/README.md) — English beta overview
- [`english-v1-rag/ENGLISH_RAG_SUMMARY.md`](english-v1-rag/ENGLISH_RAG_SUMMARY.md) — technical reference for the English RAG (sources, parsers, indexing)
- [`UPANISHAD_TRANSLATIONS.md`](UPANISHAD_TRANSLATIONS.md) — historical notes on a one-off Upanishad translation scrape (Feb 2026)
