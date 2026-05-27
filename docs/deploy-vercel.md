# Deploying on Vercel

This deploys the Flask web app to Vercel as one Python Function. It does not
run Qdrant or indexing on Vercel.

## Architecture

- `app.py` is the Vercel WSGI entrypoint. It imports the existing dual app, so
  `/` serves the full Sanskrit-first corpus and `/beta` serves the English beta.
- `vercel.json` sets a 300 second function duration and excludes local corpora,
  test data, Qdrant storage, and agent/runtime scratch folders from the bundle.
- `.vercelignore` prevents local secrets and large data directories from being
  uploaded by the Vercel CLI.
- Qdrant must be external, for example Qdrant Cloud. Do not set `QDRANT_URL` to
  `localhost` on Vercel.

Vercel's Flask docs say a top-level `app.py` with an `app` object is enough for
framework detection, and their Python runtime installs dependencies from root
`requirements.txt`. The Python function bundle has a 500 MB uncompressed limit,
so keep runtime dependencies and uploaded files tight.

## Required Environment Variables

Set these in Vercel project settings or with `vercel env add`:

| Variable | Value |
|---|---|
| `GEMINI_API_KEY` | Required for full-corpus Gemini query embeddings |
| `ANTHROPIC_API_KEY` | Required for default answer generation |
| `COHERE_API_KEY` | Required for `/beta`, which is still indexed on Cohere |
| `QDRANT_URL` | External Qdrant HTTPS endpoint |
| `QDRANT_API_KEY` | Required if using Qdrant Cloud |
| `FLASK_SECRET_KEY` | Stable random secret for sessions |
| `SESSION_COOKIE_SECURE` | `1` in production |
| `EMBEDDING_PROVIDER` | `gemini` unless overriding defaults |
| `EMBEDDING_DIMS` | `1536` unless overriding defaults |

Optional:

| Variable | Use |
|---|---|
| `RAG_WARMUP` | Defaults off on Vercel. Set `1` only if cold-start warmup cost is acceptable. |
| `CORS_ORIGINS` | Set to your Vercel origin if calling from another frontend. |
| `RAG_API_KEY` | Protect raw API calls from non-session clients. |
| `AUTH_REQUIRED` | Leave unset on Vercel unless persistent auth storage is added. |

## Auth Storage Warning

The current auth backend uses SQLite. On Vercel it falls back to a temp-file DB
so the app can boot, but registration, Google OAuth users, and saved chat history
are not durable across serverless instances or cold starts.

Use guest mode or API-key protection for Vercel. Add a real external database
before enabling production user accounts there.

## Deploy Steps

1. Provision external Qdrant and load the already-indexed collections:
   - Full corpus: `hindu_scriptures`, 1536-dimensional dense vectors.
   - English beta: `hindu_scriptures_english`, 1024-dimensional dense vectors.
2. Add the environment variables above in Vercel.
3. Connect the GitHub repo in Vercel, or deploy with:

```bash
npm i -g vercel
vercel link
vercel --prod
```

4. Smoke test:

```bash
curl https://YOUR_DOMAIN/api/health
curl https://YOUR_DOMAIN/beta/api/health
```

Then query the UI at `https://YOUR_DOMAIN/` and `https://YOUR_DOMAIN/beta`.

## Operational Notes

- Do not run indexing from Vercel. Run indexing locally or from a worker machine
  that can reach Qdrant.
- `final/metadata.json` is git-ignored and excluded from the Vercel bundle. The
  source filter dropdown can be empty without it; retrieval still uses Qdrant.
- Flask serves the existing static asset folders inside the function bundle. For
  CDN-served assets, move them into `public/` and update templates later.
- Keep `requirements.txt` runtime-only. Data pipeline dependencies live in
  `requirements-pipeline.txt`.
