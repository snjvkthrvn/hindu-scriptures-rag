#!/usr/bin/env python3
"""Validate JSON schema and check verse counts."""

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from utils import VersValidator


class SchemaValidator:
    """Comprehensive schema validation."""

    EXPECTED_COUNTS = {
        "Bhagavad Gita": 700,
        "Isha Upanishad": 18,
        "Kena Upanishad": 35,
        "Katha Upanishad": 119,
        "Prashna Upanishad": 63,
        "Mundaka Upanishad": 64,
        "Mandukya Upanishad": 12,
        "Taittiriya Upanishad": 71,
        "Aitareya Upanishad": 33,
        "Chandogya Upanishad": 630,
        "Brihadaranyaka Upanishad": 891,
        "Svetasvatara Upanishad": 122,
    }

    @classmethod
    def validate_file(cls, json_file: Path) -> dict[str, Any]:
        """Validate a verses JSON file."""
        print(f"\n{'=' * 60}")
        print(f"VALIDATING: {json_file.name}")
        print(f"{'=' * 60}")

        if not json_file.exists():
            return {"error": f"File not found: {json_file}"}

        try:
            with open(json_file, encoding="utf-8") as f:
                verses = json.load(f)
        except json.JSONDecodeError as e:
            return {"error": f"JSON decode error: {e}"}

        if not isinstance(verses, list):
            return {"error": "Root element must be a list"}

        results = {
            "file": str(json_file),
            "total_verses": len(verses),
            "valid_verses": 0,
            "invalid_verses": 0,
            "by_source": {},
            "by_category": {},
            "validation_errors": [],
            "missing_texts": [],
            "coverage": {},
        }

        # Validate each verse
        for i, verse in enumerate(verses):
            is_valid, errors = VersValidator.validate_verse(verse)

            if is_valid:
                results["valid_verses"] += 1
            else:
                results["invalid_verses"] += 1
                results["validation_errors"].append(
                    {"verse_id": verse.get("id", f"verse_{i}"), "errors": errors}
                )

            # Track by source
            source = verse.get("source", {}).get("text", "Unknown")
            if source not in results["by_source"]:
                results["by_source"][source] = 0
            results["by_source"][source] += 1

            # Track by category
            category = verse.get("metadata", {}).get("category", "unknown")
            if category not in results["by_category"]:
                results["by_category"][category] = 0
            results["by_category"][category] += 1

        # Check coverage against expected counts
        for text, expected in cls.EXPECTED_COUNTS.items():
            actual = results["by_source"].get(text, 0)
            coverage_pct = (actual / expected * 100) if expected > 0 else 0

            results["coverage"][text] = {
                "expected": expected,
                "actual": actual,
                "percentage": coverage_pct,
                "status": "complete" if actual >= expected else "incomplete",
            }

            if actual < expected:
                results["missing_texts"].append(
                    {
                        "text": text,
                        "expected": expected,
                        "actual": actual,
                        "missing": expected - actual,
                    }
                )

        return results

    @classmethod
    def print_results(cls, results: dict[str, Any]) -> None:
        """Pretty print validation results."""
        if "error" in results:
            print(f"\n❌ Error: {results['error']}")
            return

        print("\n📊 Overall Statistics:")
        print(f"  Total verses: {results['total_verses']}")
        print(
            f"  Valid verses: {results['valid_verses']} ({results['valid_verses'] / max(results['total_verses'], 1) * 100:.1f}%)"
        )
        print(f"  Invalid verses: {results['invalid_verses']}")

        print("\n📚 By Source:")
        for source, count in sorted(results["by_source"].items(), key=lambda x: x[1], reverse=True):
            print(f"  {source}: {count}")

        print("\n📁 By Category:")
        for category, count in sorted(results["by_category"].items()):
            print(f"  {category}: {count}")

        if results["coverage"]:
            print("\n✅ Coverage Analysis:")
            for text, cov in sorted(results["coverage"].items()):
                status_icon = "✓" if cov["status"] == "complete" else "⚠"
                print(
                    f"  {status_icon} {text}: {cov['actual']}/{cov['expected']} ({cov['percentage']:.1f}%)"
                )

        if results["missing_texts"]:
            print("\n⚠️  Missing/Incomplete Texts:")
            for missing in results["missing_texts"]:
                print(
                    f"  - {missing['text']}: {missing['actual']}/{missing['expected']} ({missing['missing']} verses missing)"
                )

        if results["validation_errors"]:
            print("\n❌ Validation Errors (first 10):")
            for error in results["validation_errors"][:10]:
                print(f"  {error['verse_id']}: {', '.join(error['errors'][:3])}")

        # Final verdict
        print(f"\n{'=' * 60}")
        if results["invalid_verses"] == 0 and not results["missing_texts"]:
            print("✅ VALIDATION PASSED")
        elif results["invalid_verses"] > 0:
            print("⚠️  VALIDATION WARNINGS - Some verses have issues")
        else:
            print("✅ SCHEMA VALID - But coverage incomplete")
        print(f"{'=' * 60}")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Validate verses JSON schema")
    parser.add_argument(
        "file",
        nargs="?",
        default="~/hindu-scriptures-rag/final/verses.json",
        help="Path to verses JSON file to validate",
    )
    parser.add_argument(
        "--expected-gita", type=int, default=700, help="Expected number of Gita verses"
    )
    parser.add_argument(
        "--check-all", action="store_true", help="Check all JSON files in final directory"
    )

    args = parser.parse_args()
    file_path = Path(args.file).expanduser()

    if args.check_all:
        final_dir = file_path.parent if file_path.is_file() else file_path
        json_files = list(final_dir.glob("*.json"))

        if not json_files:
            print(f"No JSON files found in {final_dir}")
            return

        for json_file in json_files:
            results = SchemaValidator.validate_file(json_file)
            SchemaValidator.print_results(results)
    else:
        if not file_path.exists():
            print(f"Error: File not found: {file_path}")
            sys.exit(1)

        results = SchemaValidator.validate_file(file_path)
        SchemaValidator.print_results(results)

        # Exit with error code if validation failed
        if results.get("invalid_verses", 0) > 0:
            sys.exit(1)


if __name__ == "__main__":
    main()
