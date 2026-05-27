"""Central configuration for the Hindu Scriptures RAG system."""

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from dotenv import load_dotenv

# Project root: two levels up from this file (scripts/rag/config.py -> project root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Load .env from project root before any os.environ reads
load_dotenv(PROJECT_ROOT / ".env")


class LLMProvider(Enum):
    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class EmbeddingProvider(Enum):
    SENTENCE_TRANSFORMERS = "sentence_transformers"
    OPENAI = "openai"
    COHERE = "cohere"
    GEMINI = "gemini"


def _embedding_provider_from_env() -> EmbeddingProvider:
    raw = os.environ.get("EMBEDDING_PROVIDER", "gemini").strip().lower()
    for provider in EmbeddingProvider:
        if provider.value == raw:
            return provider
    return EmbeddingProvider.GEMINI


def _embedding_dims_from_env() -> int:
    raw = os.environ.get("EMBEDDING_DIMS")
    if raw:
        return int(raw)

    provider = _embedding_provider_from_env()
    if provider == EmbeddingProvider.COHERE:
        return 1024
    return 1536


def _gemini_api_key_from_env() -> str:
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""


@dataclass
class RAGConfig:
    # --- Provider selection ---
    llm_provider: LLMProvider = LLMProvider.ANTHROPIC
    embedding_provider: EmbeddingProvider = field(default_factory=_embedding_provider_from_env)

    # --- LLM models ---
    ollama_model: str = "llama3.1:8b"
    ollama_base_url: str = "http://localhost:11434"
    openai_model: str = "gpt-4o-mini"
    anthropic_model: str = "claude-sonnet-4-5-20250929"
    # Smaller model for Sanskrit gloss / auxiliary text (used before main generation).
    anthropic_haiku_model: str = "claude-haiku-4-5-20251001"

    # --- Embedding models ---
    sentence_transformer_model: str = "all-MiniLM-L6-v2"
    openai_embedding_model: str = "text-embedding-3-small"

    # --- Embeddings (shared) ---
    embedding_dims: int = field(default_factory=_embedding_dims_from_env)
    embedding_batch_size: int = field(
        default_factory=lambda: int(os.environ.get("EMBEDDING_BATCH_SIZE", "50"))
    )

    # --- Gemini (default for Sanskrit-first corpus) ---
    gemini_api_key: str = field(default_factory=_gemini_api_key_from_env)
    gemini_model: str = field(
        default_factory=lambda: os.environ.get("GEMINI_EMBEDDING_MODEL", "gemini-embedding-2")
    )
    gemini_batch_delay_sec: float = field(
        default_factory=lambda: float(os.environ.get("GEMINI_BATCH_DELAY_SEC", "1"))
    )

    # --- Cohere (legacy / English beta fallback) ---
    cohere_api_key: str = field(default_factory=lambda: os.environ.get("COHERE_API_KEY", ""))
    cohere_model: str = field(
        default_factory=lambda: os.environ.get("COHERE_EMBEDDING_MODEL", "embed-multilingual-v3.0")
    )
    cohere_batch_delay_sec: float = field(
        default_factory=lambda: float(os.environ.get("COHERE_BATCH_DELAY_SEC", "4"))
    )  # Delay between embed batches to stay under 2,000 inputs/min

    @property
    def cohere_dims(self) -> int:
        """Backward-compatible alias for Qdrant dense vector size."""
        return self.embedding_dims

    @property
    def embedding_model(self) -> str:
        if self.embedding_provider == EmbeddingProvider.GEMINI:
            return self.gemini_model
        if self.embedding_provider == EmbeddingProvider.COHERE:
            return self.cohere_model
        if self.embedding_provider == EmbeddingProvider.OPENAI:
            return self.openai_embedding_model
        if self.embedding_provider == EmbeddingProvider.SENTENCE_TRANSFORMERS:
            return self.sentence_transformer_model
        raise ValueError(f"Unsupported embedding provider: {self.embedding_provider}")

    # --- Qdrant ---
    # When set (e.g. "http://localhost:6333"), use Qdrant server (Docker). Else use local embedded storage.
    qdrant_url: str | None = field(default_factory=lambda: os.environ.get("QDRANT_URL") or None)
    qdrant_api_key: str | None = field(
        default_factory=lambda: os.environ.get("QDRANT_API_KEY") or None
    )
    qdrant_path: Path = field(default_factory=lambda: PROJECT_ROOT / "qdrant_data")
    qdrant_collection: str = field(
        default_factory=lambda: os.environ.get("RAG_COLLECTION", "hindu_scriptures")
    )
    # HTTP read timeout for the Qdrant server client. The default is short and a
    # cold-start create_collection (segment alloc + payload indexes + fsync) can
    # exceed it; large upsert batches can too.
    qdrant_timeout_sec: float = field(
        default_factory=lambda: float(os.environ.get("QDRANT_TIMEOUT_SEC", "120"))
    )

    # --- API keys (from environment) ---
    openai_api_key: str = field(default_factory=lambda: os.environ.get("OPENAI_API_KEY", ""))
    anthropic_api_key: str = field(default_factory=lambda: os.environ.get("ANTHROPIC_API_KEY", ""))

    # --- Paths ---
    verses_file: Path = field(
        default_factory=lambda: PROJECT_ROOT / "final" / "verses_enriched.json"
    )

    # --- Retrieval settings ---
    top_k: int = 8
    batch_size: int = 5000

    # --- LLM parameters ---
    temperature: float = 0.3
    max_tokens: int = 4096

    # --- Agent settings ---
    max_agent_turns: int = 10
    conversation_window: int = 10

    # --- API timeouts (prevent indefinite hangs) ---
    api_timeout_sec: float = 90
    # --- API / content bounds (abuse and prompt-injection DoS) ---
    max_question_len: int = field(
        default_factory=lambda: int(os.environ.get("RAG_MAX_QUESTION_LEN", "8000"))
    )
    max_client_history_messages: int = field(
        default_factory=lambda: int(os.environ.get("RAG_MAX_CLIENT_HISTORY_MSGS", "20"))
    )

    # --- LLM / moderation (see moderation.py) ---
    llm_moderation_enabled: bool = field(
        default_factory=lambda: os.environ.get("RAG_LLM_MODERATION", "").lower() in ("1", "true", "yes")
    )
    openai_moderation_enabled: bool = field(
        default_factory=lambda: os.environ.get("RAG_OPENAI_MODERATION", "").lower() in ("1", "true", "yes")
    )
