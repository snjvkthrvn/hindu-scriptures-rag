"""Detect and merge duplicate verses from multiple sources."""

import json
from pathlib import Path
from typing import List, Dict, Any, Tuple, Set
from difflib import SequenceMatcher
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


class DuplicateDetector:
    """Detect duplicate verses across sources."""

    def __init__(self, similarity_threshold: float = 0.8):
        """
        Initialize detector.

        Args:
            similarity_threshold: Minimum similarity (0-1) to consider verses duplicates
        """
        self.threshold = similarity_threshold

    def find_duplicates(self, verses: List[Dict[str, Any]]) -> List[List[int]]:
        """
        Find groups of duplicate verses (by index).

        Returns:
            List of groups, where each group is a list of verse indices
        """
        duplicates = []
        processed = set()

        for i, verse1 in enumerate(verses):
            if i in processed:
                continue

            group = [i]
            processed.add(i)

            for j in range(i + 1, len(verses)):
                if j in processed:
                    continue

                if self._are_duplicates(verse1, verses[j]):
                    group.append(j)
                    processed.add(j)

            if len(group) > 1:
                duplicates.append(group)

        return duplicates

    def _are_duplicates(self, verse1: Dict[str, Any], verse2: Dict[str, Any]) -> bool:
        """Check if two verses are duplicates."""
        # Compare Sanskrit text (most reliable)
        sanskrit1 = verse1.get('content', {}).get('sanskrit', '').lower().strip()
        sanskrit2 = verse2.get('content', {}).get('sanskrit', '').lower().strip()

        if sanskrit1 and sanskrit2:
            similarity = self._string_similarity(sanskrit1, sanskrit2)
            if similarity > self.threshold:
                return True

        # Compare translation
        trans1 = verse1.get('content', {}).get('translation', '').lower().strip()
        trans2 = verse2.get('content', {}).get('translation', '').lower().strip()

        if trans1 and trans2 and len(trans1) > 50 and len(trans2) > 50:
            similarity = self._string_similarity(trans1, trans2)
            if similarity > self.threshold:
                return True

        return False

    @staticmethod
    def _string_similarity(s1: str, s2: str) -> float:
        """Calculate similarity between two strings (0-1)."""
        return SequenceMatcher(None, s1, s2).ratio()


class DuplicateMerger:
    """Merge duplicate verses into single canonical version."""

    @staticmethod
    def merge_group(verses: List[Dict[str, Any]]) -> Dict[str, Any]:
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
        merged['source'] = merged.get('source', {}).copy()
        merged['content'] = merged.get('content', {}).copy()
        merged['metadata'] = merged.get('metadata', {}).copy()
        merged['provenance'] = merged.get('provenance', {}).copy()
        merged['commentaries'] = merged.get('commentaries', []).copy()

        # Track alternate sources
        alternate_sources = []

        # Merge from other verses
        for verse in verses[1:]:
            source = verse.get('source', {})
            if source not in alternate_sources:
                alternate_sources.append(source)

            # Merge translations (prefer longer, better translations)
            original_trans = merged['content'].get('translation', '')
            new_trans = verse.get('content', {}).get('translation', '')

            if len(new_trans) > len(original_trans) and new_trans.strip():
                merged['content']['translation'] = new_trans

            # Merge transliterations
            if not merged['content'].get('transliteration') and verse.get('content', {}).get('transliteration'):
                merged['content']['transliteration'] = verse['content']['transliteration']

            # Merge commentaries
            for commentary in verse.get('commentaries', []):
                if commentary not in merged.get('commentaries', []):
                    merged['commentaries'].append(commentary)

            # Merge themes
            original_themes = set(merged.get('metadata', {}).get('themes', []))
            new_themes = set(verse.get('metadata', {}).get('themes', []))
            merged['metadata']['themes'] = sorted(list(original_themes | new_themes))

        # Add alternate sources metadata
        merged['metadata']['alternate_sources'] = alternate_sources
        merged['metadata']['duplicate_count'] = len(verses)

        return merged


def deduplicate_verses(verses: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Deduplicate a list of verses.

    Returns:
        (deduplicated_verses, statistics)
    """
    detector = DuplicateDetector(similarity_threshold=0.8)
    merger = DuplicateMerger()

    print("Detecting duplicates...")
    duplicates = detector.find_duplicates(verses)

    print(f"Found {len(duplicates)} duplicate groups")

    # Mark duplicates for removal
    duplicate_indices = set()
    for group in duplicates:
        duplicate_indices.update(group[1:])  # Keep first, remove rest

    # Merge duplicate groups
    merged_verses = []
    processed_groups = set()

    for i, verse in enumerate(verses):
        # Check if this verse is part of a duplicate group
        is_part_of_group = False
        for group_idx, group in enumerate(duplicates):
            if i in group:
                if group_idx not in processed_groups:
                    # Merge this group
                    group_verses = [verses[j] for j in group]
                    merged = merger.merge_group(group_verses)
                    merged_verses.append(merged)
                    processed_groups.add(group_idx)
                is_part_of_group = True
                break

        # If not part of a duplicate group, keep as-is
        if not is_part_of_group:
            merged_verses.append(verse)

    stats = {
        'original_count': len(verses),
        'duplicate_groups': len(duplicates),
        'duplicates_removed': len(duplicate_indices),
        'final_count': len(merged_verses),
        'deduplication_ratio': 1 - (len(merged_verses) / len(verses)) if verses else 0
    }

    return merged_verses, stats


def process_file(input_file: Path, output_file: Path) -> Dict[str, Any]:
    """
    Deduplicate verses in a JSON file.

    Returns:
        Statistics
    """
    print(f"Reading {input_file}...")
    with open(input_file, 'r', encoding='utf-8') as f:
        verses = json.load(f)

    if not isinstance(verses, list):
        verses = [verses]

    deduped_verses, stats = deduplicate_verses(verses)

    # Save
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(deduped_verses, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print("DEDUPLICATION SUMMARY")
    print(f"{'='*60}")
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
        '--input',
        default='~/hindu-scriptures-rag/final/verses.json',
        help='Input verses JSON file'
    )
    parser.add_argument(
        '--output',
        help='Output file (default: input file with _deduped suffix)'
    )
    parser.add_argument(
        '--threshold',
        type=float,
        default=0.8,
        help='Similarity threshold for duplicates (0-1)'
    )

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


if __name__ == '__main__':
    main()
