"""Verse boundary detection and numbering utilities."""

import re
from typing import List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class VerseMarker:
    """Represents a detected verse marker."""
    text: str
    position: int
    format_type: str  # 'devanagari', 'decimal', 'roman', 'bracket', etc.
    chapter: Optional[int] = None
    verse: Optional[int] = None


class VerseDetector:
    """Detect verse boundaries in various formats."""

    def __init__(self):
        """Initialize verse patterns."""
        # Devanagari verse markers: ॥1॥, ॥१॥
        self.devanagari_pattern = r'॥([०-९]+)॥'

        # Decimal verse markers: 1.1, 1:1, [1], (1), etc.
        self.decimal_pattern = r'(?:^|\s)(\d+)[:.]\s*(\d+)(?:\s|$)'
        self.bracket_pattern = r'\[(\d+)\]'
        self.paren_pattern = r'\((\d+)\)'

        # Roman numerals: I, II, III, etc.
        self.roman_pattern = r'(?:^|\s)([ivxlcdm]+)(?:\s|$)'

    def detect_devanagari_markers(self, text: str) -> List[VerseMarker]:
        """Detect Devanagari verse markers (॥)."""
        markers = []
        for match in re.finditer(self.devanagari_pattern, text):
            # Convert Devanagari digit to integer
            verse_text = match.group(1)
            try:
                verse_num = self._devanagari_to_int(verse_text)
                markers.append(VerseMarker(
                    text=match.group(0),
                    position=match.start(),
                    format_type='devanagari',
                    verse=verse_num
                ))
            except ValueError:
                pass

        return markers

    def detect_decimal_markers(self, text: str) -> List[VerseMarker]:
        """Detect decimal verse markers (1.1, 1:1)."""
        markers = []
        for match in re.finditer(self.decimal_pattern, text, re.MULTILINE):
            try:
                chapter = int(match.group(1))
                verse = int(match.group(2))
                markers.append(VerseMarker(
                    text=match.group(0),
                    position=match.start(),
                    format_type='decimal',
                    chapter=chapter,
                    verse=verse
                ))
            except ValueError:
                pass

        return markers

    def detect_bracket_markers(self, text: str) -> List[VerseMarker]:
        """Detect bracket verse markers [1]."""
        markers = []
        for match in re.finditer(self.bracket_pattern, text):
            try:
                verse = int(match.group(1))
                markers.append(VerseMarker(
                    text=match.group(0),
                    position=match.start(),
                    format_type='bracket',
                    verse=verse
                ))
            except ValueError:
                pass

        return markers

    def detect_all_markers(self, text: str) -> List[VerseMarker]:
        """Detect all verse marker types."""
        all_markers = []
        all_markers.extend(self.detect_devanagari_markers(text))
        all_markers.extend(self.detect_decimal_markers(text))
        all_markers.extend(self.detect_bracket_markers(text))

        # Sort by position
        return sorted(all_markers, key=lambda m: m.position)

    def split_by_verses(self, text: str) -> List[Tuple[str, Optional[VerseMarker]]]:
        """
        Split text into verses based on detected markers.

        Returns:
            List of (verse_text, verse_marker) tuples
        """
        markers = self.detect_all_markers(text)
        if not markers:
            return [(text, None)]

        verses = []
        last_pos = 0

        for i, marker in enumerate(markers):
            # Extract text before this marker
            verse_text = text[last_pos:marker.position].strip()
            if verse_text:
                verses.append((verse_text, None))

            # Move past the marker
            last_pos = marker.position + len(marker.text)

        # Add remaining text
        remaining = text[last_pos:].strip()
        if remaining:
            verses.append((remaining, None))

        return verses

    @staticmethod
    def _devanagari_to_int(devanagari_str: str) -> int:
        """Convert Devanagari number string to integer."""
        mapping = {
            '०': '0', '१': '1', '२': '2', '३': '3', '४': '4',
            '५': '5', '६': '6', '७': '7', '८': '8', '९': '9'
        }

        converted = ''.join(mapping.get(char, char) for char in devanagari_str)
        return int(converted)

    @staticmethod
    def _int_to_devanagari(num: int) -> str:
        """Convert integer to Devanagari number string."""
        mapping = {
            '0': '०', '1': '१', '2': '२', '3': '३', '4': '४',
            '5': '५', '6': '६', '7': '७', '8': '८', '9': '९'
        }

        return ''.join(mapping.get(char, char) for char in str(num))


def is_verse_boundary(line: str) -> bool:
    """
    Check if a line appears to be a verse boundary line.

    Args:
        line: Text line to check

    Returns:
        True if line looks like a verse marker
    """
    line = line.strip()

    # Check for various verse marker patterns
    patterns = [
        r'^॥.*॥$',  # Devanagari markers
        r'^\d+\.\d+$',  # 1.1 format
        r'^\[\d+\]$',  # [1] format
        r'^\(\d+\)$',  # (1) format
        r'^verse\s+\d+', # "verse 1"
        r'^sloka\s+\d+', # "sloka 1"
    ]

    return any(re.match(pattern, line, re.IGNORECASE) for pattern in patterns)
