"""Embedding wrapper for Cohere embed-multilingual-v3.0.

Handles batching (max 96 per call), proactive rate-limit throttling, and retries.

Cohere Embed API limit: 2,000 inputs/min (trial and production).
At 96 inputs/batch that's ~20 batches/min → need ~3s between batches.
Default delay is 4s (conservative) and is configurable via COHERE_BATCH_DELAY_SEC.
"""

import time

import cohere
import cohere.core
from config import RAGConfig


class CohereEmbedder:
    """Cohere embed-multilingual-v3.0 wrapper (1024 dims, handles Devanagari)."""

    BATCH_SIZE = 96  # Cohere API limit per call

    def __init__(self, config: RAGConfig | None = None):
        if config is None:
            config = RAGConfig()
        self.config = config
        self.client = cohere.ClientV2(api_key=config.cohere_api_key)
        self.model = config.cohere_model
        self.dims = config.cohere_dims
        self.batch_delay = config.cohere_batch_delay_sec

    def _embed_with_retry(
        self, texts: list[str], input_type: str, max_retries: int = 8
    ) -> list[list[float]]:
        """Embed with exponential backoff on rate limits.

        Catches both TooManyRequestsError and generic ApiError with status 429.
        Uses Retry-After header when available, otherwise exponential backoff.
        """
        for attempt in range(max_retries):
            try:
                response = self.client.embed(
                    texts=texts,
                    model=self.model,
                    input_type=input_type,
                    embedding_types=["float"],
                )
                return [list(e) for e in response.embeddings.float_]
            except (cohere.errors.TooManyRequestsError, cohere.core.ApiError) as e:
                # Only handle 429 for generic ApiError
                if isinstance(e, cohere.core.ApiError) and getattr(e, "status_code", None) != 429:
                    raise

                # Log the full error body for debugging
                error_body = getattr(e, "body", None)
                error_headers = getattr(e, "headers", None)

                # Try to use Retry-After header if provided
                wait = None
                if error_headers:
                    retry_after = error_headers.get("retry-after") or error_headers.get(
                        "Retry-After"
                    )
                    if retry_after:
                        try:
                            wait = int(retry_after)
                        except (ValueError, TypeError):
                            pass

                # Fall back to exponential backoff: 15, 30, 60, 120, 240, 480...
                if wait is None:
                    wait = min(2**attempt * 15, 600)

                print(
                    f"  Rate limited (429). Waiting {wait}s (attempt {attempt + 1}/{max_retries})"
                )
                if error_body:
                    print(f"    Error detail: {error_body}")
                time.sleep(wait)

        raise RuntimeError(
            f"Cohere rate limit: max retries ({max_retries}) exceeded. "
            f"Try increasing COHERE_BATCH_DELAY_SEC (currently {self.batch_delay}s) "
            f"or use --resume to continue later."
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of documents. Batches automatically with proactive rate limiting."""
        all_embeddings = []

        for i in range(0, len(texts), self.BATCH_SIZE):
            batch = texts[i : i + self.BATCH_SIZE]
            embeddings = self._embed_with_retry(batch, "search_document")
            all_embeddings.extend(embeddings)

            # Proactive throttle: sleep between batches to stay under rate limit
            if i + self.BATCH_SIZE < len(texts) and self.batch_delay > 0:
                time.sleep(self.batch_delay)

        return all_embeddings

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query."""
        embeddings = self._embed_with_retry([text], "search_query")
        return embeddings[0]
