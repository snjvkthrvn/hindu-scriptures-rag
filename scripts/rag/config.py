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



@dataclass
class RAGConfig:
    # --- Provider selection ---
    llm_provider: LLMProvider = LLMProvider.ANTHROPIC
    embedding_provider: EmbeddingProvider = EmbeddingProvider.COHERE

    # --- LLM models ---
    ollama_model: str = "llama3.1:8b"
    ollama_base_url: str = "http://localhost:11434"
    openai_model: str = "gpt-4o-mini"
    anthropic_model: str = "claude-sonnet-4-5-20250929"

    # --- Embedding models ---
    sentence_transformer_model: str = "all-MiniLM-L6-v2"
    openai_embedding_model: str = "text-embedding-3-small"

    # --- Cohere ---
    cohere_api_key: str = field(default_factory=lambda: os.environ.get("COHERE_API_KEY", ""))
    cohere_model: str = "embed-multilingual-v3.0"
    cohere_dims: int = 1024
    cohere_batch_delay_sec: float = field(
        default_factory=lambda: float(os.environ.get("COHERE_BATCH_DELAY_SEC", "4"))
    )  # Delay between embed batches to stay under 2,000 inputs/min

    # --- Qdrant ---
    qdrant_path: Path = field(default_factory=lambda: PROJECT_ROOT / "qdrant_data")
    qdrant_collection: str = "hindu_scriptures"

    # --- API keys (from environment) ---
    openai_api_key: str = field(default_factory=lambda: os.environ.get("OPENAI_API_KEY", ""))
    anthropic_api_key: str = field(default_factory=lambda: os.environ.get("ANTHROPIC_API_KEY", ""))

    # --- Paths ---
    verses_file: Path = field(default_factory=lambda: PROJECT_ROOT / "final" / "verses_enriched.json")

    # --- Retrieval settings ---
    top_k: int = 8
    batch_size: int = 5000

    # --- LLM parameters ---
    temperature: float = 0.3
    max_tokens: int = 4096

    # --- Agent settings ---
    max_agent_turns: int = 10
    conversation_window: int = 10
