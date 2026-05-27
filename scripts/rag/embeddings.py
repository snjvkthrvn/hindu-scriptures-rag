"""Embedding providers for dense retrieval (Gemini default, Cohere legacy)."""

from __future__ import annotations

import time
from typing import Protocol

import cohere
import cohere.core
from config import RAGConfig, EmbeddingProvider


def format_gemini_query(text: str) -> str:
    """Gemini Embedding 2 asymmetric retrieval prefix for queries."""
    return f"task: search result | query: {text.strip()}"


def format_gemini_document(text: str, title: str | None = None) -> str:
    """Gemini Embedding 2 asymmetric retrieval prefix for corpus documents."""
    clean_title = (title or "").strip() or "none"
    return f"title: {clean_title} | text: {text.strip()}"


class Embedder(Protocol):
    model: str
    dims: int
    batch_size: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class GeminiEmbedder:
    """Gemini Embedding 2 wrapper (default 1536 dims, 8192-token context)."""

    def __init__(self, config: RAGConfig | None = None):
        if config is None:
            config = RAGConfig()
        if not config.gemini_api_key:
            raise ValueError(
                "GEMINI_API_KEY (or GOOGLE_API_KEY) is required when EMBEDDING_PROVIDER=gemini"
            )

        from google import genai
        from google.genai import types

        self.config = config
        self.client = genai.Client(api_key=config.gemini_api_key)
        self.types = types
        self.model = config.gemini_model
        self.dims = config.embedding_dims
        self.batch_size = config.embedding_batch_size
        self.batch_delay = config.gemini_batch_delay_sec

    def _embed_batch(self, texts: list[str], *, as_query: bool) -> list[list[float]]:
        from google.genai import errors

        contents = []
        for text in texts:
            formatted = (
                format_gemini_query(text)
                if as_query
                else format_gemini_document(text)
            )
            contents.append(
                self.types.Content(parts=[self.types.Part.from_text(text=formatted)])
            )

        config = self.types.EmbedContentConfig(output_dimensionality=self.dims)
        max_retries = 8

        for attempt in range(max_retries):
            try:
                result = self.client.models.embed_content(
                    model=self.model,
                    contents=contents,
                    config=config,
                )
                embeddings = [list(item.values) for item in result.embeddings]
                if len(embeddings) != len(texts):
                    raise RuntimeError(
                        "Gemini Embedding 2 returned "
                        f"{len(embeddings)} embedding(s) for {len(texts)} input(s). "
                        "Each document must be sent as a separate Content object; "
                        "otherwise the API may aggregate the batch into one vector."
                    )
                for idx, embedding in enumerate(embeddings):
                    if len(embedding) != self.dims:
                        raise RuntimeError(
                            "Gemini Embedding 2 returned an unexpected vector size "
                            f"for item {idx}: {len(embedding)} != {self.dims}"
                        )
                return embeddings
            except (errors.ClientError, errors.ServerError) as e:
                status = getattr(e, "code", None) or getattr(e, "status_code", None)
                if status not in (429, 500, 503):
                    raise
                wait = min(2**attempt * 5, 120)
                print(
                    f"  Gemini rate limited ({status}). Waiting {wait}s "
                    f"(attempt {attempt + 1}/{max_retries})"
                )
                time.sleep(wait)

        raise RuntimeError(
            f"Gemini rate limit: max retries ({max_retries}) exceeded. "
            f"Try increasing GEMINI_BATCH_DELAY_SEC (currently {self.batch_delay}s)."
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            all_embeddings.extend(self._embed_batch(batch, as_query=False))

            if i + self.batch_size < len(texts) and self.batch_delay > 0:
                time.sleep(self.batch_delay)

        return all_embeddings

    def embed_query(self, text: str) -> list[float]:
        return self._embed_batch([text], as_query=True)[0]


class CohereEmbedder:
    """Cohere embed-multilingual-v3.0 wrapper (legacy English beta / fallback)."""

    BATCH_SIZE = 96  # Cohere API limit per call

    def __init__(self, config: RAGConfig | None = None):
        if config is None:
            config = RAGConfig()
        if not config.cohere_api_key:
            raise ValueError("COHERE_API_KEY is required when EMBEDDING_PROVIDER=cohere")

        self.config = config
        self.client = cohere.ClientV2(api_key=config.cohere_api_key)
        self.model = config.cohere_model
        self.dims = config.embedding_dims
        self.batch_size = min(config.embedding_batch_size, self.BATCH_SIZE)
        self.batch_delay = config.cohere_batch_delay_sec

    def _embed_with_retry(
        self, texts: list[str], input_type: str, max_retries: int = 8
    ) -> list[list[float]]:
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
                if isinstance(e, cohere.core.ApiError) and getattr(e, "status_code", None) != 429:
                    raise

                error_body = getattr(e, "body", None)
                error_headers = getattr(e, "headers", None)

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
        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            embeddings = self._embed_with_retry(batch, "search_document")
            all_embeddings.extend(embeddings)

            if i + self.batch_size < len(texts) and self.batch_delay > 0:
                time.sleep(self.batch_delay)

        return all_embeddings

    def embed_query(self, text: str) -> list[float]:
        embeddings = self._embed_with_retry([text], "search_query")
        return embeddings[0]


def get_embedder(config: RAGConfig | None = None) -> Embedder:
    if config is None:
        config = RAGConfig()
    if config.embedding_provider == EmbeddingProvider.GEMINI:
        return GeminiEmbedder(config)
    if config.embedding_provider == EmbeddingProvider.COHERE:
        return CohereEmbedder(config)
    raise ValueError(f"Unsupported embedding provider: {config.embedding_provider}")
