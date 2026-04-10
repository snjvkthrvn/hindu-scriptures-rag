"""Ingest Hindu scripture verses into ChromaDB with embeddings.

Usage:
    python scripts/rag/ingest.py
    python scripts/rag/ingest.py --config-override top_k=10
"""

import json

import chromadb
from config import RAGConfig
from sentence_transformers import SentenceTransformer
from tqdm import tqdm


def build_embeddable_text(verse: dict) -> str:
    """Build the text used for embedding.

    Priority: English translation > transliteration > Sanskrit.
    Always appends metadata context in English for better retrieval.
    """
    content = verse.get("content", {})
    translation = content.get("translation", "").strip()
    transliteration = content.get("transliteration", "").strip()
    sanskrit = content.get("sanskrit", "").strip()

    # Pick the best available text for the embedding model
    if translation:
        primary = translation
    elif transliteration:
        primary = transliteration
    elif sanskrit:
        primary = sanskrit
    else:
        primary = ""

    # Append metadata context in English for semantic searchability
    source = verse.get("source", {})
    meta = verse.get("metadata", {})

    parts = [primary]

    source_text = source.get("text", "")
    if source_text:
        parts.append(f"Source: {source_text}")

    chapter_name = source.get("chapter_name", "")
    if chapter_name:
        parts.append(f"Chapter: {chapter_name}")

    category = meta.get("category", "")
    if category:
        parts.append(f"Category: {category}")

    tradition = meta.get("tradition", "")
    if tradition:
        parts.append(f"Tradition: {tradition}")

    themes = meta.get("themes", [])
    if themes:
        parts.append(f"Themes: {', '.join(themes)}")

    return " | ".join(parts)


def build_full_document(verse: dict) -> str:
    """Build the full rich document stored in ChromaDB (returned at query time)."""
    content = verse.get("content", {})
    source = verse.get("source", {})

    lines = []

    # Header
    source_text = source.get("text", "Unknown")
    chapter = source.get("chapter_name", "")
    verse_num = source.get("verse", "")
    header = f"[{source_text}"
    if chapter:
        header += f" - {chapter}"
    if verse_num:
        header += f", Verse {verse_num}"
    header += "]"
    lines.append(header)

    # Sanskrit
    sanskrit = content.get("sanskrit", "").strip()
    if sanskrit:
        lines.append(f"Sanskrit: {sanskrit}")

    # Transliteration
    transliteration = content.get("transliteration", "").strip()
    if transliteration:
        lines.append(f"Transliteration: {transliteration}")

    # Translation
    translation = content.get("translation", "").strip()
    if translation:
        lines.append(f"Translation: {translation}")

    return "\n".join(lines)


def flatten_metadata(verse: dict) -> dict:
    """Flatten verse metadata into ChromaDB-compatible flat dict (strings, ints, floats, bools)."""
    source = verse.get("source", {})
    meta = verse.get("metadata", {})
    content = verse.get("content", {})

    themes = meta.get("themes", [])
    themes_str = ", ".join(str(t) for t in themes) if themes else ""
    if len(themes_str) > 500:
        themes_str = themes_str[:497] + "..."

    return {
        "verse_id": str(verse.get("id", "")),
        "source_text": str(source.get("text", "")),
        "chapter": int(source.get("chapter", 0) or 0),
        "chapter_name": str(source.get("chapter_name", "")),
        "verse": int(source.get("verse", 0) or 0),
        "category": str(meta.get("category", "")),
        "tradition": str(meta.get("tradition", "")),
        "themes": themes_str,
        "has_translation": 1 if content.get("translation", "").strip() else 0,
    }


def ingest(config: RAGConfig | None = None) -> None:
    """Run the full ingestion pipeline."""
    if config is None:
        config = RAGConfig()

    # Load verses
    print(f"Loading verses from {config.verses_file}...")
    with open(config.verses_file) as f:
        verses = json.load(f)
    print(f"Loaded {len(verses):,} verses")

    # Initialize embedding model
    print(f"Loading embedding model: {config.sentence_transformer_model}...")
    model = SentenceTransformer(config.sentence_transformer_model)

    # Initialize ChromaDB
    print(f"Initializing ChromaDB at {config.chromadb_dir}...")
    config.chromadb_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(config.chromadb_dir))

    # Delete existing collection if present (fresh ingest)
    try:
        client.delete_collection(config.collection_name)
        print(f"Deleted existing collection '{config.collection_name}'")
    except Exception:
        pass  # Collection may not exist yet

    collection = client.create_collection(
        name=config.collection_name,
        metadata={"hnsw:space": "cosine"},
    )

    # Process in batches
    total = len(verses)
    batch_size = config.batch_size

    print(f"Ingesting {total:,} verses in batches of {batch_size:,}...")

    for start in tqdm(range(0, total, batch_size), desc="Batches"):
        batch = verses[start : start + batch_size]

        ids = []
        documents = []
        embeddable_texts = []
        metadatas = []

        for i, verse in enumerate(batch):
            base_id = verse.get("id", f"verse_{start}_{i}")
            verse_id = f"{base_id}_{start}_{i}"  # Ensure unique IDs (sources can duplicate)
            embeddable = build_embeddable_text(verse)

            # Skip verses with no usable text
            if not embeddable.strip():
                continue

            ids.append(verse_id)
            documents.append(build_full_document(verse))
            embeddable_texts.append(embeddable)
            metadatas.append(flatten_metadata(verse))

        if not ids:
            continue

        # Pre-compute embeddings
        embeddings = model.encode(embeddable_texts, show_progress_bar=False).tolist()

        collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    print(
        f"\nIngestion complete! Collection '{config.collection_name}' has {collection.count():,} documents."
    )


if __name__ == "__main__":
    ingest()
