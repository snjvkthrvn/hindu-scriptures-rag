#!/usr/bin/env python3
"""
Example script showing how to query and use processed verses.

This demonstrates basic operations you can perform on the processed JSON data.
"""

import json
from collections import Counter
from pathlib import Path
from typing import Any


class VerseQuery:
    """Simple query interface for processed verses."""

    def __init__(self, verses_file: Path):
        """Load verses from JSON file."""
        with open(verses_file, encoding="utf-8") as f:
            self.verses = json.load(f)
        print(f"Loaded {len(self.verses)} verses")

    def search_by_text(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search verses by text (case-insensitive)."""
        query = query.lower()
        results = []

        for verse in self.verses:
            translation = verse.get("content", {}).get("translation", "").lower()
            sanskrit = verse.get("content", {}).get("sanskrit", "").lower()

            if query in translation or query in sanskrit:
                results.append(verse)
                if len(results) >= limit:
                    break

        return results

    def get_by_source(self, source_name: str) -> list[dict[str, Any]]:
        """Get all verses from a specific source."""
        return [
            v
            for v in self.verses
            if source_name.lower() in v.get("source", {}).get("text", "").lower()
        ]

    def get_by_theme(self, theme: str) -> list[dict[str, Any]]:
        """Get verses tagged with a specific theme."""
        theme = theme.lower()
        return [
            v
            for v in self.verses
            if theme in [t.lower() for t in v.get("metadata", {}).get("themes", [])]
        ]

    def get_by_life_domain(self, domain: str) -> list[dict[str, Any]]:
        """Get verses relevant to a specific life domain."""
        domain = domain.lower()
        return [
            v
            for v in self.verses
            if domain in [d.lower() for d in v.get("metadata", {}).get("life_domains", [])]
        ]

    def get_by_category(self, category: str) -> list[dict[str, Any]]:
        """Get verses by category (shruti, smriti, etc.)."""
        category = category.lower()
        return [
            v for v in self.verses if v.get("metadata", {}).get("category", "").lower() == category
        ]

    def get_statistics(self) -> dict[str, Any]:
        """Get corpus statistics."""
        stats = {
            "total_verses": len(self.verses),
            "sources": Counter(v.get("source", {}).get("text") for v in self.verses),
            "categories": Counter(v.get("metadata", {}).get("category") for v in self.verses),
            "traditions": Counter(v.get("metadata", {}).get("tradition") for v in self.verses),
            "themes": Counter(
                theme for v in self.verses for theme in v.get("metadata", {}).get("themes", [])
            ),
            "life_domains": Counter(
                domain
                for v in self.verses
                for domain in v.get("metadata", {}).get("life_domains", [])
            ),
        }
        return stats

    def print_verse(self, verse: dict[str, Any], show_sanskrit: bool = True) -> None:
        """Pretty print a verse."""
        source = verse.get("source", {})
        content = verse.get("content", {})
        metadata = verse.get("metadata", {})

        print(f"\n{'=' * 60}")
        print(f"{source.get('text', 'Unknown')} - {source.get('chapter_name', '')}")
        if source.get("chapter") and source.get("verse"):
            print(f"Chapter {source['chapter']}, Verse {source['verse']}")
        print(f"{'=' * 60}")

        if show_sanskrit and content.get("sanskrit"):
            print(f"\nSanskrit: {content['sanskrit']}")

        if content.get("transliteration"):
            print(f"\nTransliteration: {content['transliteration']}")

        print(f"\nTranslation: {content['translation']}")

        if metadata.get("themes"):
            print(f"\nThemes: {', '.join(metadata['themes'])}")

        if metadata.get("life_domains"):
            print(f"Life domains: {', '.join(metadata['life_domains'])}")


def example_queries():
    """Run example queries."""
    # Load verses
    verses_file = Path.home() / "hindu-scriptures-rag" / "final" / "verses.json"

    if not verses_file.exists():
        print(f"Error: Verses file not found at {verses_file}")
        print("Please run the pipeline first: python scripts/main.py run")
        return

    query = VerseQuery(verses_file)

    # Example 1: Search for verses about karma
    print("\n" + "╔" + "=" * 58 + "╗")
    print("║" + " " * 15 + "EXAMPLE 1: Search by Theme" + " " * 16 + "║")
    print("╚" + "=" * 58 + "╝")

    karma_verses = query.get_by_theme("karma_yoga")
    print(f"\nFound {len(karma_verses)} verses about karma yoga")
    if karma_verses:
        print("\nFirst result:")
        query.print_verse(karma_verses[0])

    # Example 2: Search for verses about work/motivation
    print("\n\n" + "╔" + "=" * 58 + "╗")
    print("║" + " " * 12 + "EXAMPLE 2: Search by Life Domain" + " " * 13 + "║")
    print("╚" + "=" * 58 + "╝")

    work_verses = query.get_by_life_domain("work")
    print(f"\nFound {len(work_verses)} verses about work")
    if work_verses:
        print("\nFirst result:")
        query.print_verse(work_verses[0])

    # Example 3: Get all Bhagavad Gita verses
    print("\n\n" + "╔" + "=" * 58 + "╗")
    print("║" + " " * 14 + "EXAMPLE 3: Get Specific Text" + " " * 16 + "║")
    print("╚" + "=" * 58 + "╝")

    gita_verses = query.get_by_source("Bhagavad Gita")
    print(f"\nFound {len(gita_verses)} Bhagavad Gita verses")

    # Example 4: Text search
    print("\n\n" + "╔" + "=" * 58 + "╗")
    print("║" + " " * 14 + "EXAMPLE 4: Text Search" + " " * 21 + "║")
    print("╚" + "=" * 58 + "╝")

    search_results = query.search_by_text("detachment", limit=3)
    print("\nFound verses mentioning 'detachment':")
    for i, verse in enumerate(search_results[:3], 1):
        print(f"\n--- Result {i} ---")
        query.print_verse(verse, show_sanskrit=False)

    # Example 5: Statistics
    print("\n\n" + "╔" + "=" * 58 + "╗")
    print("║" + " " * 16 + "EXAMPLE 5: Statistics" + " " * 20 + "║")
    print("╚" + "=" * 58 + "╝")

    stats = query.get_statistics()

    print("\nCorpus Statistics:")
    print(f"  Total verses: {stats['total_verses']}")

    print("\n  Top 5 sources:")
    for source, count in stats["sources"].most_common(5):
        print(f"    - {source}: {count}")

    print("\n  Categories:")
    for category, count in stats["categories"].most_common():
        print(f"    - {category}: {count}")

    print("\n  Top 10 themes:")
    for theme, count in stats["themes"].most_common(10):
        print(f"    - {theme}: {count}")

    print("\n  Top 10 life domains:")
    for domain, count in stats["life_domains"].most_common(10):
        print(f"    - {domain}: {count}")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Query processed verses")
    parser.add_argument(
        "--file",
        default="~/hindu-scriptures-rag/final/verses.json",
        help="Path to verses JSON file",
    )
    parser.add_argument("--examples", action="store_true", help="Run example queries")
    parser.add_argument("--search", help="Search for text in verses")
    parser.add_argument("--theme", help="Get verses by theme")
    parser.add_argument("--domain", help="Get verses by life domain")
    parser.add_argument("--source", help="Get verses from specific source")
    parser.add_argument("--stats", action="store_true", help="Show statistics")
    parser.add_argument("--limit", type=int, default=10, help="Limit number of results")

    args = parser.parse_args()

    if args.examples:
        example_queries()
        return

    verses_file = Path(args.file).expanduser()
    if not verses_file.exists():
        print(f"Error: File not found: {verses_file}")
        return

    query = VerseQuery(verses_file)

    if args.search:
        results = query.search_by_text(args.search, limit=args.limit)
        print(f"\nFound {len(results)} results for '{args.search}':")
        for i, verse in enumerate(results, 1):
            print(f"\n--- Result {i} ---")
            query.print_verse(verse)

    elif args.theme:
        results = query.get_by_theme(args.theme)
        print(f"\nFound {len(results)} verses with theme '{args.theme}':")
        for i, verse in enumerate(results[: args.limit], 1):
            print(f"\n--- Result {i} ---")
            query.print_verse(verse)

    elif args.domain:
        results = query.get_by_life_domain(args.domain)
        print(f"\nFound {len(results)} verses for life domain '{args.domain}':")
        for i, verse in enumerate(results[: args.limit], 1):
            print(f"\n--- Result {i} ---")
            query.print_verse(verse)

    elif args.source:
        results = query.get_by_source(args.source)
        print(f"\nFound {len(results)} verses from '{args.source}':")
        for i, verse in enumerate(results[: args.limit], 1):
            print(f"\n--- Result {i} ---")
            query.print_verse(verse)

    elif args.stats:
        stats = query.get_statistics()
        print("\nCorpus Statistics:")
        print(f"  Total verses: {stats['total_verses']}")
        print(f"  Sources: {len(stats['sources'])}")
        print(f"  Themes: {len(stats['themes'])}")
        print(f"  Life domains: {len(stats['life_domains'])}")

    else:
        print("No query specified. Use --help for options or --examples to see examples.")


if __name__ == "__main__":
    main()
