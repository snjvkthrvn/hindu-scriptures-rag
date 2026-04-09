"""Hybrid search over Qdrant: dense (Cohere) + sparse (BM25) with metadata filters.

Returns structured results ready for the LLM context window.
"""

from qdrant_client import models

from config import RAGConfig
from embeddings import CohereEmbedder
from vector_store import QdrantStore

# Module-level caches keyed by config values — avoid re-creating clients on
# every search call while supporting multiple collections / models.
# The BM25 encoder in QdrantStore is especially expensive to reload.
_embedder_cache: dict[str, CohereEmbedder] = {}
_store_cache: dict[str, QdrantStore] = {}


def _get_embedder(config: RAGConfig) -> CohereEmbedder:
    key = config.cohere_model
    if key not in _embedder_cache:
        _embedder_cache[key] = CohereEmbedder(config)
    return _embedder_cache[key]


def _get_store(config: RAGConfig) -> QdrantStore:
    key = config.qdrant_collection
    if key not in _store_cache:
        store = QdrantStore(config)
        # Eagerly load BM25 so first hybrid search isn't slow
        _ = store.bm25_encoder
        _store_cache[key] = store
    return _store_cache[key]


def warmup(config: RAGConfig | None = None):
    """Load all RAG components (embedder, Qdrant, BM25) with a minimal search.

    Call at startup to avoid slow first user request.
    """
    if config is None:
        config = RAGConfig()
    try:
        search("dharma", config=config, top_k=1)
    except Exception:
        pass  # Don't fail startup if warmup errors (e.g. no API key, empty collection)


def _build_filter(filters: dict | None) -> models.Filter | None:
    """Convert a flat filter dict into a Qdrant Filter."""
    if not filters:
        return None

    conditions = []
    for key, value in filters.items():
        if value is None or value == "":
            continue
        conditions.append(
            models.FieldCondition(
                key=key,
                match=models.MatchValue(value=value),
            )
        )

    if not conditions:
        return None
    return models.Filter(must=conditions)


def _format_result(point) -> dict:
    """Convert a Qdrant ScoredPoint into a clean result dict."""
    payload = point.payload or {}
    return {
        "id": payload.get("_point_id", str(point.id)),
        "score": point.score,
        "chunk_type": payload.get("chunk_type", "verse"),
        "verse_id": payload.get("verse_id", ""),
        "source_text": payload.get("source_text", ""),
        "chapter": payload.get("chapter") or None,
        "chapter_name": payload.get("chapter_name", ""),
        "verse_num": payload.get("verse_num") or None,
        "section": payload.get("section", ""),
        "category": payload.get("category", ""),
        "tradition": payload.get("tradition", ""),
        "school": payload.get("school", ""),
        "themes": payload.get("themes", ""),
        "schools": payload.get("schools", ""),
        "sanskrit": payload.get("sanskrit", ""),
        "transliteration": payload.get("transliteration", ""),
        "translation": payload.get("translation", ""),
        # Commentary-specific
        "author": payload.get("author", ""),
        "commentary_text": payload.get("commentary_text", ""),
    }


def search(
    query: str,
    config: RAGConfig | None = None,
    filters: dict | None = None,
    top_k: int | None = None,
) -> list[dict]:
    """Hybrid search: dense (Cohere) + sparse (BM25) with RRF fusion.

    Args:
        query: Natural language question.
        config: RAG configuration.
        filters: Optional metadata filters, e.g. {"source_text": "Bhagavad Gita"}.
        top_k: Number of results to return.

    Returns:
        List of result dicts sorted by relevance.
    """
    if config is None:
        config = RAGConfig()
    if top_k is None:
        top_k = config.top_k

    embedder = _get_embedder(config)
    store = _get_store(config)
    qdrant_filter = _build_filter(filters)

    # Embed the query
    query_vector = embedder.embed_query(query)

    # Hybrid search with RRF
    points = store.search_hybrid(
        query_vector=query_vector,
        query_text=query,
        limit=top_k,
        query_filter=qdrant_filter,
    )

    return [_format_result(p) for p in points]


