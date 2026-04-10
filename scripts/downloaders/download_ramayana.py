#!/usr/bin/env python3
"""
Download and parse the Ramayana (Valmiki) from Project Gutenberg.

Ralph T.H. Griffith English verse translation (1870-1874).
Source: https://www.gutenberg.org/cache/epub/24869/pg24869-images.html

Structure: Books I–VI, each with Cantos. Verses are in tei-lg/tei-l divs.
Output: JSON in the same schema as Rigveda (id, source, content, metadata, provenance).
"""

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.gutenberg.org/cache/epub/24869/pg24869-images.html"

# Traditional book names (Kandas) for Ramayana
BOOK_NAMES = {
    1: "Bala Kanda",
    2: "Ayodhya Kanda",
    3: "Aranya Kanda",
    4: "Kishkindha Kanda",
    5: "Sundara Kanda",
    6: "Yuddha Kanda",
}


@dataclass
class RamayanaVerse:
    """A single verse (stanza) from the Ramayana."""

    book: int
    canto: int
    canto_name: str
    verse_num: int
    text: str


def _clean_text(text: str) -> str:
    """Remove footnote refs, extra whitespace."""
    # Strip superscript numbers that are footnote refs
    text = re.sub(r"\s*\d+\s*$", "", text)
    text = re.sub(r"^\s*\d+\s*", "", text)
    return " ".join(text.split()).strip()


def _strip_footnotes(soup_element) -> str:
    """Get text from element, removing footnote anchor tags."""
    if soup_element is None:
        return ""
    # Clone to avoid modifying original - remove footnote links before extracting text
    el = BeautifulSoup(str(soup_element), "html.parser")
    for a in el.find_all("a", href=lambda h: h and h.startswith("#note")):
        a.decompose()
    raw = el.get_text(separator=" ", strip=True)
    # Remove any remaining orphaned footnote refs (e.g. trailing digits)
    raw = re.sub(r"\s*\d+\s*$", "", raw)
    return _clean_text(raw)


def fetch_ramayana_html(url: str = BASE_URL) -> str:
    """Fetch the Ramayana HTML from Project Gutenberg."""
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Hindu Scriptures RAG; +https://github.com/hindu-scriptures-rag)",
            "Accept": "text/html,application/xhtml+xml",
        }
    )
    resp = session.get(url, timeout=60)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "utf-8"
    return resp.text


def parse_ramayana(html: str) -> list[RamayanaVerse]:
    """
    Parse Ramayana HTML and extract verses.

    Uses TEI structure: tei-head for Book/Canto, tei-lg for stanzas, tei-l for lines.
    """
    soup = BeautifulSoup(html, "html.parser")
    verses = []

    # Find main text container
    text_div = soup.find(
        "div", class_=lambda c: c and "tei-text" in (c if isinstance(c, list) else [c])
    )
    if not text_div:
        text_div = soup.find("body")

    current_book = 0
    current_canto = 0
    current_canto_name = ""
    verse_counter = 0

    def process_heading(head_el):
        nonlocal current_book, current_canto, current_canto_name
        txt = head_el.get_text(strip=True)
        # Remove trailing footnote numbers
        txt = re.sub(r"\.?\d+\s*$", "", txt).strip()

        # Book I., BOOK II., etc.
        book_match = re.match(r"^(?:BOOK\s+)?(?:Book\s+)?([IVXLCDM]+)\.?\s*$", txt, re.I)
        if book_match:
            current_book = _roman_to_int(book_match.group(1))
            current_canto = 0
            current_canto_name = ""
            return

        # Canto I. Nárad., Canto II. Brahmá's Visit
        canto_match = re.match(r"^Canto\s+([IVXLCDM]+)\.?\s*(.*)$", txt, re.I)
        if canto_match:
            current_canto = _roman_to_int(canto_match.group(1))
            current_canto_name = canto_match.group(2).strip() if canto_match.group(2) else ""
            return

        # Invocation - treat as book 1, canto 0
        if "Invocation" in txt and current_book == 0:
            current_book = 1
            current_canto = 0
            current_canto_name = "Invocation"

    def process_stanza(lg_el):
        nonlocal verse_counter
        lines = []
        for line_el in lg_el.find_all(
            "div", class_=lambda c: c and "tei-l" in (c if isinstance(c, list) else [c])
        ):
            line_text = _strip_footnotes(line_el)
            if line_text:
                lines.append(line_text)

        # Only include verses from main books 1-6 (skip Appendix, Notes, etc.)
        if not lines or current_book == 0 or current_book > 6:
            return

        verse_counter += 1
        verse_text = " ".join(lines).strip()
        if not verse_text or len(verse_text) < 3:
            return

        verses.append(
            RamayanaVerse(
                book=current_book,
                canto=current_canto,
                canto_name=current_canto_name,
                verse_num=verse_counter,
                text=verse_text,
            )
        )

    # Walk the DOM in document order
    for el in text_div.find_all(["h1", "h2", "h3", "h4", "div"]):
        classes = el.get("class") or []
        if isinstance(classes, str):
            classes = [classes]

        if "tei-head" in classes:
            process_heading(el)
        elif "tei-lg" in classes:
            process_stanza(el)

    return verses


