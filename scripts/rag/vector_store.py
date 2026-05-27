"""Qdrant vector store with dense embeddings + sparse BM25 vectors.

Uses Qdrant server (Docker) when QDRANT_URL is set, else runs in-process local storage.
"""

import hashlib
import os

from config import RAGConfig
from qdrant_client import QdrantClient, models
from qdrant_client.models import (
    Distance,
    PointStruct,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)


def _stable_id(point_id: str) -> int:
    """Deterministic string → int64 hash using SHA-256.

    Python's built-in hash() is randomized per process (PYTHONHASHSEED),
    so the same string produces different IDs across runs, breaking --resume.
    """
    return int(hashlib.sha256(point_id.encode()).hexdigest()[:15], 16)


class QdrantStore:
    """Qdrant wrapper supporting dense + sparse (BM25) hybrid search."""

    def __init__(self, config: RAGConfig | None = None):
        if config is None:
            config = RAGConfig()
        self.config = config
        self.collection = config.qdrant_collection

        if config.qdrant_url:
            self.client = QdrantClient(
                url=config.qdrant_url,
                api_key=config.qdrant_api_key,
                timeout=config.qdrant_timeout_sec,
            )
        else:
            if os.environ.get("VERCEL"):
                raise RuntimeError(
                    "QDRANT_URL is required on Vercel. "
                    "Use Qdrant Cloud or another external Qdrant server; "
                    "embedded qdrant_data is local-only."
                )
            # In-process Qdrant (persists to disk)
            config.qdrant_path.mkdir(parents=True, exist_ok=True)
            self.client = QdrantClient(path=str(config.qdrant_path))

        # Lazy-loaded BM25 encoder
        self._bm25_encoder = None

    @property
    def bm25_encoder(self):
        """Lazy-load fastembed BM25 encoder."""
        if self._bm25_encoder is None:
            from fastembed import SparseTextEmbedding

            self._bm25_encoder = SparseTextEmbedding(model_name="Qdrant/bm25")
        return self._bm25_encoder

    def create_collection(self):
        """Create the collection with dense + sparse vector config."""
        # Delete if exists
        if self.client.collection_exists(self.collection):
            self.client.delete_collection(self.collection)

        self.client.create_collection(
            collection_name=self.collection,
            vectors_config={
                "dense": VectorParams(
                    size=self.config.embedding_dims,
                    distance=Distance.COSINE,
                ),
            },
            sparse_vectors_config={
                "sparse": SparseVectorParams(),
            },
        )

        # Create payload indexes for efficient filtered search
        for field_name in [
            "source_text",
            "chunk_type",
            "category",
            "tradition",
            "school",
            "author",
            "verse_id",
            "schools",
        ]:
            self.client.create_payload_index(
                collection_name=self.collection,
                field_name=field_name,
                field_schema=models.PayloadSchemaType.KEYWORD,
            )

        # Integer indexes for range queries (context expansion / story retrieval)
        for field_name in ["verse_num", "chapter"]:
            self.client.create_payload_index(
                collection_name=self.collection,
                field_name=field_name,
                field_schema=models.PayloadSchemaType.INTEGER,
            )

    def collection_exists(self) -> bool:
        return self.client.collection_exists(self.collection)

    def count(self) -> int:
        info = self.client.get_collection(self.collection)
        return info.points_count

    def count_exact(self, query_filter: models.Filter | None = None) -> int:
        """Return an exact point count, optionally filtered by payload."""
        result = self.client.count(
            collection_name=self.collection,
            count_filter=query_filter,
            exact=True,
        )
        return result.count

    def count_by_chunk_type(self, chunk_type: str) -> int:
        """Return exact count for verse/commentary chunks."""
        return self.count_exact(
            models.Filter(
                must=[
                    models.FieldCondition(
                        key="chunk_type",
                        match=models.MatchValue(value=chunk_type),
                    )
                ]
            )
        )

    def upsert_batch(
        self,
        ids: list[str],
        dense_vectors: list[list[float]],
        texts_for_bm25: list[str],
        payloads: list[dict],
    ):
        """Insert a batch of points with dense + sparse vectors."""
        # Generate sparse vectors
        sparse_embeddings = list(self.bm25_encoder.embed(texts_for_bm25))

        points = []
        for i, point_id in enumerate(ids):
            sparse_emb = sparse_embeddings[i]
            points.append(
                PointStruct(
                    id=_stable_id(point_id),  # Deterministic int64 from SHA-256
                    vector={
                        "dense": dense_vectors[i],
                        "sparse": SparseVector(
                            indices=sparse_emb.indices.tolist(),
                            values=sparse_emb.values.tolist(),
                        ),
                    },
                    payload={**payloads[i], "_point_id": point_id},
                )
            )

        self.client.upsert(
            collection_name=self.collection,
            points=points,
        )

    def search_dense(
        self,
        query_vector: list[float],
        limit: int = 10,
        query_filter: models.Filter | None = None,
    ) -> list[models.ScoredPoint]:
        """Dense-only search."""
        return self.client.query_points(
            collection_name=self.collection,
            query=query_vector,
            using="dense",
            limit=limit,
            query_filter=query_filter,
            with_payload=True,
        ).points

    def search_sparse(
        self,
        query_text: str,
        limit: int = 10,
        query_filter: models.Filter | None = None,
    ) -> list[models.ScoredPoint]:
        """Sparse BM25 search (exact term matching)."""
        sparse_emb = list(self.bm25_encoder.query_embed(query_text))[0]
        sparse_vec = SparseVector(
            indices=sparse_emb.indices.tolist(),
            values=sparse_emb.values.tolist(),
        )
        return self.client.query_points(
            collection_name=self.collection,
            query=sparse_vec,
            using="sparse",
            limit=limit,
            query_filter=query_filter,
            with_payload=True,
        ).points

    def search_hybrid(
        self,
        query_vector: list[float],
        query_text: str,
        limit: int = 10,
        query_filter: models.Filter | None = None,
    ) -> list[models.ScoredPoint]:
        """Hybrid search using Qdrant's built-in prefetch + RRF."""
        sparse_emb = list(self.bm25_encoder.query_embed(query_text))[0]
        sparse_vec = SparseVector(
            indices=sparse_emb.indices.tolist(),
            values=sparse_emb.values.tolist(),
        )

        return self.client.query_points(
            collection_name=self.collection,
            prefetch=[
                models.Prefetch(
                    query=query_vector,
                    using="dense",
                    limit=limit * 2,
                    filter=query_filter,
                ),
                models.Prefetch(
                    query=sparse_vec,
                    using="sparse",
                    limit=limit * 2,
                    filter=query_filter,
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=limit,
            with_payload=True,
        ).points
