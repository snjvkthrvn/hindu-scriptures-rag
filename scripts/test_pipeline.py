#!/usr/bin/env python3
"""Test the pipeline with sample data."""

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from formatters import MetadataEnricher, SchemaNormalizer
from utils import VerseDetector, VersValidator, normalize_devanagari


def create_sample_verse() -> dict:
    """Create a sample verse for testing."""
    return {
        "id": "test_bg_2_47",
        "source": {
            "text": "Bhagavad Gita",
            "chapter": 2,
            "chapter_name": "Sankhya Yoga",
            "verse": 47,
            "section": None,
        },
        "content": {
            "sanskrit": "कर्मण्येवाधिकारस्ते मा फलेषु कदाचन।",
            "transliteration": "karmaṇy evādhikāras te mā phaleṣu kadācana",
            "translation": "You have a right to perform your prescribed duties, but you are not entitled to the fruits of your actions.",
            "word_by_word": {"कर्मणि": "in action", "एव": "only", "अधिकारः": "right", "ते": "your"},
        },
        "metadata": {
            "category": "smriti",
            "tradition": "vedanta",
            "themes": ["karma_yoga", "detachment"],
            "philosophical_schools": ["advaita", "dvaita", "vishishtadvaita"],
        },
        "commentaries": [
            {
                "author": "Shankaracharya",
                "school": "advaita",
                "text": "The right to action alone is yours, never to its fruits.",
            }
        ],
        "provenance": {
            "download_source": "test",
            "original_url": "https://example.com",
            "license": "Public Domain",
            "processed_date": datetime.now().isoformat(),
        },
    }


def test_unicode_utils():
    """Test Unicode utilities."""
    print("\n" + "=" * 60)
    print("TEST 1: Unicode Normalization")
    print("=" * 60)

    sanskrit = "कर्मण्येवाधिकारस्ते"
    normalized = normalize_devanagari(sanskrit)

    print(f"Original:    {sanskrit}")
    print(f"Normalized:  {normalized}")
    print(f"Length:      {len(sanskrit)} chars")
    print("✓ Unicode normalization works")


def test_verse_detector():
    """Test verse detection."""
    print("\n" + "=" * 60)
    print("TEST 2: Verse Detection")
    print("=" * 60)

    detector = VerseDetector()

    test_text = """
    ॥1॥ First verse in Devanagari format
    ॥2॥ Second verse in Devanagari format

    1.1 First verse in decimal format
    1.2 Second verse in decimal format

    [1] First verse in bracket format
    [2] Second verse in bracket format
    """

    markers = detector.detect_all_markers(test_text)

    print(f"Found {len(markers)} verse markers:")
    for marker in markers:
        print(f"  - {marker.format_type}: {marker.text} (position {marker.position})")

    print("✓ Verse detection works")


def test_verse_validation():
    """Test verse validation."""
    print("\n" + "=" * 60)
    print("TEST 3: Verse Validation")
    print("=" * 60)

    verse = create_sample_verse()
    is_valid, errors = VersValidator.validate_verse(verse)

    print(f"Sample verse ID: {verse['id']}")
    print(f"Valid: {is_valid}")

    if errors:
        print("Errors:")
        for error in errors:
            print(f"  - {error}")
    else:
        print("✓ No validation errors")

    print("✓ Verse validation works")


def test_schema_normalizer():
    """Test schema normalization."""
    print("\n" + "=" * 60)
    print("TEST 4: Schema Normalization")
    print("=" * 60)

    # Create a verse with some missing fields
    partial_verse = {"id": "test_partial", "content": {"translation": "Some translation"}}

    normalized = SchemaNormalizer.normalize_verse(partial_verse)

    print("Original verse keys:", list(partial_verse.keys()))
    print("Normalized verse keys:", list(normalized.keys()))
    print(
        "Required fields present:",
        all(key in normalized for key in ["id", "source", "content", "metadata", "provenance"]),
    )
    print("✓ Schema normalization works")


def test_metadata_enrichment():
    """Test metadata enrichment."""
    print("\n" + "=" * 60)
    print("TEST 5: Metadata Enrichment")
    print("=" * 60)

    verse = create_sample_verse()
    enriched = MetadataEnricher.enrich_verse(verse)

    original_themes = set(verse.get("metadata", {}).get("themes", []))
    enriched_themes = set(enriched.get("metadata", {}).get("themes", []))

    print(f"Original themes: {original_themes}")
    print(f"Enriched themes: {enriched_themes}")
    print(f"New themes added: {enriched_themes - original_themes}")

    life_domains = enriched.get("metadata", {}).get("life_domains", [])
    print(f"Life domains: {life_domains}")

    print("✓ Metadata enrichment works")


def test_full_pipeline():
    """Test the full pipeline on sample data."""
    print("\n" + "=" * 60)
    print("TEST 6: Full Pipeline")
    print("=" * 60)

    # Create sample verses
    verses = [create_sample_verse() for _ in range(3)]

    # Update IDs
    for i, verse in enumerate(verses):
        verse["id"] = f"test_verse_{i}"

    print(f"Created {len(verses)} sample verses")

    # Normalize
    normalized = [SchemaNormalizer.normalize_verse(v) for v in verses]
    print(f"Normalized {len(normalized)} verses")

    # Enrich
    enriched = MetadataEnricher.enrich_all(normalized)
    print(f"Enriched {len(enriched)} verses")

    # Validate
    valid_count = sum(1 for v in enriched if VersValidator.validate_verse(v)[0])
    print(f"Valid verses: {valid_count}/{len(enriched)}")

    # Save to temp file
    temp_file = Path("/tmp/test_verses.json")
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(enriched, f, ensure_ascii=False, indent=2)

    print(f"Saved test output to: {temp_file}")
    print("✓ Full pipeline works")


def run_all_tests():
    """Run all tests."""
    print("\n" + "╔" + "=" * 58 + "╗")
    print("║" + " " * 15 + "PIPELINE TEST SUITE" + " " * 24 + "║")
    print("╚" + "=" * 58 + "╝")

    tests = [
        test_unicode_utils,
        test_verse_detector,
        test_verse_validation,
        test_schema_normalizer,
        test_metadata_enrichment,
        test_full_pipeline,
    ]

    failed = []

    for test_func in tests:
        try:
            test_func()
        except Exception as e:
            print(f"✗ Test failed: {e}")
            failed.append(test_func.__name__)

    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Total tests: {len(tests)}")
    print(f"Passed: {len(tests) - len(failed)}")
    print(f"Failed: {len(failed)}")

    if failed:
        print("\nFailed tests:")
        for name in failed:
            print(f"  - {name}")
        sys.exit(1)
    else:
        print("\n✓ All tests passed!")
        sys.exit(0)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Test pipeline components")
    parser.add_argument(
        "--test",
        choices=[
            "unicode",
            "detector",
            "validation",
            "normalizer",
            "enrichment",
            "pipeline",
            "all",
        ],
        default="all",
        help="Which test to run",
    )

    args = parser.parse_args()

    test_map = {
        "unicode": test_unicode_utils,
        "detector": test_verse_detector,
        "validation": test_verse_validation,
        "normalizer": test_schema_normalizer,
        "enrichment": test_metadata_enrichment,
        "pipeline": test_full_pipeline,
        "all": run_all_tests,
    }

    test_map[args.test]()


if __name__ == "__main__":
    main()
