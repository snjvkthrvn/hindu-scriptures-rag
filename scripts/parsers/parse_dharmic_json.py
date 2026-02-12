"""Parse DharmicData JSON format into unified schema."""

import json
from pathlib import Path
from typing import List, Dict, Any, Tuple
from datetime import datetime
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.unicode_utils import normalize_devanagari


class DharmicDataParser:
    """Parse JSON data from DharmicData repository."""

    def __init__(self, source_dir: Path):
        """Initialize parser with source directory."""
        self.source_dir = Path(source_dir)

    def parse_gita(self, json_file: Path) -> List[Dict[str, Any]]:
        """
        Parse Bhagavad Gita JSON.

        Returns:
            List of verse dictionaries in unified schema
        """
        verses = []

        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Handle different possible JSON structures
            if isinstance(data, list):
                chapters_data = data
            elif isinstance(data, dict) and 'chapters' in data:
                chapters_data = data['chapters']
            else:
                chapters_data = [data]

            for chapter_idx, chapter_data in enumerate(chapters_data, 1):
                chapter_num = chapter_data.get('chapter', chapter_idx)
                chapter_name = chapter_data.get('name', f"Chapter {chapter_num}")

                verses_data = chapter_data.get('verses', [])
                if not isinstance(verses_data, list):
                    continue

                for verse_data in verses_data:
                    verse_num = verse_data.get('verse', 0)

                    # Extract content
                    sanskrit = normalize_devanagari(
                        verse_data.get('text', '').strip()
                    )
                    transliteration = verse_data.get('transliteration', '').strip()
                    translation = verse_data.get('translation', '').strip()

                    # Skip empty verses
                    if not sanskrit or not translation:
                        continue

                    verse_id = f"bg_{chapter_num}_{verse_num}"

                    verses.append({
                        'id': verse_id,
                        'source': {
                            'text': 'Bhagavad Gita',
                            'chapter': chapter_num,
                            'chapter_name': chapter_name,
                            'verse': verse_num,
                            'section': None
                        },
                        'content': {
                            'sanskrit': sanskrit,
                            'transliteration': transliteration,
                            'translation': translation,
                            'word_by_word': {}
                        },
                        'metadata': {
                            'category': 'smriti',
                            'tradition': 'vedanta',
                            'themes': self._extract_themes_gita(chapter_num),
                            'philosophical_schools': ['advaita', 'dvaita', 'vishishtadvaita']
                        },
                        'commentaries': [],
                        'provenance': {
                            'download_source': 'dharmic-data',
                            'original_url': 'https://github.com/bhavykhatri/DharmicData',
                            'license': 'ODbL-1.0',
                            'processed_date': datetime.now().isoformat()
                        }
                    })

        except json.JSONDecodeError as e:
            print(f"JSON decode error in {json_file}: {e}")
        except Exception as e:
            print(f"Error parsing {json_file}: {e}")

        return verses

    def parse_mahabharata(self, json_file: Path) -> List[Dict[str, Any]]:
        """
        Parse Mahabharata JSON.

        Returns:
            List of verse dictionaries in unified schema
        """
        verses = []

        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Extract parvas (books)
            parvas = data if isinstance(data, list) else data.get('parvas', [])

            for parva_data in parvas:
                parva_name = parva_data.get('name', 'Unknown Parva')

                # Handle verses at parva level or in sub-sections
                verses_data = parva_data.get('verses', [])
                if not isinstance(verses_data, list):
                    verses_data = [verses_data] if verses_data else []

                for verse_idx, verse_data in enumerate(verses_data, 1):
                    sanskrit = normalize_devanagari(
                        verse_data.get('text', '').strip()
                    )
                    translation = verse_data.get('translation', '').strip()

                    if not sanskrit or not translation:
                        continue

                    verse_id = f"maha_{parva_name.lower().replace(' ', '_')}_{verse_idx}"

                    verses.append({
                        'id': verse_id,
                        'source': {
                            'text': 'Mahabharata',
                            'chapter': None,
                            'chapter_name': parva_name,
                            'verse': verse_idx,
                            'section': None
                        },
                        'content': {
                            'sanskrit': sanskrit,
                            'transliteration': '',
                            'translation': translation,
                            'word_by_word': {}
                        },
                        'metadata': {
                            'category': 'itihasa',
                            'tradition': 'common',
                            'themes': ['dharma', 'war', 'duty', 'morality'],
                            'philosophical_schools': []
                        },
                        'commentaries': [],
                        'provenance': {
                            'download_source': 'dharmic-data',
                            'original_url': 'https://github.com/bhavykhatri/DharmicData',
                            'license': 'ODbL-1.0',
                            'processed_date': datetime.now().isoformat()
                        }
                    })

        except Exception as e:
            print(f"Error parsing Mahabharata JSON: {e}")

        return verses

    def parse_ramayana(self, json_file: Path) -> List[Dict[str, Any]]:
        """
        Parse Ramayana JSON.

        Returns:
            List of verse dictionaries in unified schema
        """
        verses = []

        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Extract kandas (books)
            kandas = data if isinstance(data, list) else data.get('kandas', [])

            for kanda_data in kandas:
                kanda_name = kanda_data.get('name', 'Unknown Kanda')
                kanda_num = kanda_data.get('kanda', 1)

                verses_data = kanda_data.get('verses', [])
                if not isinstance(verses_data, list):
                    verses_data = [verses_data] if verses_data else []

                for verse_idx, verse_data in enumerate(verses_data, 1):
                    sanskrit = normalize_devanagari(
                        verse_data.get('text', '').strip()
                    )
                    translation = verse_data.get('translation', '').strip()

                    if not sanskrit or not translation:
                        continue

                    verse_id = f"rama_{kanda_num}_{verse_idx}"

                    verses.append({
                        'id': verse_id,
                        'source': {
                            'text': 'Ramayana',
                            'chapter': kanda_num,
                            'chapter_name': kanda_name,
                            'verse': verse_idx,
                            'section': None
                        },
                        'content': {
                            'sanskrit': sanskrit,
                            'transliteration': '',
                            'translation': translation,
                            'word_by_word': {}
                        },
                        'metadata': {
                            'category': 'itihasa',
                            'tradition': 'common',
                            'themes': ['dharma', 'devotion', 'virtue', 'duty'],
                            'philosophical_schools': []
                        },
                        'commentaries': [],
                        'provenance': {
                            'download_source': 'dharmic-data',
                            'original_url': 'https://github.com/bhavykhatri/DharmicData',
                            'license': 'ODbL-1.0',
                            'processed_date': datetime.now().isoformat()
                        }
                    })

        except Exception as e:
            print(f"Error parsing Ramayana JSON: {e}")

        return verses

    @staticmethod
    def _extract_themes_gita(chapter: int) -> List[str]:
        """Extract themes based on Gita chapter."""
        chapter_themes = {
            1: ['arjuna_doubt', 'dharma', 'dilemma'],
            2: ['sankhya', 'karma_yoga', 'detachment'],
            3: ['action', 'karma', 'duty'],
            4: ['knowledge', 'yoga', 'renunciation'],
            5: ['sannyasa', 'renunciation', 'action'],
            6: ['meditation', 'yoga', 'mind'],
            7: ['knowledge', 'brahman', 'nature'],
            8: ['brahman', 'yoga', 'liberation'],
            9: ['bhakti', 'devotion', 'surrender'],
            10: ['vibhuti', 'divine_manifestations', 'glory'],
            11: ['vision', 'divine_form', 'awe'],
            12: ['devotion', 'bhakti', 'faith'],
            13: ['field', 'knowledge', 'ignorance'],
            14: ['gunas', 'qualities', 'nature'],
            15: ['sacred_fig', 'knowledge', 'vedas'],
            16: ['divine_and_asura', 'virtues', 'vices'],
            17: ['faith', 'sacrifice', 'worship'],
            18: ['renunciation', 'liberation', 'duty']
        }
        return chapter_themes.get(chapter, ['gita', 'yoga', 'knowledge'])

    def parse_directory(self) -> Tuple[int, List[Dict[str, Any]]]:
        """
        Parse all JSON files in the DharmicData directory.

        Returns:
            (total_verses, verses_list)
        """
        all_verses = []

        # Look for known files
        files_to_parse = [
            ('gita.json', self.parse_gita),
            ('bhagavad_gita.json', self.parse_gita),
            ('mahabharata.json', self.parse_mahabharata),
            ('ramayana.json', self.parse_ramayana),
        ]

        for filename, parser_func in files_to_parse:
            filepath = self.source_dir / filename
            if filepath.exists():
                print(f"Parsing {filename}...")
                verses = parser_func(filepath)
                all_verses.extend(verses)
                print(f"  Found {len(verses)} verses")

        return len(all_verses), all_verses


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Parse DharmicData JSON files")
    parser.add_argument(
        'input_dir',
        default='~/hindu-scriptures-rag/raw/dharmic-data',
        nargs='?',
        help='Path to DharmicData directory'
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

    parser = DharmicDataParser(input_dir)
    total, verses = parser.parse_directory()

    print(f"\n{'='*60}")
    print(f"Parsed {total} verses")

    # Save to JSON
    output_file = output_dir / 'dharmic_data.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(verses, f, ensure_ascii=False, indent=2)

    print(f"Saved to: {output_file}")


if __name__ == '__main__':
    main()
