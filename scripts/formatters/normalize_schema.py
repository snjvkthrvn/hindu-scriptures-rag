"""Normalize parsed verses to unified JSON schema."""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.unicode_utils import normalize_devanagari


class SchemaNormalizer:
    """Normalize verses to unified schema."""

    REQUIRED_TOP_LEVEL = {"id", "source", "content", "metadata", "provenance"}
    REQUIRED_SOURCE = {"text", "chapter", "verse"}
    REQUIRED_CONTENT = {"sanskrit", "transliteration", "translation"}
    REQUIRED_METADATA = {"category", "tradition", "themes", "philosophical_schools"}

    @classmethod
    def normalize_verse(cls, verse: dict[str, Any]) -> dict[str, Any]:
        """
        Normalize a verse to the unified schema.

        Fills in missing fields with defaults and ensures all required fields exist.
        """
        normalized = {
            "id": cls._ensure_verse_id(verse.get("id")),
            "source": cls._normalize_source(verse.get("source", {})),
            "content": cls._normalize_content(verse.get("content", {})),
            "metadata": cls._normalize_metadata(verse.get("metadata", {})),
            "commentaries": verse.get("commentaries", []),
            "provenance": cls._normalize_provenance(verse.get("provenance", {})),
        }

        return normalized

    @classmethod
    def _ensure_verse_id(cls, verse_id: Any) -> str:
        """Ensure verse ID is valid and non-empty."""
        if isinstance(verse_id, str) and verse_id.strip():
            return verse_id.strip()
        # Generate ID from timestamp if missing
        return f"verse_{datetime.now().timestamp()}"

    @classmethod
    def _normalize_source(cls, source: dict[str, Any]) -> dict[str, Any]:
        """Normalize source metadata."""
        return {
            "text": str(source.get("text", "Unknown")),
            "chapter": source.get("chapter", None),
            "chapter_name": source.get("chapter_name"),
            "verse": source.get("verse", 0),
            "section": source.get("section"),
        }

    @classmethod
    def _normalize_content(cls, content: dict[str, Any]) -> dict[str, Any]:
        """Normalize verse content."""
        sanskrit = str(content.get("sanskrit", "")).strip()
        transliteration = str(content.get("transliteration", "")).strip()
        translation = str(content.get("translation", "")).strip()

        # Normalize Sanskrit
        if sanskrit:
            sanskrit = normalize_devanagari(sanskrit)

        return {
            "sanskrit": sanskrit,
            "transliteration": transliteration,
            "translation": translation,
            "word_by_word": content.get("word_by_word", {}),
        }

    @classmethod
    def _normalize_metadata(cls, metadata: dict[str, Any]) -> dict[str, Any]:
        """Normalize metadata."""
        themes = metadata.get("themes", [])
        if isinstance(themes, str):
            themes = [t.strip() for t in themes.split(",")]
        elif not isinstance(themes, list):
            themes = []

        schools = metadata.get("philosophical_schools", [])
        if isinstance(schools, str):
            schools = [s.strip() for s in schools.split(",")]
        elif not isinstance(schools, list):
            schools = []

        return {
            "category": str(metadata.get("category", "prakarana")).lower(),
            "tradition": str(metadata.get("tradition", "common")).lower(),
            "themes": [t.lower().replace(" ", "_") for t in themes if t],
            "philosophical_schools": [s.lower().replace(" ", "_") for s in schools if s],
            "life_domains": metadata.get("life_domains", []),
        }

    @classmethod
    def _normalize_provenance(cls, provenance: dict[str, Any]) -> dict[str, Any]:
        """Normalize provenance information."""
        return {
            "download_source": str(provenance.get("download_source", "unknown")),
            "original_url": str(provenance.get("original_url", "")),
            "license": str(provenance.get("license", "Unknown")),
            "processed_date": str(provenance.get("processed_date", datetime.now().isoformat())),
        }


class VerseValidator:
    """Validate normalized verses."""

    @staticmethod
    def is_valid(verse: dict[str, Any]) -> bool:
        """Check if verse meets minimum validity requirements."""
        # Must have ID
        if not verse.get("id"):
            return False

        # Must have source text
        if not verse.get("source", {}).get("text"):
            return False

        # Must have translation
        if not verse.get("content", {}).get("translation"):
            return False

        # Should have at least Sanskrit or translation
        content = verse.get("content", {})
        if not content.get("sanskrit") and not content.get("translation"):
            return False

        return True


def process_directory(input_dir: Path, output_file: Path) -> dict[str, Any]:
    """
    Process all JSON files in input directory and normalize to unified schema.

    Returns:
        Statistics about the normalization
    """
    all_verses = []
    stats = {"total_input": 0, "total_output": 0, "invalid_verses": 0, "by_category": {}}

    # Load all JSON files
    json_files = list(input_dir.glob("*.json"))
    print(f"Found {len(json_files)} JSON files to process")

    for json_file in json_files:
        print(f"\nProcessing {json_file.name}...")
        try:
            with open(json_file, encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, list):
                data = [data]

            for verse in data:
                stats["total_input"] += 1

                # Normalize
                normalized = SchemaNormalizer.normalize_verse(verse)

                # Validate
                if VerseValidator.is_valid(normalized):
                    all_verses.append(normalized)
                    stats["total_output"] += 1

                    # Track by category
                    category = normalized.get("metadata", {}).get("category", "unknown")
                    if category not in stats["by_category"]:
                        stats["by_category"][category] = 0
                    stats["by_category"][category] += 1
                else:
                    stats["invalid_verses"] += 1

        except json.JSONDecodeError as e:
            print(f"  JSON error: {e}")
        except Exception as e:
            print(f"  Error: {e}")

    # Save normalized verses
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_verses, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print("NORMALIZATION SUMMARY")
    print(f"{'=' * 60}")
    print(f"Input verses: {stats['total_input']}")
    print(f"Output verses: {stats['total_output']}")
    print(f"Invalid verses: {stats['invalid_verses']}")
    print("By category:")
    for category, count in sorted(stats["by_category"].items()):
        print(f"  {category}: {count}")
    print(f"\nOutput: {output_file}")

    return stats


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Normalize verses to unified schema")
    parser.add_argument(
        "--input-dir",
        default="~/hindu-scriptures-rag/processed",
        help="Input directory with parsed JSON files",
    )
    parser.add_argument(
        "--output",
        default="~/hindu-scriptures-rag/final/verses.json",
        help="Output file for normalized verses",
    )

    args = parser.parse_args()
    input_dir = Path(args.input_dir).expanduser()
    output_file = Path(args.output).expanduser()

    if not input_dir.exists():
        print(f"Error: Input directory not found: {input_dir}")
        return

    process_directory(input_dir, output_file)


if __name__ == "__main__":
    main()
