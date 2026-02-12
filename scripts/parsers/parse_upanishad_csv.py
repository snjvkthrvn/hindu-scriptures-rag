"""Parse Upanishad CSV format into unified schema."""

import csv
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple
from datetime import datetime
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.unicode_utils import normalize_devanagari


class UpanishadCSVParser:
    """Parse CSV data from indian-scriptures repository."""

    # Map CSV filenames to Upanishad metadata
    UPANISHADS = {
        'isha_upanishad.csv': {
            'title': 'Isha Upanishad',
            'category': 'shruti',
            'themes': ['atman', 'brahman', 'non-duality'],
            'verses_per_chapter': 18
        },
        'kena_upanishad.csv': {
            'title': 'Kena Upanishad',
            'category': 'shruti',
            'themes': ['brahman', 'knowledge', 'inquiry'],
            'verses_per_chapter': 4
        },
        'katha_upanishad.csv': {
            'title': 'Katha Upanishad',
            'category': 'shruti',
            'themes': ['death', 'knowledge', 'yama', 'atman'],
            'verses_per_chapter': 29
        },
        'prashna_upanishad.csv': {
            'title': 'Prashna Upanishad',
            'category': 'shruti',
            'themes': ['questions', 'brahman', 'prana'],
            'verses_per_chapter': 6
        },
        'mundaka_upanishad.csv': {
            'title': 'Mundaka Upanishad',
            'category': 'shruti',
            'themes': ['knowledge', 'brahman', 'meditation'],
            'verses_per_chapter': 34
        },
        'mandukya_upanishad.csv': {
            'title': 'Mandukya Upanishad',
            'category': 'shruti',
            'themes': ['om', 'atman', 'brahman'],
            'verses_per_chapter': 12
        },
        'taittiriya_upanishad.csv': {
            'title': 'Taittiriya Upanishad',
            'category': 'shruti',
            'themes': ['brahman', 'ananda', 'bliss'],
            'verses_per_chapter': 27
        },
        'aitareya_upanishad.csv': {
            'title': 'Aitareya Upanishad',
            'category': 'shruti',
            'themes': ['brahman', 'creation', 'atman'],
            'verses_per_chapter': 12
        },
        'chandogya_upanishad.csv': {
            'title': 'Chandogya Upanishad',
            'category': 'shruti',
            'themes': ['om', 'brahman', 'meditation'],
            'verses_per_chapter': 41
        },
        'brihadaranyaka_upanishad.csv': {
            'title': 'Brihadaranyaka Upanishad',
            'category': 'shruti',
            'themes': ['brahman', 'atman', 'knowledge'],
            'verses_per_chapter': 70
        },
        'svetasvatara_upanishad.csv': {
            'title': 'Svetasvatara Upanishad',
            'category': 'shruti',
            'themes': ['brahman', 'shiva', 'yoga'],
            'verses_per_chapter': 23
        }
    }

    # Alternate filenames in indian-scriptures repo (data/processed/upanishads/)
    ALTERNATE_FILENAMES = {
        'Isha Upanishad': ['isavasya_upanishad.csv'],
        'Prashna Upanishad': ['prasna_upanishad.csv'],
        'Svetasvatara Upanishad': ['svetashvatra_upanishad.csv'],
        'Aitareya Upanishad': ['aitereya_upanishad.csv'],
    }

    def __init__(self, source_dir: Path):
        """Initialize parser with source directory."""
        self.source_dir = Path(source_dir)
        # Look in data/processed/upanishads/ if it exists (indian-scriptures layout)
        upanishads_subdir = self.source_dir / 'data' / 'processed' / 'upanishads'
        self.csv_dir = upanishads_subdir if upanishads_subdir.exists() else self.source_dir

    def parse_upanishad_csv(
        self,
        csv_file: Path,
        upanishad_info: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Parse a single Upanishad CSV file.

        CSV expected columns: verse_number, sanskrit, transliteration, translation

        Returns:
            List of verse dictionaries in unified schema
        """
        verses = []
        title = upanishad_info['title']
        print(f"  Parsing {title}...")

        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)

                if reader.fieldnames is None:
                    print(f"    Warning: Empty CSV file")
                    return verses

                for row_idx, row in enumerate(reader, 1):
                    # Extract fields (handle different column names)
                    # indian-scriptures format: title, mantra, number
                    verse_num = (row.get('number') or row.get('verse_number') or
                                row.get('verse') or str(row_idx))
                    mantra = (row.get('mantra') or row.get('sanskrit') or
                              row.get('text') or '').strip()
                    sanskrit = mantra
                    transliteration = (row.get('transliteration') or '').strip()
                    translation = (row.get('translation') or row.get('english') or '').strip()

                    # indian-scriptures has mantra but no translation - use sanskrit for searchability
                    if not translation and sanskrit:
                        translation = sanskrit

                    # Normalize
                    sanskrit = normalize_devanagari(sanskrit)

                    # Skip empty rows
                    if not sanskrit:
                        continue

                    try:
                        verse_num_int = int(verse_num)
                    except (ValueError, TypeError):
                        # Extract first number from "।। 1.1.1 ।।" or "1.1.2" format
                        match = re.search(r'(\d+)', str(verse_num))
                        verse_num_int = int(match.group(1)) if match else row_idx

                    verse_id = f"upanishad_{title.lower().replace(' ', '_')}_{verse_num_int}"

                    verses.append({
                        'id': verse_id,
                        'source': {
                            'text': title,
                            'chapter': None,
                            'chapter_name': title,
                            'verse': verse_num_int,
                            'section': None
                        },
                        'content': {
                            'sanskrit': sanskrit,
                            'transliteration': transliteration,
                            'translation': translation,
                            'word_by_word': {}
                        },
                        'metadata': {
                            'category': upanishad_info['category'],
                            'tradition': 'vedanta',
                            'themes': upanishad_info['themes'],
                            'philosophical_schools': ['advaita', 'dvaita', 'vishishtadvaita']
                        },
                        'commentaries': [],
                        'provenance': {
                            'download_source': 'indian-scriptures',
                            'original_url': 'https://github.com/hrgupta/indian-scriptures',
                            'license': 'CC-BY-4.0',
                            'processed_date': datetime.now().isoformat()
                        }
                    })

        except csv.Error as e:
            print(f"    CSV error in {csv_file}: {e}")
        except Exception as e:
            print(f"    Error parsing {csv_file}: {e}")

        print(f"    Found {len(verses)} verses")
        return verses

    def parse_directory(self) -> Tuple[int, List[Dict[str, Any]]]:
        """
        Parse all Upanishad CSV files in the directory.

        Returns:
            (total_verses, verses_list)
        """
        all_verses = []
        parsed_titles = set()  # Avoid duplicates

        for filename, upanishad_info in self.UPANISHADS.items():
            title = upanishad_info['title']
            if title in parsed_titles:
                continue
            filepath = self.csv_dir / filename
            if filepath.exists():
                verses = self.parse_upanishad_csv(filepath, upanishad_info)
                all_verses.extend(verses)
                parsed_titles.add(title)
            else:
                # Try alternate filenames (e.g. isavasya for Isha, prasna for Prashna)
                alts = self.ALTERNATE_FILENAMES.get(title, [])
                for alt in alts:
                    alt_path = self.csv_dir / alt
                    if alt_path.exists():
                        print(f"  Found alternate file: {alt}")
                        verses = self.parse_upanishad_csv(alt_path, upanishad_info)
                        all_verses.extend(verses)
                        parsed_titles.add(title)
                        break
                if title not in parsed_titles:
                    # Fallback: glob by title
                    for candidate in self.csv_dir.glob(f"*{title.lower().replace(' ', '_')}*"):
                        if candidate.is_file() and candidate.suffix == '.csv':
                            print(f"  Found file: {candidate.name}")
                            verses = self.parse_upanishad_csv(candidate, upanishad_info)
                            all_verses.extend(verses)
                            parsed_titles.add(title)
                            break

        return len(all_verses), all_verses


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Parse Upanishad CSV files")
    parser.add_argument(
        'input_dir',
        default='~/hindu-scriptures-rag/raw/indian-scriptures',
        nargs='?',
        help='Path to indian-scriptures directory'
    )
    parser.add_argument(
        '--output',
        default='~/hindu-scriptures-rag/processed/tier1-essential',
        help='Output directory for processed verses'
    )

    args = parser.parse_args()
    input_dir = Path(args.input_dir).expanduser()
    output_dir = Path(args.output).expanduser()

    if not input_dir.exists():
        print(f"Error: Input directory not found: {input_dir}")
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    parser_obj = UpanishadCSVParser(input_dir)
    total, verses = parser_obj.parse_directory()

    print(f"\n{'='*60}")
    print(f"Parsed {total} verses from {len(parser_obj.UPANISHADS)} Upanishads")

    # Save to JSON
    import json
    output_file = output_dir / 'upanishads.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(verses, f, ensure_ascii=False, indent=2)

    print(f"Saved to: {output_file}")


if __name__ == '__main__':
    main()
