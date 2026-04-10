#!/usr/bin/env python3
"""
Master orchestration script for Hindu Scripture RAG Data Pipeline.

Handles downloading, parsing, formatting, and validation of Hindu scripture texts.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Add scripts dir to path
sys.path.insert(0, str(Path(__file__).parent))

from downloaders import GitHubDownloader, GutenbergDownloader, SacredTextsDownloader
from formatters import MetadataEnricher, deduplicate_verses
from formatters import process_directory as normalize_directory
from parsers import DharmicDataParser, UpanishadCSVParser
from utils import CorpusValidator


class PipelineOrchestrator:
    """Orchestrate the entire scripture processing pipeline."""

    def __init__(self, base_dir: Path = None):
        """Initialize orchestrator."""
        if base_dir is None:
            base_dir = Path.home() / "hindu-scriptures-rag"
        self.base_dir = Path(base_dir)
        self.raw_dir = self.base_dir / "raw"
        self.processed_dir = self.base_dir / "processed"
        self.final_dir = self.base_dir / "final"

        # Create directories
        for d in [self.raw_dir, self.processed_dir, self.final_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def download_all(self, parallel: bool = True) -> dict[str, Any]:
        """Download from all sources."""
        print("\n" + "=" * 60)
        print("PHASE 1: DOWNLOADING SOURCES")
        print("=" * 60)

        results = {}

        # GitHub sources
        print("\n[1/3] Downloading from GitHub...")
        github_downloader = GitHubDownloader(self.raw_dir)
        results["github"] = github_downloader.download_all()

        # Project Gutenberg
        print("\n[2/3] Downloading from Project Gutenberg...")
        gutenberg_downloader = GutenbergDownloader(self.raw_dir / "gutenberg")
        results["gutenberg"] = gutenberg_downloader.download_all()

        # Sacred Texts
        print("\n[3/3] Downloading from Sacred Texts...")
        sacred_downloader = SacredTextsDownloader(self.raw_dir / "sacred-texts", delay=1.0)
        results["sacred_texts"] = sacred_downloader.download_all()

        return results

    def parse_all(self) -> dict[str, Any]:
        """Parse all downloaded sources."""
        print("\n" + "=" * 60)
        print("PHASE 2: PARSING SOURCE FILES")
        print("=" * 60)

        all_verses = []
        parse_results = {}

        # Parse DharmicData
        print("\n[1/2] Parsing DharmicData JSON...")
        dharmic_dir = self.raw_dir / "dharmicdata"
        if dharmic_dir.exists():
            parser = DharmicDataParser(dharmic_dir)
            count, verses = parser.parse_directory()
            all_verses.extend(verses)
            parse_results["dharmic_data"] = {
                "verses_count": count,
                "status": "complete" if count > 0 else "no_files",
            }
            print(f"  Found {count} verses")

        # Parse Upanishads CSV
        print("\n[2/2] Parsing Upanishad CSV files...")
        upanishad_dir = self.raw_dir / "indian-scriptures"
        if upanishad_dir.exists():
            parser = UpanishadCSVParser(upanishad_dir)
            count, verses = parser.parse_directory()
            all_verses.extend(verses)
            parse_results["upanishads"] = {
                "verses_count": count,
                "status": "complete" if count > 0 else "no_files",
            }
            print(f"  Found {count} verses")

        # Save intermediate results
        tier1_dir = self.processed_dir / "tier1-essential"
        tier1_dir.mkdir(parents=True, exist_ok=True)

        intermediate_file = tier1_dir / "parsed_verses.json"
        with open(intermediate_file, "w", encoding="utf-8") as f:
            json.dump(all_verses, f, ensure_ascii=False, indent=2)

        print(f"\n  Total verses parsed: {len(all_verses)}")
        print(f"  Saved to: {intermediate_file}")

        return parse_results

    def format_all(self) -> dict[str, Any]:
        """Format and normalize all verses."""
        print("\n" + "=" * 60)
        print("PHASE 3: FORMATTING & NORMALIZATION")
        print("=" * 60)

        print("\n[1/3] Normalizing schema...")
        stats = normalize_directory(self.processed_dir, self.final_dir / "verses.json")

        print("\n[2/3] Enriching metadata...")
        enricher_stats = self._enrich_metadata(self.final_dir / "verses.json")

        print("\n[3/3] Deduplicating verses...")
        dedup_stats = self._deduplicate(self.final_dir / "verses.json")

        return {"normalization": stats, "enrichment": enricher_stats, "deduplication": dedup_stats}

    def _enrich_metadata(self, verses_file: Path) -> dict[str, Any]:
        """Enrich verses with additional metadata."""
        with open(verses_file, encoding="utf-8") as f:
            verses = json.load(f)

        enriched = MetadataEnricher.enrich_all(verses)

        # Save enriched version
        enriched_file = verses_file.parent / "verses_enriched.json"
        with open(enriched_file, "w", encoding="utf-8") as f:
            json.dump(enriched, f, ensure_ascii=False, indent=2)

        return {"total_verses": len(enriched), "output_file": str(enriched_file)}

    def _deduplicate(self, verses_file: Path) -> dict[str, Any]:
        """Deduplicate verses across sources."""
        with open(verses_file, encoding="utf-8") as f:
            verses = json.load(f)

        deduped, stats = deduplicate_verses(verses)

        # Save deduplicated version
        dedup_file = verses_file.parent / "verses_deduped.json"
        with open(dedup_file, "w", encoding="utf-8") as f:
            json.dump(deduped, f, ensure_ascii=False, indent=2)

        return {**stats, "output_file": str(dedup_file)}

    def validate(self) -> dict[str, Any]:
        """Validate final output."""
        print("\n" + "=" * 60)
        print("PHASE 4: VALIDATION")
        print("=" * 60)

        verses_file = self.final_dir / "verses.json"
        if not verses_file.exists():
            return {"status": "no_verses_file", "error": "verses.json not found"}

        validator = CorpusValidator()
        stats = validator.validate_file(verses_file)

        # Also check deduped version if it exists
        dedup_file = self.final_dir / "verses_deduped.json"
        if dedup_file.exists():
            print("\nValidating deduplicated version...")
            dedup_stats = validator.validate_file(dedup_file)
            stats["deduped_validation"] = dedup_stats

        validator.print_report(stats)
        return stats

    def export_metadata(self) -> None:
        """Export metadata about the corpus."""
        print("\n" + "=" * 60)
        print("EXPORTING METADATA")
        print("=" * 60)

        verses_file = self.final_dir / "verses.json"
        if not verses_file.exists():
            print("Warning: verses.json not found")
            return

        with open(verses_file, encoding="utf-8") as f:
            verses = json.load(f)

        # Generate statistics
        metadata = {
            "generated_date": datetime.now().isoformat(),
            "total_verses": len(verses),
            "by_source": {},
            "by_category": {},
            "by_tradition": {},
            "themes_used": set(),
            "life_domains_used": set(),
        }

        for verse in verses:
            # By source
            source = verse.get("source", {}).get("text", "Unknown")
            if source not in metadata["by_source"]:
                metadata["by_source"][source] = 0
            metadata["by_source"][source] += 1

            # By category
            category = verse.get("metadata", {}).get("category", "unknown")
            if category not in metadata["by_category"]:
                metadata["by_category"][category] = 0
            metadata["by_category"][category] += 1

            # By tradition
            tradition = verse.get("metadata", {}).get("tradition", "unknown")
            if tradition not in metadata["by_tradition"]:
                metadata["by_tradition"][tradition] = 0
            metadata["by_tradition"][tradition] += 1

            # Collect themes and domains
            metadata["themes_used"].update(verse.get("metadata", {}).get("themes", []))
            metadata["life_domains_used"].update(verse.get("metadata", {}).get("life_domains", []))

        # Convert sets to lists for JSON serialization
        metadata["themes_used"] = sorted(list(metadata["themes_used"]))
        metadata["life_domains_used"] = sorted(list(metadata["life_domains_used"]))

        # Save metadata
        metadata_file = self.final_dir / "metadata.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        print(f"Metadata saved to: {metadata_file}")
        print("\nCorpus statistics:")
        print(f"  Total verses: {metadata['total_verses']}")
        print(f"  Unique themes: {len(metadata['themes_used'])}")
        print(f"  Unique life domains: {len(metadata['life_domains_used'])}")
        print(f"  Sources: {len(metadata['by_source'])}")
        print(f"  Categories: {len(metadata['by_category'])}")

    def run_full_pipeline(self) -> dict[str, Any]:
        """Run the complete pipeline."""
        print("\n" + "╔" + "=" * 58 + "╗")
        print("║" + " " * 18 + "HINDU SCRIPTURE RAG PIPELINE" + " " * 13 + "║")
        print("╚" + "=" * 58 + "╝")

        results = {}

        # Phase 1: Download
        try:
            results["download"] = self.download_all()
        except Exception as e:
            print(f"Error in download phase: {e}")
            results["download"] = {"error": str(e)}

        # Phase 2: Parse
        try:
            results["parse"] = self.parse_all()
        except Exception as e:
            print(f"Error in parse phase: {e}")
            results["parse"] = {"error": str(e)}

        # Phase 3: Format
        try:
            results["format"] = self.format_all()
        except Exception as e:
            print(f"Error in format phase: {e}")
            results["format"] = {"error": str(e)}

        # Phase 4: Validate
        try:
            results["validation"] = self.validate()
        except Exception as e:
            print(f"Error in validation phase: {e}")
            results["validation"] = {"error": str(e)}

        # Export metadata
        try:
            self.export_metadata()
        except Exception as e:
            print(f"Error exporting metadata: {e}")

        # Print summary
        self._print_summary(results)

        return results

    def _print_summary(self, results: dict[str, Any]) -> None:
        """Print summary of pipeline execution."""
        print("\n" + "=" * 60)
        print("PIPELINE SUMMARY")
        print("=" * 60)

        if "validation" in results:
            val = results["validation"]
            if "total" in val:
                print("\nFinal statistics:")
                print(f"  Total verses: {val['total']}")
                print(f"  Valid verses: {val['valid']}")
                print(f"  Invalid verses: {val['invalid']}")

        print(f"\nOutput directory: {self.final_dir}")
        print("\nGenerated files:")
        for file in sorted(self.final_dir.glob("*.json")):
            size_mb = file.stat().st_size / 1024 / 1024
            print(f"  - {file.name} ({size_mb:.1f} MB)")

        print("\n✓ Pipeline complete!")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Hindu Scripture RAG Data Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full pipeline
  python main.py run

  # Only download
  python main.py download

  # Only parse
  python main.py parse

  # Validate existing data
  python main.py validate
        """,
    )

    parser.add_argument(
        "command",
        choices=["run", "download", "parse", "format", "validate"],
        default="run",
        nargs="?",
        help="Pipeline command to execute",
    )

    parser.add_argument(
        "--base-dir", default="~/hindu-scriptures-rag", help="Base directory for all operations"
    )

    parser.add_argument(
        "--parallel", action="store_true", help="Enable parallel processing where available"
    )

    args = parser.parse_args()
    base_dir = Path(args.base_dir).expanduser()

    orchestrator = PipelineOrchestrator(base_dir)

    if args.command == "run":
        orchestrator.run_full_pipeline()
    elif args.command == "download":
        orchestrator.download_all(parallel=args.parallel)
    elif args.command == "parse":
        orchestrator.parse_all()
    elif args.command == "format":
        orchestrator.format_all()
    elif args.command == "validate":
        orchestrator.validate()


if __name__ == "__main__":
    main()
