# Quick Start

Get the chat UI running in under five minutes. For deeper context (architecture, corpus details, schema, deployment internals), see [README.md](README.md).

## Prerequisites

- Python 3.10 or higher
- Docker + Docker Compose (recommended) **or** a local Qdrant instance
- A Gemini API key for the full corpus, a Cohere API key for `/beta`, and either Anthropic or OpenAI for answer generation

## TL;DR — Docker

```bash
git clone https://github.com/snjvkthrvn/hindu-scriptures-rag.git
cd hindu-scriptures-rag

cp .env.example .env       # fill in GEMINI_API_KEY, COHERE_API_KEY, and ANTHROPIC_API_KEY
make deploy                # starts Qdrant + Caddy + the rag service
make deploy-index          # one-time: embed verses into Qdrant
```

Open:
- `http://localhost/` — full multilingual corpus
- `http://localhost/beta` — English-only beta

That's it.

## Without Docker

Run the dual-app Flask server directly:

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

pip install -r requirements-rag.txt

# Start your own Qdrant somewhere and set QDRANT_URL in .env:
docker run -p 6333:6333 -p 6334:6334 qdrant/qdrant
# or `make qdrant-up`

python english-v1-rag/index_english.py    # one-time
python english-v1-rag/app.py              # port 5002 by default
```

`scripts/rag/app.py` is the full-corpus-only variant on port 5001 if you only want the main UI.

## Verifying the corpus

The corpus file is **not** in git (it's ~170 MB). After cloning you have two options:

1. Build it from sources (~10 minutes — see the "Rebuilding the corpus" section in [README.md](README.md)).
2. Copy `final/verses_enriched.json` over from another checkout if you already have one.

Quick sanity check:

```bash
python -c "import json; v=json.load(open('final/verses_enriched.json', encoding='utf-8')); print(f'{len(v):,} verses')"
```

Expected output: `118,358 verses`. Anything materially different means the parser misfired — check `scripts/parse_all_scriptures.py` ran end-to-end.

## Common issues

**`UnicodeEncodeError: 'charmap' codec` on Windows.** The parser prints emoji during progress reporting; cmd/PowerShell uses cp1252 by default. Fix:

```powershell
$env:PYTHONUTF8 = "1"
```

Set this in your shell profile to make it permanent.

**`final/verses_enriched.json` not found.** You haven't built the corpus yet. See "Rebuilding the corpus" in [README.md](README.md) — `python scripts/parse_all_scriptures.py` is the modern entry point.

**Qdrant connection refused.** Confirm `QDRANT_URL` in `.env` points to a reachable instance. Default in Docker is `http://qdrant:6333` (container DNS); for local dev outside Docker, use `http://localhost:6333`.

**Embedding errors / `403` from Gemini or Cohere.** `GEMINI_API_KEY` is required for the full corpus. `COHERE_API_KEY` is still required for the English beta.

**`/api/query` returns 401.** Either set `RAG_API_KEY` and pass it as the `X-API-Key` header, or set `SESSION_PASSWORD` and log in through the UI. With neither set, the API is open from any same-origin request (the CSRF guard still applies).

## Next steps

- Read the architecture overview in [README.md](README.md).
- Deploy the Flask app to Vercel with [docs/deploy-vercel.md](docs/deploy-vercel.md).
- Customize prompts in `scripts/rag/prompt_templates.py` and `english-v1-rag/prompt_templates.py`.
- For the parallel English-only RAG (smaller corpus, fits in a free Qdrant tier), see [english-v1-rag/README.md](english-v1-rag/README.md).
