#!/usr/bin/env python3
"""Download Ralph T. H. Griffith's Texts of the White Yajurveda (1899) from
archive.org's OCR'd plain-text version.

The PDF/scan is at archive.org/details/textswhiteyajur00grifgoog; the OCR
text is at archive.org/download/<id>/<id>_djvu.txt. Quality varies — common
OCR drift includes "BOOR" for "BOOK", "TffB" for "THE", garbled diacritics
on Sanskrit transliterations. We extract what we can with conservative
heuristics and accept partial coverage.

Format observed:
  - Front matter: title page, preface, table of contents
  - Translation body: 40 "BOOK <Roman>." headings, each followed by
    numbered verses 1, 2, 3, ... at line starts
  - Page headers like "[BOOK I." or "[BOOR L" recur at the top of each page
  - Footnotes interleaved in italics/smaller type (some leak into verses)

Strategy:
  1. Fetch djvu.txt once
  2. Find the actual translation start (first "BOOK I." that's followed
     by a real verse "1 <text>" within a few hundred chars, NOT the TOC
     "BOOK I." which is followed by chapter-name + page-number lines)
  3. Split body by BOOK markers; for each book, find numbered-verse starts
  4. Aggregate multi-line verses until next number or next book
  5. Aim for the canonical Madhyandina structure (40 books, ~1975 verses)

Output: raw/wikisource/yajurveda_griffith.json — main-corpus-aligned
schema with ids yv_madhyadina_<adhyaya>_<verse> matching the YV
main-corpus ids minted by the fixed parse_yajurveda.

Usage:
    PYTHONUTF8=1 python scripts/downloaders/download_archive_griffith_yv.py
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_FILE = PROJECT_ROOT / "raw" / "wikisource" / "yajurveda_griffith.json"
CACHE_FILE = PROJECT_ROOT / "raw" / "wikisource" / "_griffith_yv_djvu.txt"

ARCHIVE_ID = "textswhiteyajur00grifgoog"
DJVU_URL = f"https://archive.org/download/{ARCHIVE_ID}/{ARCHIVE_ID}_djvu.txt"
USER_AGENT = "hindu-scriptures-rag/0.1 (research, contact: sanjeevkathiravanpro@gmail.com)"


# ────────────────────────────────────────────────────────────────────────────
# Fetch (with on-disk cache so we don't keep re-downloading 862KB)

def fetch_djvu() -> str:
    if CACHE_FILE.exists():
        print(f"  (using cached djvu.txt from {CACHE_FILE.relative_to(PROJECT_ROOT)})")
        return CACHE_FILE.read_text(encoding="utf-8", errors="replace")
    print(f"  Fetching {DJVU_URL} ...")
    req = Request(DJVU_URL, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=120) as r:
        data = r.read()
    text = data.decode("utf-8", errors="replace")
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(text, encoding="utf-8")
    print(f"  Cached {len(data):,} bytes → {CACHE_FILE.relative_to(PROJECT_ROOT)}")
    return text


# ────────────────────────────────────────────────────────────────────────────
# ────────────────────────────────────────────────────────────────────────────
# Roman numerals and English Ordinals

ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}


def roman_to_int(s: str) -> int | None:
    s = s.upper()
    if not s or not all(c in ROMAN_VALUES for c in s):
        return None
    total = 0
    for i, ch in enumerate(s):
        v = ROMAN_VALUES[ch]
        nxt = ROMAN_VALUES.get(s[i + 1]) if i + 1 < len(s) else 0
        total += -v if nxt > v else v
    return total


ORDINALS_MAP = {
    "FIRST": 1, "SECOND": 2, "THIRD": 3, "FOURTH": 4, "FIFTH": 5, "SIXTH": 6, "SEVENTH": 7, "EIGHTH": 8, "NINTH": 9, "TENTH": 10,
    "ELEVENTH": 11, "TWELFTH": 12, "THIRTEENTH": 13, "FOURTEENTH": 14, "FIFTEENTH": 15, "SIXTEENTH": 16, "SEVENTEENTH": 17,
    "EIGHTEENTH": 18, "NINETEENTH": 19, "TWENTIETH": 20, "TWENTYFIRST": 21, "TWENTYSECOND": 22, "TWENTYTHIRD": 23, "TWENTYTHIR": 23, "TWENTYTHIRI": 23,
    "TWENTYFOURTH": 24, "TWENTYFOUKTB": 24, "TWENTYFIFTH": 25, "TWENTYSIXTH": 26, "TWENTYSEVENTH": 27, "TWENTYEIGHTH": 28, "TWENTYNINTH": 29,
    "THIRTIETH": 30, "THIRTYFIRST": 31, "THIRTYSECOND": 32, "THIRTY SECOND": 32, "THIRTYTHIRD": 33, "THIRTYFOURTH": 34, "THIRTYPOURTTF": 34, "THIRTYPOURTT": 34,
    "THIRTYFIFTH": 35, "THIRTYSIXTH": 36, "THIRTYSEVENTH": 37, "THIRTYSSEVENTH": 37, "THIRTYEIGHTH": 38, "THIRTYEIRGFRTF": 38, "THIRTYEIRGF": 38, "THIRTYNINTH": 39, "FORTIETH": 40
}


def parse_roman_or_word(word: str) -> int | None:
    """Parse Roman numerals or English ordinals (with common OCR mistakes)."""
    word = word.strip().upper()
    norm_word = re.sub(r"[^A-Z]", "", word)
    
    # 1. Check exact match
    if norm_word in ORDINALS_MAP:
        return ORDINALS_MAP[norm_word]
        
    # 2. Check if any ordinal is a substring (longest first)
    for ord_name in sorted(ORDINALS_MAP.keys(), key=len, reverse=True):
        if ord_name in norm_word:
            return ORDINALS_MAP[ord_name]
            
    # 3. Check Roman numerals
    roman_clean = re.sub(r"[^A-Z]", "", word)
    val = roman_to_int(roman_clean)
    if val and 1 <= val <= 40:
        return val
        
    return None


# ────────────────────────────────────────────────────────────────────────────
# Content extraction

# Match pattern for book headers, restricting the first word to variations of BOOK.
BOOK_MARKER_RE = re.compile(
    r"^\s*(?:BOOK|BOOR|B00K|BOOE|BOOS|B00R|ftJOK|ftOOK|fiOOK|book)\s+(?:THE\s+|THK\s+|TFEIE\s+|TfeIE\s+|TfeiE\s+)?([A-Za-z\- \d_<>»\.\']+)",
    re.IGNORECASE | re.MULTILINE
)

# A verse start: line containing only optional whitespace then digits then
# whitespace then a capitalised word. We require multi-line aggregation
# until the next such line OR a BOOK marker OR end of book section.
VERSE_START_RE = re.compile(r"^\s*(\d{1,3})\s+([A-Z][a-z\"\'(]|\")", re.MULTILINE)


def find_translation_start(text: str) -> int:
    """Find the byte offset where the actual translation begins.

    The TOC also has "BOOK I." entries, but each is followed by chapter-name
    lines + page numbers, not by a numbered verse. The translation start is
    the FIRST "BOOK I." (or equivalent first book marker) after the TOC (char 30,000).
    """
    for m in BOOK_MARKER_RE.finditer(text):
        # Filter page headers
        line_start = text.rfind('\n', 0, m.start()) + 1
        line = text[line_start:m.end()]
        if '[' in line or ']' in line:
            continue
            
        num = parse_roman_or_word(m.group(1))
        if num == 1 and m.start() > 30000:
            return m.start()
    return -1


def split_into_books(text: str, start_offset: int) -> list[tuple[int, str]]:
    """Find the start offsets of all 40 books and extract their text sections."""
    markers = list(BOOK_MARKER_RE.finditer(text))
    found_books: dict[int, int] = {}
    for m in markers:
        # Ignore page headers
        line_start = text.rfind('\n', 0, m.start()) + 1
        line = text[line_start:m.end()]
        if '[' in line or ']' in line:
            continue
        
        num = parse_roman_or_word(m.group(1))
        if num is not None and 1 <= num <= 40:
            if m.start() >= start_offset:
                if num not in found_books:
                    found_books[num] = m.start()

    # Ensure Book 1 starts at start_offset
    found_books[1] = start_offset

    # Slice sections
    books: list[tuple[int, str]] = []
    sorted_nums = sorted(found_books.keys())
    for i, b in enumerate(sorted_nums):
        start = found_books[b]
        end = found_books[sorted_nums[i + 1]] if i + 1 < len(sorted_nums) else len(text)
        books.append((b, text[start:end]))
        
    return books


_PAGE_HEADER_RE = re.compile(r"\[BO[O0][KR]\s+[IVXLC]+", re.IGNORECASE)
_TFB_TEXT_RE = re.compile(r"T[fF]+[bBeE6]\s+TEXTS\s+OF\s+T[FfeE6H]+", re.IGNORECASE)


def clean_verse_text(text: str) -> str:
    """Light cleanup: drop page-header crumbs, collapse whitespace."""
    text = _PAGE_HEADER_RE.sub(" ", text)
    text = _TFB_TEXT_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_verses_from_book(book_text: str) -> list[tuple[int, str]]:
    """Find numbered verse starts within a book's text, aggregate multi-line
    verses up to the next numbered start.
    """
    matches = list(VERSE_START_RE.finditer(book_text))
    if not matches:
        return []
    out: list[tuple[int, str]] = []
    for i, m in enumerate(matches):
        verse_num = int(m.group(1))
        start = m.end() - len(m.group(2))  # back up to start of the captured letter
        # Actually use the digit's match-end as text start
        text_start = m.start() + len(m.group(0)) - len(m.group(2))
        end = matches[i + 1].start() if i + 1 < len(matches) else len(book_text)
        raw = book_text[text_start:end]
        cleaned = clean_verse_text(raw)
        # Drop very short / suspicious verses (likely OCR noise)
        if len(cleaned) < 15:
            continue
        # Heuristic: numbered footnotes (1 throughout etc see L 7.) tend to
        # be one short clause; real verses tend to be longer.
        out.append((verse_num, cleaned))
    return out


# ────────────────────────────────────────────────────────────────────────────
# Record assembly

PROVENANCE = {
    "download_source": "archive.org",
    "original_url": f"https://archive.org/details/{ARCHIVE_ID}",
    "translator": "Ralph T. H. Griffith",
    "translation_year": 1899,
    "license": "Public Domain",
}


def build_record(adhyaya: int, verse: int, translation: str) -> dict:
    return {
        "id": f"yv_madhyadina_{adhyaya}_{verse}",
        "source": {
            "text": "Yajurveda",
            "chapter": adhyaya,
            "chapter_name": f"Adhyaya {adhyaya}",
            "verse": verse,
            "section": "Vajasneyi Madhyadina Samhita",
        },
        "content": {
            "sanskrit": "",
            "transliteration": "",
            "translation": translation,
        },
        "metadata": {
            "category": "shruti",
            "tradition": "vedic",
        },
        "provenance": {
            **PROVENANCE,
            "processed_date": datetime.now(timezone.utc).isoformat(),
        },
    }


# ────────────────────────────────────────────────────────────────────────────
# Main

def main() -> int:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    print(f"Output → {OUTPUT_FILE.relative_to(PROJECT_ROOT)}")
    try:
        text = fetch_djvu()
    except (HTTPError, URLError) as e:
        print(f"  ! fetch failed: {e}")
        return 1
    print(f"  Loaded {len(text):,} chars")

    start = find_translation_start(text)
    if start < 0:
        print("  ! could not find translation start")
        return 1
    print(f"  Translation body starts at char {start:,}")

    books = split_into_books(text, start)
    print(f"  Detected {len(books)} books in translation body")

    all_records: list[dict] = []
    per_book: dict[int, int] = {}
    for adhyaya, book_text in books:
        if adhyaya < 1 or adhyaya > 40:
            continue
        verses = extract_verses_from_book(book_text)
        per_book[adhyaya] = len(verses)
        for verse_num, vtext in verses:
            all_records.append(build_record(adhyaya, verse_num, vtext))

    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(all_records, f, ensure_ascii=False, indent=2)

    print()
    print("=" * 60)
    print(f"  Total: {len(all_records):,} verses across {len(per_book)} adhyayas")
    print("=" * 60)
    for adhyaya in sorted(per_book):
        print(f"  Adhyaya {adhyaya:>2}: {per_book[adhyaya]:>4} verses")
    print(f"\nSaved → {OUTPUT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
