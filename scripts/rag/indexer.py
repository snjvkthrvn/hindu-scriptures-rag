"""One-time indexer: chunk verses → embed via Cohere → insert into Qdrant.

Verse-native chunking strategy:
  - Verse chunk: embed Sanskrit + transliteration + translation, store full verse
  - Commentary chunk: one per commentary entry, linked to parent verse_id

Supports --resume to continue from where a previous run was interrupted.

Usage:
    python scripts/rag/indexer.py            # fresh index
    python scripts/rag/indexer.py --resume   # continue from checkpoint
"""

import json
import sys
from pathlib import Path

from config import PROJECT_ROOT, RAGConfig
from embeddings import CohereEmbedder
from text_normalization import build_sparse_text
from tqdm import tqdm
from vector_store import QdrantStore


def _checkpoint_file(config: RAGConfig) -> Path:
    return PROJECT_ROOT / "qdrant_data" / f"_indexer_checkpoint_{config.qdrant_collection}.json"


# ── Build embeddable / payload helpers ────────────────────────────────────


def build_embeddable_text(verse: dict) -> str:
    """Build Sanskrit-first text for embedding."""
    content = verse.get("content", {})
    sanskrit = content.get("sanskrit", "").strip()
    transliteration = content.get("transliteration", "").strip()
    translation = content.get("translation", "").strip()

    primary_parts = [p for p in (sanskrit, transliteration, translation) if p]
    if not primary_parts:
        return ""

    source = verse.get("source", {})
    meta = verse.get("metadata", {})

    parts = [" ".join(primary_parts)]
    if source.get("text"):
        parts.append(f"Source: {source['text']}")
    if source.get("chapter_name"):
        parts.append(f"Chapter: {source['chapter_name']}")
    if meta.get("category"):
        parts.append(f"Category: {meta['category']}")
    if meta.get("tradition"):
        parts.append(f"Tradition: {meta['tradition']}")
    themes = meta.get("themes", [])
    if themes:
        parts.append(f"Themes: {', '.join(themes)}")

    return " | ".join(parts)


def build_verse_payload(verse: dict) -> dict:
    """Build Qdrant payload for a verse chunk."""
    source = verse.get("source", {})
    meta = verse.get("metadata", {})
    content = verse.get("content", {})

    themes = meta.get("themes", [])
    themes_str = ", ".join(str(t) for t in themes) if themes else ""

    schools = meta.get("philosophical_schools", [])
    schools_str = ", ".join(str(s) for s in schools) if schools else ""

    return {
        "chunk_type": "verse",
        "verse_id": str(verse.get("id", "")),
        "source_text": str(source.get("text", "")),
        "chapter": int(source.get("chapter") or 0),
        "chapter_name": str(source.get("chapter_name", "")),
        "verse_num": int(source.get("verse") or 0),
        "section": str(source.get("section") or ""),
        "category": str(meta.get("category", "")),
        "tradition": str(meta.get("tradition", "")),
        "themes": themes_str,
        "schools": schools_str,
        "sanskrit": content.get("sanskrit", ""),
        "transliteration": content.get("transliteration", ""),
        "translation": content.get("translation", ""),
        "has_translation": bool(content.get("translation", "").strip()),
    }


def build_commentary_payload(verse: dict, commentary: dict) -> dict:
    """Build Qdrant payload for a commentary chunk."""
    source = verse.get("source", {})

    return {
        "chunk_type": "commentary",
        "verse_id": str(verse.get("id", "")),
        "source_text": str(source.get("text", "")),
        "chapter": int(source.get("chapter") or 0),
        "chapter_name": str(source.get("chapter_name", "")),
        "verse_num": int(source.get("verse") or 0),
        "section": "",
        "category": "commentary",
        "tradition": "",
        "school": commentary.get("school", "common"),
        "themes": "",
        "schools": commentary.get("school", ""),
        "author": commentary.get("author", ""),
        "commentary_text": commentary.get("text", ""),
        "sanskrit": "",
        "transliteration": "",
        "translation": "",
        "has_translation": False,
    }


def build_commentary_embeddable(verse: dict, commentary: dict) -> str:
    """Build embeddable text for a commentary chunk."""
    source = verse.get("source", {})
    author = commentary.get("author", "Unknown")
    school = commentary.get("school", "")
    ch = source.get("chapter", "")
    v = source.get("verse", "")
    text = commentary.get("text", "")

    # Truncate very long commentaries for embedding (keep first 1000 chars)
    if len(text) > 1000:
        text = text[:1000]

    source_name = source.get("text", "unknown")
    return f"{author} ({school}) commentary on {source_name} {ch}.{v}: {text}"


# ── Checkpointing ────────────────────────────────────────────────────────


def save_checkpoint(batch_index: int, config: RAGConfig):
    cp = _checkpoint_file(config)
    cp.parent.mkdir(parents=True, exist_ok=True)
    with open(cp, "w") as f:
        json.dump({"batch_index": batch_index}, f)