def search_with_context_expansion(
    query: str,
    config: RAGConfig | None = None,
    filters: dict | None = None,
    top_k: int | None = None,
    context_window: int = 10,
) -> list[dict]:
    """Hybrid search + expand around each hit to capture full narrative sections.

    For story-type queries (e.g. "Tell me the story of Nachiketa"), the normal
    search returns scattered individual verses. This function:
      1. Runs normal hybrid search to find seed hits.
      2. For each hit, fetches neighboring verses from the same source_text +
         chapter within ±context_window of the hit's verse_num.
      3. Deduplicates and sorts into reading order.

    Args:
        query: Natural language question.
        config: RAG configuration.
        filters: Optional metadata filters.
        top_k: Number of seed results for the initial search.
        context_window: How many verses before/after each hit to include.

    Returns:
        Expanded list of result dicts sorted by (source_text, chapter, verse_num).
    """
    if config is None:
        config = RAGConfig()
    if top_k is None:
        top_k = min(config.top_k, 5)  # fewer seeds → wider expansion

    # Step 1: seed search (existing hybrid logic)
    seed_results = search(query, config=config, filters=filters, top_k=top_k)
    if not seed_results:
        return []

    store = _get_store(config)

    # Step 2: expand around each hit
    seen_ids: set[str] = set()
    expanded: list[dict] = []

    for hit in seed_results:
        source = hit.get("source_text", "")
        chapter = hit.get("chapter")
        verse_num = hit.get("verse_num")

        if not source or verse_num is None:
            # Can't expand — keep the hit as-is
            if hit["id"] not in seen_ids:
                seen_ids.add(hit["id"])
                expanded.append(hit)
            continue

        # Build filter: same source_text, same chapter, verse_num in range
        lo = max(1, verse_num - context_window)
        hi = verse_num + context_window

        conditions = [
            models.FieldCondition(
                key="source_text",
                match=models.MatchValue(value=source),
            ),
            models.FieldCondition(
                key="chunk_type",
                match=models.MatchValue(value="verse"),
            ),
            models.FieldCondition(
                key="verse_num",
                range=models.Range(gte=lo, lte=hi),
            ),
        ]
        if chapter is not None:
            conditions.append(
                models.FieldCondition(
                    key="chapter",
                    match=models.MatchValue(value=chapter),
                )
            )

        neighbors, _ = store.client.scroll(
            collection_name=store.collection,
            scroll_filter=models.Filter(must=conditions),
            limit=context_window * 2 + 1,
            with_payload=True,
        )

        for pt in neighbors:
            r = _format_result(pt)
            if r["id"] not in seen_ids:
                seen_ids.add(r["id"])
                expanded.append(r)

    # Step 3: sort into reading order
    expanded.sort(key=lambda r: (
        r.get("source_text", ""),
        r.get("chapter") or 0,
        r.get("verse_num") or 0,
    ))

    return expanded


def search_by_verse_id(
    verse_id: str,
    config: RAGConfig | None = None,
) -> list[dict]:
    """Retrieve a specific verse and all its commentaries by verse_id.

    Returns:
        List of result dicts (verse + commentary chunks).
    """
    if config is None:
        config = RAGConfig()

    store = _get_store(config)
    qdrant_filter = models.Filter(
        must=[
            models.FieldCondition(
                key="verse_id",
                match=models.MatchValue(value=verse_id),
            )
        ]
    )

    # Search for all chunks with this verse_id (verse + commentaries)
    # Use a dense vector of zeros just to satisfy the API — filter does the work
    points = store.client.scroll(
        collection_name=store.collection,
        scroll_filter=qdrant_filter,
        limit=50,
        with_payload=True,
    )[0]

    return [_format_result(p) for p in points]


def format_context(results: list[dict]) -> str:
    """Format search results into a context string for the LLM."""
    parts = []
    for i, r in enumerate(results, 1):
        if r["chunk_type"] == "verse":
            header = f"[{r['source_text']}"
            if r["chapter_name"]:
                header += f" - {r['chapter_name']}"
            if r["verse_num"]:
                header += f", Verse {r['verse_num']}"
            header += "]"

            lines = [f"Passage {i}: {header}"]
            if r["sanskrit"]:
                lines.append(f"Sanskrit: {r['sanskrit']}")
            if r["transliteration"]:
                lines.append(f"Transliteration: {r['transliteration']}")
            if r["translation"]:
                lines.append(f"Translation: {r['translation']}")
            parts.append("\n".join(lines))

        elif r["chunk_type"] == "commentary":
            lines = [
                f"Passage {i}: [Commentary on {r['source_text']} {r['chapter']}.{r['verse_num']}]",
                f"Author: {r['author']} ({r.get('school') or r.get('tradition', '')})",
                f"Commentary: {r['commentary_text'][:1500]}",
            ]
            parts.append("\n".join(lines))

    return "\n\n".join(parts)
