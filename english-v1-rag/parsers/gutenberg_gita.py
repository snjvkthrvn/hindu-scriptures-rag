"""Parse Bhagavad Gita from Gutenberg plain text (Edwin Arnold, The Song Celestial)."""

import re
from datetime import datetime, timezone
from pathlib import Path

ROMAN_TO_INT = {
    "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8,
    "IX": 9, "X": 10, "XI": 11, "XII": 12, "XIII": 13, "XIV": 14, "XV": 15,
    "XVI": 16, "XVII": 17, "XVIII": 18,
}

# Target window: ~200 words, overlap: ~50 words
_WINDOW_WORDS = 200
_OVERLAP_WORDS = 50


def _split_into_windows(text: str) -> list[str]:
    """Split text into ~200-word windows with ~50-word overlap."""
    words = text.split()
    if len(words) <= _WINDOW_WORDS:
        return [text]

    windows = []
    start = 0
    while start < len(words):
        end = start + _WINDOW_WORDS
        window = " ".join(words[start:end])
        windows.append(window)
        if end >= len(words):
            break
        start = end - _OVERLAP_WORDS
    return windows


def parse_arnold_gita(txt_path: Path) -> list[dict]:
    """Extract verses from Arnold's poetic Gita translation.

    Splits by chapter (CHAPTER I, II, ...) and by speaker blocks (Arjuna., Krishna., etc),
    then further splits each block into ~200-word windows with ~50-word overlap
    to produce ~200-300 chunks instead of 56.
    """
    text = txt_path.read_text(encoding="utf-8", errors="replace")

    # Skip Gutenberg header
    start_marker = "*** START OF THE PROJECT GUTENBERG"
    if start_marker in text:
        text = text.split(start_marker, 1)[1]

    # Find first CHAPTER I
    m0 = re.search(r"\n\s*CHAPTER\s+I\b", text, re.IGNORECASE)
    if not m0:
        return []
    text = text[m0.start():]

    verses = []
    # Find each chapter: "CHAPTER N" ... until "HERE ENDETH" or next "CHAPTER"
    chapter_pat = re.compile(
        r"\n\s*CHAPTER\s+([IVXLCDM]+)\s*\n",
        re.IGNORECASE,
    )
    for match in chapter_pat.finditer(text):
        chapter_roman = match.group(1).upper()
        chapter_num = ROMAN_TO_INT.get(chapter_roman, 0)
        if chapter_num < 1 or chapter_num > 18:
            continue

        start = match.end()
        # Find end: HERE ENDETH or next CHAPTER
        end_match = re.search(
            r"HERE ENDETH CHAPTER[^\n]*\n|(?=\n\s*CHAPTER\s+[IVXLCDM]+\s*\n)",
            text[start:],
            re.IGNORECASE,
        )
        chunk = text[start: start + end_match.start()] if end_match else text[start:]

        # Split by speaker blocks: "  Arjuna.\n", "  Krishna.\n", etc.
        blocks = re.split(r"\n\s{2,}(?:Dhritirashtra|Sanjaya|Arjuna|Krishna)\.\s*\n", chunk, flags=re.IGNORECASE)
        verse_in_chapter = 0
        for block in blocks:
            block = re.sub(r"\s+", " ", block).strip()
            if len(block) < 25:
                continue

            # Further split into ~200-word windows with overlap
            windows = _split_into_windows(block)
            for window in windows:
                if len(window) < 25:
                    continue
                verse_in_chapter += 1
                verses.append({
                    "id": f"bg_arnold_{chapter_num}_{verse_in_chapter}",
                    "source": {
                        "text": "Bhagavad Gita (Arnold)",
                        "chapter": chapter_num,
                        "chapter_name": f"Chapter {chapter_num}",
                        "verse": verse_in_chapter,
                    },
                    "content": {
                        "sanskrit": "",
                        "transliteration": "",
                        "translation": window,
                    },
                    "metadata": {
                        "category": "smriti",
                        "tradition": "vedanta",
                        "themes": ["bhagavad_gita", "karma", "dharma"],
                    },
                    "commentaries": [],
                    "provenance": {
                        "download_source": "gutenberg",
                        "original_url": "https://www.gutenberg.org/ebooks/2388",
                        "license": "Public Domain",
                        "translator": "Sir Edwin Arnold",
                        "processed_date": datetime.now(timezone.utc).isoformat(),
                    },
                })

    return verses