def _roman_to_int(roman: str) -> int:
    """Convert Roman numeral to int."""
    roman = roman.upper().strip()
    values = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    total = 0
    prev = 0
    for c in reversed(roman):
        v = values.get(c, 0)
        total += v if v >= prev else -v
        prev = v
    return total


def verses_to_json(verses: list[RamayanaVerse]) -> list[dict]:
    """Convert parsed verses to the project JSON schema."""
    # Reset verse numbering per canto for cleaner IDs
    canto_verses: dict[tuple[int, int], int] = {}

    result = []
    for v in verses:
        key = (v.book, v.canto)
        canto_verses[key] = canto_verses.get(key, 0) + 1
        verse_num = canto_verses[key]

        verse_id = f"ram_{v.book}_{v.canto}_{verse_num}"
        book_name = BOOK_NAMES.get(v.book, f"Book {v.book}")

        result.append(
            {
                "id": verse_id,
                "source": {
                    "text": "Ramayana",
                    "book": v.book,
                    "book_name": book_name,
                    "canto": v.canto,
                    "canto_name": v.canto_name or "",
                    "verse": verse_num,
                },
                "content": {
                    "sanskrit": "",
                    "transliteration": "",
                    "translation": v.text,
                    "word_by_word": {},
                },
                "metadata": {
                    "category": "smriti",
                    "tradition": "itihasa",
                    "themes": ["ramayana"],
                    "philosophical_schools": [],
                },
                "commentaries": [],
                "provenance": {
                    "download_source": "gutenberg",
                    "original_url": BASE_URL,
                    "translator": "Ralph T.H. Griffith",
                    "translation_year": "1870-1874",
                    "license": "Public Domain",
                    "processed_date": datetime.now(timezone.utc).isoformat(),
                },
            }
        )
    return result


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Download and parse Ramayana from Project Gutenberg"
    )
    parser.add_argument(
        "-o",
        "--output",
        default="raw/gutenberg/ramayana.json",
        help="Output JSON file path",
    )
    parser.add_argument(
        "--from-html",
        help="Parse from local HTML file instead of fetching",
    )
    parser.add_argument(
        "--save-html",
        help="Save fetched HTML to this path",
    )

    args = parser.parse_args()
    output_path = Path(args.output)

    if args.from_html:
        html_path = Path(args.from_html)
        if not html_path.exists():
            print(f"Error: File not found: {html_path}")
            return 1
        print(f"Parsing from {html_path}")
        html = html_path.read_text(encoding="utf-8", errors="replace")
    else:
        print(f"Fetching from {BASE_URL}")
        html = fetch_ramayana_html()
        if args.save_html:
            save_path = Path(args.save_html)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            save_path.write_text(html, encoding="utf-8")
            print(f"Saved HTML to {save_path}")

    print("Parsing verses...")
    verses = parse_ramayana(html)
    print(f"Extracted {len(verses)} verses")

    records = verses_to_json(verses)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(records)} verses to {output_path}")
    return 0


if __name__ == "__main__":
    exit(main())
