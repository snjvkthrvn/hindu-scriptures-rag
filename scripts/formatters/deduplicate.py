"""Detect and merge duplicate verses from multiple sources."""

import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))


class DuplicateDetector:
    """Detect exact-duplicate verses across sources via normalized-text hashing."""

    # Strip whitespace, digits, danda marks, and punctuation so trivially
    # different encodings of the same verse collapse to one key.
    _STRIP = re.compile(r"[\s।॥|.,;:!?()\[\]{}/\\0-9०-९‐-―-]")

    @classmethod
    def _dedup_key(cls, verse: dict[str, Any]) -> str | None:
        """Return a normalized text key, or None if the verse is too short to match."""
        content = verse.get("content", {})
        text = content.get("sanskrit") or content.get("translation") or ""
        key = cls._STRIP.sub("", text.lower())
        return key if len(key) >= 8 else None

    def find_duplicates(self, verses: list[dict[str, Any]]) -> list[list[int]]:
        """
        Group verses sharing an identical normalized text key.

        O(n) bucketing. The original pairwise scan was O(n^2) — infeasible at
        full corpus scale (~10^10 fuzzy comparisons).

        Returns:
            Duplicate groups; each group is a list of verse indices.
        """
        buckets: dict[str, list[int]] = {}
        for i, verse in enumerate(verses):
            key = self._dedup_key(verse)
            if key is not None:
                buckets.setdefault(key, []).append(i)

        return [indices for indices in buckets.values() if len(indices) > 1]


class DuplicateMerger:
    """Merge duplicate verses into single canonical version."""

    @staticmethod
    def merge_group(verses: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Merge a group of duplicate verses.

        Keeps the first verse as base and merges additional data.

        Returns:
            Single merged verse
        """
        if not verses:
            return {}

        # Use first verse as base
        merged = verses[0].copy()
        merged["source"] = merged.get("source", {}).copy()
        merged["content"] = merged.get("content", {}).copy()
        merged["metadata"] = merged.get("metadata", {}).copy()
        merged["provenance"] = merged.get("provenance", {}).copy()
        merged["commentaries"] = merged.get("commentaries", []).copy()

        # Track alternate sources
        alternate_sources = []

        # Merge from other verses
        for verse in verses[1:]:
            source = verse.get("source", {})
            if source not in alternate_sources:
                alternate_sources.append(source)

            # Merge translations (prefer longer, better translations)
            original_trans = merged["content"].get("translation", "")
            new_trans = verse.get("content", {}).get("translation", "")

            if len(new_trans) > len(original_trans) and new_trans.strip():
                merged["content"]["translation"] = new_trans

            # Merge transliterations
            if not merged["content"].get("transliteration") and verse.get("content", {}).get(
                "transliteration"
            ):
                merged["content"]["transliteration"] = verse["content"]["transliteration"]

            # Merge commentaries
            for commentary in verse.get("commentaries", []):
                if commentary not in merged.get("commentaries", []):
                    merged["commentaries"].append(commentary)

            # Merge themes
            original_themes = set(merged.get("metadata", {}).get("themes", []))
            new_themes = set(verse.get("metadata", {}).get("themes", []))
            merged["metadata"]["themes"] = sorted(list(original_themes | new_themes))

        # Add alternate sources metadata
        merged["metadata"]["alternate_sources"] = alternate_sources
        merged["metadata"]["duplicate_count"] = len(verses)

        return merged


def deduplicate_verses(verses: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Deduplicate a list of verses.

    Returns:
        (deduplicated_verses, statistics)
    """
    detector = DuplicateDetector()
    merger = DuplicateMerger()

    print("Detecting duplicates...")
    duplicates = detector.find_duplicates(verses)
    print(f"Found {len(duplicates)} duplicate groups")

    # Map each duplicated verse index to its group.
    index_to_group: dict[int, int] = {}
    for group_idx, group in enumerate(duplicates):
        for i in group:
            index_to_group[i] = group_idx

    merged_verses = []
    processed_groups = set()
    duplicates_removed = 0

    for i, verse in enumerate(verses):
        group_idx = index_to_group.get(i)
        if group_idx is None:
            merged_verses.append(verse)
            continue
        if group_idx not in processed_groups:
            group_verses = [verses[j] for j in duplicates[group_idx]]
            merged_verses.append(merger.merge_group(group_verses))
            processed_groups.add(group_idx)
            duplicates_removed += len(group_verses) - 1

    stats = {
        "original_count": len(verses),
        "duplicate_groups": len(duplicates),
        "duplicates_removed": duplicates_removed,
        "final_count": len(merged_verses),
        "deduplication_ratio": 1 - (len(merged_verses) / len(verses)) if verses else 0,
    }

    return merged_verses, stats


def process_file(input_file: Path, output_file: Path) -> dict[str, Any]:
    """
    Deduplicate verses in a JSON file.

    Returns:
        Statistics
    """
    print(f"Reading {input_file}...")
    with open(input_file, encoding="utf-8") as f:
        verses = json.load(f)

    if not isinstance(verses, list):
        verses = [verses]

    deduped_verses, stats = deduplicate_verses(verses)

    # Save
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(deduped_verses, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print("DEDUPLICATION SUMMARY")
    print(f"{'=' * 60}")
    print(f"Original verses: {stats['original_count']}")
    print(f"Duplicate groups found: {stats['duplicate_groups']}")
    print(f"Duplicates removed: {stats['duplicates_removed']}")
    print(f"Final verses: {stats['final_count']}")
    print(f"Deduplication ratio: {stats['deduplication_ratio']:.1%}")
    print(f"Output: {output_file}")

    return stats


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Deduplicate verses across sources")
    parser.add_argument(
        "--input", default="~/hindu-scriptures-rag/final/verses.json", help="Input verses JSON file"
    )
    parser.add_argument("--output", help="Output file (default: input file with _deduped suffix)")

    args = parser.parse_args()
    input_file = Path(args.input).expanduser()

    if not input_file.exists():
        print(f"Error: Input file not found: {input_file}")
        return

    if args.output:
        output_file = Path(args.output).expanduser()
    else:
        output_file = input_file.parent / f"{input_file.stem}_deduped.json"

    process_file(input_file, output_file)


if __name__ == "__main__":
    main()
