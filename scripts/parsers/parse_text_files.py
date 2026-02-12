"""Parse plain text scripture files into unified schema."""

from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime
import re
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.unicode_utils import normalize_devanagari
from utils.verse_detector import VerseDetector


class TextFileParser:
    """Parse plain text scripture files."""

    def __init__(self):
        """Initialize parser."""
        self.verse_detector = VerseDetector()

    def parse_gutenberg_txt(
        self,
        txt_file: Path,
        title: str,
        category: str = 'prakarana'
    ) -> List[Dict[str, Any]]:
        """
        Parse Project Gutenberg TXT file.

        Removes header/footer and attempts to identify verses.

        Returns:
            List of verse dictionaries
        """
        verses = []

        try:
            with open(txt_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Remove Gutenberg header/footer
            content = self._remove_gutenberg_boilerplate(content)

            # Split into logical sections
            sections = self._split_into_sections(content)

            verse_num = 0
            for section in sections:
                section = section.strip()
                if not section or len(section) < 50:
                    continue

                verse_num += 1

                # Try to extract verse and translation
                lines = section.split('\n')
                sanskrit = ''
                translation = ''

                # Heuristic: look for Devanagari text
                for line in lines:
                    if any(ord(c) in range(0x0900, 0x097F) for c in line):
                        sanskrit = line.strip()
                        break

                # Take remaining content as translation
                if sanskrit:
                    translation = ' '.join(l.strip() for l in lines if l.strip() and l.strip() != sanskrit)
                else:
                    translation = section

                if translation and len(translation) > 20:
                    verse_id = f"{title.lower().replace(' ', '_')}_{verse_num}"

                    verses.append({
                        'id': verse_id,
                        'source': {
                            'text': title,
                            'chapter': None,
                            'chapter_name': None,
                            'verse': verse_num,
                            'section': None
                        },
                        'content': {
                            'sanskrit': normalize_devanagari(sanskrit),
                            'transliteration': '',
                            'translation': translation,
                            'word_by_word': {}
                        },
                        'metadata': {
                            'category': category,
                            'tradition': 'vedanta',
                            'themes': [],
                            'philosophical_schools': []
                        },
                        'commentaries': [],
                        'provenance': {
                            'download_source': 'gutenberg',
                            'original_url': f'https://www.gutenberg.org',
                            'license': 'Public Domain',
                            'processed_date': datetime.now().isoformat()
                        }
                    })

        except Exception as e:
            print(f"Error parsing {txt_file}: {e}")

        return verses

    def parse_plain_text(
        self,
        txt_file: Path,
        title: str,
        category: str = 'prakarana'
    ) -> List[Dict[str, Any]]:
        """
        Parse generic plain text scripture file.

        Attempts to detect verse boundaries using markers.

        Returns:
            List of verse dictionaries
        """
        verses = []

        try:
            with open(txt_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Detect verse markers
            markers = self.verse_detector.detect_all_markers(content)

            if markers:
                # Split by markers
                last_pos = 0
                for marker in markers:
                    text_before = content[last_pos:marker.position].strip()
                    if text_before and len(text_before) > 20:
                        verse_id = f"{title.lower().replace(' ', '_')}_{marker.verse}"
                        verses.append(self._create_verse(
                            verse_id, title, marker.verse, text_before, category
                        ))
                    last_pos = marker.position + len(marker.text)

                # Add remaining text
                remaining = content[last_pos:].strip()
                if remaining and len(remaining) > 20:
                    verse_id = f"{title.lower().replace(' ', '_')}_{len(verses)}"
                    verses.append(self._create_verse(
                        verse_id, title, len(verses), remaining, category
                    ))
            else:
                # No markers found, split by paragraphs
                paragraphs = content.split('\n\n')
                for idx, para in enumerate(paragraphs, 1):
                    para = para.strip()
                    if para and len(para) > 50:
                        verse_id = f"{title.lower().replace(' ', '_')}_{idx}"
                        verses.append(self._create_verse(
                            verse_id, title, idx, para, category
                        ))

        except Exception as e:
            print(f"Error parsing {txt_file}: {e}")

        return verses

    def _create_verse(
        self,
        verse_id: str,
        title: str,
        verse_num: int,
        text: str,
        category: str
    ) -> Dict[str, Any]:
        """Create a verse dictionary from raw text."""
        # Heuristic: Devanagari text is likely Sanskrit
        sanskrit = ''
        translation = text

        for line in text.split('\n'):
            devanagari_chars = sum(1 for c in line if ord(c) in range(0x0900, 0x097F))
            if devanagari_chars > len(line) * 0.5:  # More than 50% Devanagari
                sanskrit = line.strip()
                translation = text.replace(sanskrit, '').strip()
                break

        return {
            'id': verse_id,
            'source': {
                'text': title,
                'chapter': None,
                'chapter_name': None,
                'verse': verse_num,
                'section': None
            },
            'content': {
                'sanskrit': normalize_devanagari(sanskrit),
                'transliteration': '',
                'translation': translation,
                'word_by_word': {}
            },
            'metadata': {
                'category': category,
                'tradition': 'vedanta',
                'themes': [],
                'philosophical_schools': []
            },
            'commentaries': [],
            'provenance': {
                'download_source': 'text_file',
                'original_url': '',
                'license': 'Unknown',
                'processed_date': datetime.now().isoformat()
            }
        }

    @staticmethod
    def _remove_gutenberg_boilerplate(text: str) -> str:
        """Remove Project Gutenberg header and footer."""
        # Remove header (before "START OF PROJECT GUTENBERG")
        if '***START OF' in text:
            text = text.split('***START OF')[1]
        if '***START OF THE' in text:
            text = text.split('***START OF THE')[1]

        # Remove footer (after "END OF PROJECT GUTENBERG")
        if '***END OF' in text:
            text = text.split('***END OF')[0]

        # Remove licensing text at end
        if 'Project Gutenberg' in text:
            lines = text.split('\n')
            for i, line in enumerate(lines):
                if 'Project Gutenberg' in line and i > len(lines) * 0.8:
                    text = '\n'.join(lines[:i])
                    break

        return text

    @staticmethod
    def _split_into_sections(text: str, min_length: int = 100) -> List[str]:
        """
        Split text into logical sections.

        Uses multiple approaches: verse markers, double newlines, chapter markers.
        """
        # Try verse marker splitting first
        if '॥' in text:
            sections = text.split('॥')
        elif '---' in text:
            sections = text.split('---')
        else:
            # Split by double newlines
            sections = text.split('\n\n')

        # Filter out very short sections
        return [s.strip() for s in sections if len(s.strip()) >= min_length]


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Parse text scripture files")
    parser.add_argument(
        'input_file',
        help='Path to text file to parse'
    )
    parser.add_argument(
        '--title',
        required=True,
        help='Title of the scripture'
    )
    parser.add_argument(
        '--category',
        default='prakarana',
        help='Category (shruti, smriti, itihasa, purana, prakarana, darshana)'
    )
    parser.add_argument(
        '--output',
        help='Output JSON file'
    )

    args = parser.parse_args()
    input_file = Path(args.input_file).expanduser()

    if not input_file.exists():
        print(f"Error: File not found: {input_file}")
        return

    parser_obj = TextFileParser()
    verses = parser_obj.parse_plain_text(input_file, args.title, args.category)

    print(f"Parsed {len(verses)} verses")

    if args.output:
        import json
        output_file = Path(args.output).expanduser()
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(verses, f, ensure_ascii=False, indent=2)
        print(f"Saved to: {output_file}")


if __name__ == '__main__':
    main()
