"""Add metadata enrichment to verses (themes, life domains, etc.)."""

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))


class MetadataEnricher:
    """Add and enrich metadata for verses."""

    # Keyword mapping for themes
    THEME_KEYWORDS = {
        "karma_yoga": ["karma", "action", "duty", "perform", "work"],
        "bhakti": ["devotion", "love", "surrender", "faith", "bhakti"],
        "jnana": ["knowledge", "wisdom", "understand", "realize"],
        "detachment": ["detachment", "non-attachment", "vairagya", "freedom"],
        "dharma": ["dharma", "righteousness", "duty", "law", "virtue"],
        "atman": ["atman", "self", "soul", "consciousness"],
        "brahman": ["brahman", "ultimate", "absolute", "infinite"],
        "meditation": ["meditation", "meditate", "contemplation", "focus"],
        "yoga": ["yoga", "union", "discipline", "practice"],
        "liberation": ["liberation", "moksha", "freedom", "enlightenment"],
        "mind": ["mind", "thought", "mental", "consciousness"],
        "death": ["death", "mortality", "dying", "end"],
        "rebirth": ["rebirth", "reincarnation", "birth", "samsara"],
        "creation": ["creation", "creation", "origin", "manifest"],
        "god": ["god", "divine", "lord", "supreme"],
        "nature": ["nature", "prakrti", "gunas", "material"],
        "maya": ["maya", "illusion", "appearance", "deception"],
        "vedas": ["vedas", "vedic", "scripture", "shruti"],
    }

    # Keyword mapping for life domains
    LIFE_DOMAIN_KEYWORDS = {
        "work": ["work", "career", "job", "occupation", "labor"],
        "relationships": ["love", "friend", "family", "relationship", "husband", "wife"],
        "purpose": ["purpose", "goal", "meaning", "aim", "direction"],
        "motivation": ["motivation", "inspire", "encourage", "effort"],
        "anxiety": ["anxiety", "fear", "worry", "stress", "concern"],
        "grief": ["grief", "sorrow", "mourning", "loss", "sadness"],
        "anger": ["anger", "rage", "wrath", "irritation", "resentment"],
        "failure": ["failure", "defeat", "loss", "failure", "disappointment"],
        "success": ["success", "achievement", "victory", "triumph", "attainment"],
        "decision": ["decision", "choose", "choice", "decide", "dilemma"],
        "ethics": ["ethics", "moral", "right", "wrong", "good", "evil"],
        "leadership": ["leader", "lead", "guide", "command", "authority"],
        "aging": ["old", "age", "young", "youth", "elderly"],
        "patience": ["patience", "patient", "wait", "tolerance", "endure"],
        "forgiveness": ["forgive", "forgiveness", "pardon", "mercy"],
        "gratitude": ["gratitude", "grateful", "thanks", "appreciate"],
        "mindfulness": ["mindful", "awareness", "aware", "presence", "present"],
    }

    @classmethod
    def enrich_verse(cls, verse: dict[str, Any]) -> dict[str, Any]:
        """
        Enrich a single verse with additional metadata.

        Returns:
            Enriched verse dictionary
        """
        # Get all searchable text
        content = verse.get("content", {})
        metadata = verse.get("metadata", {})

        text_to_search = " ".join(
            [
                content.get("sanskrit", ""),
                content.get("transliteration", ""),
                content.get("translation", ""),
                str(verse.get("source", {}).get("chapter_name", "")),
                str(metadata.get("themes", [])),
            ]
        ).lower()

        # Extract themes
        themes = set(metadata.get("themes", []))
        for theme, keywords in cls.THEME_KEYWORDS.items():
            if any(kw in text_to_search for kw in keywords):
                themes.add(theme)

        # Extract life domains
        life_domains = []
        for domain, keywords in cls.LIFE_DOMAIN_KEYWORDS.items():
            if any(kw in text_to_search for kw in keywords):
                life_domains.append(domain)

        # Update metadata
        enriched = verse.copy()
        enriched["metadata"] = metadata.copy()
        enriched["metadata"]["themes"] = sorted(list(themes))
        enriched["metadata"]["life_domains"] = sorted(list(set(life_domains)))

        return enriched

    @classmethod
    def enrich_all(cls, verses: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Enrich all verses in a list."""
        return [cls.enrich_verse(verse) for verse in verses]


class MetadataValidator:
    """Validate that metadata is complete and reasonable."""

    @staticmethod
    def validate_verse(verse: dict[str, Any]) -> list[str]:
        """
        Validate metadata for a verse.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        metadata = verse.get("metadata", {})

        # Check required fields
        if not metadata.get("category"):
            errors.append("Missing category")

        if not metadata.get("tradition"):
            errors.append("Missing tradition")

        # Themes should be non-empty for most verses
        themes = metadata.get("themes", [])
        if not themes:
            errors.append("No themes assigned")

        # Should have some life domains for practical relevance
        # (but not required)

        return errors


def process_file(input_file: Path, output_file: Path) -> dict[str, Any]:
    """
    Enrich metadata in a verses JSON file.

    Returns:
        Statistics about enrichment
    """
    print(f"Reading {input_file}...")
    with open(input_file, encoding="utf-8") as f:
        verses = json.load(f)

    if not isinstance(verses, list):
        verses = [verses]

    print(f"Enriching {len(verses)} verses...")
    enriched_verses = MetadataEnricher.enrich_all(verses)

    # Validate
    invalid_count = 0
    for verse in enriched_verses:
        errors = MetadataValidator.validate_verse(verse)
        if errors:
            invalid_count += 1

    # Save
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(enriched_verses, f, ensure_ascii=False, indent=2)

    stats = {
        "total_verses": len(enriched_verses),
        "validation_warnings": invalid_count,
        "output_file": str(output_file),
    }

    print(f"\n{'=' * 60}")
    print("METADATA ENRICHMENT SUMMARY")
    print(f"{'=' * 60}")
    print(f"Verses enriched: {stats['total_verses']}")
    print(f"Validation warnings: {stats['validation_warnings']}")
    print(f"Output: {output_file}")

    return stats


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Enrich verses with additional metadata")
    parser.add_argument(
        "--input", default="~/hindu-scriptures-rag/final/verses.json", help="Input verses JSON file"
    )
    parser.add_argument("--output", help="Output file (default: input file with _enriched suffix)")

    args = parser.parse_args()
    input_file = Path(args.input).expanduser()

    if not input_file.exists():
        print(f"Error: Input file not found: {input_file}")
        return

    if args.output:
        output_file = Path(args.output).expanduser()
    else:
        output_file = input_file.parent / f"{input_file.stem}_enriched.json"

    process_file(input_file, output_file)


if __name__ == "__main__":
    main()