def load_checkpoint(config: RAGConfig) -> int:
    cp = _checkpoint_file(config)
    if cp.exists():
        with open(cp) as f:
            return json.load(f).get("batch_index", 0)
    return 0


def clear_checkpoint(config: RAGConfig):
    cp = _checkpoint_file(config)
    if cp.exists():
        cp.unlink()


# ── Main indexing pipeline ────────────────────────────────────────────────


def index(config: RAGConfig | None = None, resume: bool = False) -> None:
    """Run the full Qdrant indexing pipeline."""
    if config is None:
        config = RAGConfig()

    # Load verses
    print(f"Loading verses from {config.verses_file}...")
    with open(config.verses_file) as f:
        verses = json.load(f)
    print(f"Loaded {len(verses):,} verses")

    # Initialize components
    print(f"Initializing Cohere embedder ({config.cohere_model})...")
    embedder = CohereEmbedder(config)

    print(f"Initializing Qdrant at {config.qdrant_path}...")
    store = QdrantStore(config)

    if not resume or not store.collection_exists():
        store.create_collection()
        clear_checkpoint(config)
        start_batch = 0
    else:
        start_batch = load_checkpoint(config)
        existing = store.count()
        print(f"Resuming from batch {start_batch} ({existing:,} points already indexed)")

    # Separate verse and commentary chunks
    verse_chunks = []  # (id, embeddable_text, bm25_text, payload)
    commentary_chunks = []

    print("Preparing chunks...")
    for verse in tqdm(verses, desc="Chunking"):
        embeddable = build_embeddable_text(verse)
        if not embeddable.strip():
            continue

        verse_id = verse.get("id", "unknown")
        payload = build_verse_payload(verse)

        # BM25 text: combine Sanskrit + transliteration + translation for term matching
        content = verse.get("content", {})
        bm25_text = build_sparse_text([
            content.get("sanskrit", ""),
            content.get("transliteration", ""),
            content.get("translation", ""),
        ])

        verse_chunks.append((verse_id, embeddable, bm25_text, payload))

        # Commentary chunks
        for ci, comm in enumerate(verse.get("commentaries", [])):
            comm_text = (comm.get("text") or "").strip()
            if not comm_text:
                continue
            comm_id = f"{verse_id}_comm_{ci}"
            comm_embeddable = build_commentary_embeddable(verse, comm)
            comm_payload = build_commentary_payload(verse, comm)
            commentary_chunks.append((comm_id, comm_embeddable, comm_text, comm_payload))

    total = len(verse_chunks) + len(commentary_chunks)
    print(f"  Verse chunks: {len(verse_chunks):,}")
    print(f"  Commentary chunks: {len(commentary_chunks):,}")
    print(f"  Total: {total:,}")

    # Index all chunks
    all_chunks = verse_chunks + commentary_chunks
    batch_size = 96  # Match Cohere's batch limit
    total_batches = (len(all_chunks) + batch_size - 1) // batch_size

    print(f"\nEmbedding and indexing {total:,} chunks (batch size {batch_size})...")
    if start_batch > 0:
        print(f"Skipping first {start_batch} batches (already done)")

    for batch_idx in tqdm(
        range(start_batch, total_batches), desc="Indexing", initial=start_batch, total=total_batches
    ):
        start = batch_idx * batch_size
        batch = all_chunks[start : start + batch_size]

        ids = [c[0] for c in batch]
        embeddable_texts = [c[1] for c in batch]
        bm25_texts = [c[2] for c in batch]
        payloads = [c[3] for c in batch]

        # Embed via Cohere (has built-in retry on rate limit)
        dense_vectors = embedder.embed_documents(embeddable_texts)

        # Upsert to Qdrant
        store.upsert_batch(ids, dense_vectors, bm25_texts, payloads)

        # Save checkpoint every batch (cheap operation, protects against rate-limit failures)
        save_checkpoint(batch_idx + 1, config)

    clear_checkpoint(config)
    final_count = store.count_exact()
    verse_count = store.count_by_chunk_type("verse")
    commentary_count = store.count_by_chunk_type("commentary")

    print(f"\nIndexing complete! Collection '{config.qdrant_collection}' has:")
    print(f"  Verse points: {verse_count:,} / expected {len(verse_chunks):,}")
    print(f"  Commentary points: {commentary_count:,} / expected {len(commentary_chunks):,}")
    print(f"  Total points: {final_count:,} / expected {total:,}")

    if (
        final_count != total
        or verse_count != len(verse_chunks)
        or commentary_count != len(commentary_chunks)
    ):
        raise AssertionError(
            "Qdrant point-count mismatch after indexing: "
            f"total={final_count}/{total}, "
            f"verse={verse_count}/{len(verse_chunks)}, "
            f"commentary={commentary_count}/{len(commentary_chunks)}"
        )


if __name__ == "__main__":
    resume = "--resume" in sys.argv
    index(resume=resume)
