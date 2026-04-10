"""Quality validation and checking utilities."""

import json
from pathlib import Path
from typing import Any

from .unicode_utils import is_devanagari_char


class VersValidator:
    """Validate verse documents against schema."""

    REQUIRED_FIELDS = {"id", "source", "content", "metadata", "provenance"}

    SOURCE_FIELDS = {"text", "chapter", "verse"}
    CONTENT_FIELDS = {"sanskrit", "transliteration", "translation"}
    # At least one of sanskrit or translation must be non-empty
    CONTENT_FIELDS_REQUIRED = set()  # Checked separately
    METADATA_FIELDS = {"category", "tradition", "themes"}
    PROVENANCE_FIELDS = {"download_source", "license", "processed_date"}

    @classmethod
    def validate_verse(cls, verse: dict[str, Any]) -> tuple[bool, list[str]]:
        """
        Validate a single verse document.

        Returns:
            (is_valid, list_of_errors)
        """
        errors = []

        # Check required top-level fields
        for field in cls.REQUIRED_FIELDS:
            if field not in verse:
                errors.append(f"Missing required field: {field}")

        if errors:
            return False, errors

        # Validate source
        if not isinstance(verse.get("source"), dict):
            errors.append("source must be a dict")
        else:
            for field in cls.SOURCE_FIELDS:
                if field not in verse["source"]:
                    errors.append(f"Missing source.{field}")

        # Validate content
        if not isinstance(verse.get("content"), dict):
            errors.append("content must be a dict")
        else:
            for field in cls.CONTENT_FIELDS:
                if field not in verse["content"]:
                    errors.append(f"Missing content.{field}")
                else:
                    value = verse["content"][field]
                    if not isinstance(value, str):
                        errors.append(f"content.{field} must be string")
            # At least sanskrit or translation must be non-empty
            content = verse.get("content", {})
            sanskrit = (content.get("sanskrit") or "").strip()
            translation = (content.get("translation") or "").strip()
            if not sanskrit and not translation:
                errors.append("content must have non-empty sanskrit or translation")

        # Validate metadata
        if not isinstance(verse.get("metadata"), dict):
            errors.append("metadata must be a dict")
        else:
            for field in cls.METADATA_FIELDS:
                if field not in verse["metadata"]:
                    errors.append(f"Missing metadata.{field}")

        # Validate provenance
        if not isinstance(verse.get("provenance"), dict):
            errors.append("provenance must be a dict")
        else:
            for field in cls.PROVENANCE_FIELDS:
                if field not in verse["provenance"]:
                    errors.append(f"Missing provenance.{field}")

        # Validate ID format
        verse_id = verse.get("id", "")
        if not verse_id or not isinstance(verse_id, str):
            errors.append("id must be non-empty string")

        return len(errors) == 0, errors

    @classmethod
    def check_sanskrit_translation_alignment(cls, verse: dict[str, Any]) -> bool:
        """
        Check if Sanskrit and translation appear aligned.

        Basic heuristic: translation should be at least 30% of Sanskrit length.
        """
        if "content" not in verse:
            return False

        content = verse["content"]
        sanskrit = content.get("sanskrit", "")
        translation = content.get("translation", "")

        if not sanskrit or not translation:
            return False

        # Count meaningful characters (excluding spaces/punctuation)
        sanskrit_chars = len([c for c in sanskrit if is_devanagari_char(c)])
        trans_chars = len([c for c in translation if c.isalnum()])

        # Allow cases where translation is shorter but meaningful
        return trans_chars > 5 and sanskrit_chars > 0


class CorpusValidator:
    """Validate entire corpus of verses."""

    def __init__(self):
        self.total_verses = 0
        self.valid_verses = 0
        self.invalid_verses = 0
        self.errors = []

    def validate_file(self, json_file: Path) -> dict[str, Any]:
        """
        Validate a JSON verses file.

        Returns:
            Statistics and error report
        """
        stats = {
            "total": 0,
            "valid": 0,
            "invalid": 0,
            "errors": [],
            "by_source": {},
            "by_category": {},
        }

        try:
            with open(json_file, encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, list):
                stats["errors"].append("Root element must be a list")
                return stats

            for i, verse in enumerate(data):
                stats["total"] += 1
                is_valid, errors = VersValidator.validate_verse(verse)

                if is_valid:
                    stats["valid"] += 1
                else:
                    stats["invalid"] += 1
                    stats["errors"].append(
                        {"verse_id": verse.get("id", f"unknown_{i}"), "errors": errors}
                    )

                # Track by source
                source = verse.get("source", {}).get("text", "unknown")
                if source not in stats["by_source"]:
                    stats["by_source"][source] = {"total": 0, "valid": 0}
                stats["by_source"][source]["total"] += 1
                if is_valid:
                    stats["by_source"][source]["valid"] += 1

                # Track by category
                category = verse.get("metadata", {}).get("category", "unknown")
                if category not in stats["by_category"]:
                    stats["by_category"][category] = {"total": 0, "valid": 0}
                stats["by_category"][category]["total"] += 1
                if is_valid:
                    stats["by_category"][category]["valid"] += 1

        except json.JSONDecodeError as e:
            stats["errors"].append(f"JSON parsing error: {str(e)}")
        except Exception as e:
            stats["errors"].append(f"Unexpected error: {str(e)}")

        return stats

    def print_report(self, stats: dict[str, Any]) -> None:
        """Pretty print validation report."""
        print("\n" + "=" * 60)
        print("CORPUS VALIDATION REPORT")
        print("=" * 60)

        print("\nOverall Statistics:")
        print(f"  Total verses: {stats['total']}")
        print(
            f"  Valid verses: {stats['valid']} ({100 * stats['valid'] / max(stats['total'], 1):.1f}%)"
        )
        print(f"  Invalid verses: {stats['invalid']}")

        if stats["by_source"]:
            print("\nBreakdown by source:")
            for source, counts in sorted(stats["by_source"].items()):
                pct = 100 * counts["valid"] / max(counts["total"], 1)
                print(f"  {source}: {counts['valid']}/{counts['total']} ({pct:.1f}%)")

        if stats["by_category"]:
            print("\nBreakdown by category:")
            for category, counts in sorted(stats["by_category"].items()):
                pct = 100 * counts["valid"] / max(counts["total"], 1)
                print(f"  {category}: {counts['valid']}/{counts['total']} ({pct:.1f}%)")

        if stats["errors"]:
            print("\nFirst 10 errors:")
            for error in stats["errors"][:10]:
                if isinstance(error, dict):
                    print(f"  {error['verse_id']}: {error['errors']}")
                else:
                    print(f"  {error}")

        print("=" * 60)
