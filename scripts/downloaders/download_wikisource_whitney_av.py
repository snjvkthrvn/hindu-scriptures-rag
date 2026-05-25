#!/usr/bin/env python3
"""Download William Dwight Whitney's Atharvaveda English translation from Wikisource.

Wikisource hosts the complete Whitney (1905) translation at
https://en.wikisource.org/wiki/Atharva-Veda_Samhita/Book_<Roman>/Hymn_<N>
with some structural variation across books:

  - Most books: /Book_<R>/Hymn_<N>
  - Book VII (after hymn 5): /Book_VII/Hymn_<W>_(<C1>,_<C2>) — Whitney's
    numbering diverges from canonical Shaunaka; parens give canonical hymn(s)
  - Books XV, XVI: /Book_<R>/Paryaya_<N> — these books are organised as
    paryāyas (liturgical sections) not suktas
  - Book XX: Whitney did NOT translate (mostly RV repetitions) — skipped

Verse extraction: every hymn page has paragraphs starting with "<N>. " — the
first match is the hymn title (same number as the hymn), the rest are verses.

Output: raw/wikisource/atharvaveda_whitney.json — main-corpus-aligned schema
ready for the english merger. Verses use the *canonical* hymn number so the
ids align with main corpus av_<book>_<sukta>_<verse> ids.

Usage:
    PYTHONUTF8=1 python scripts/downloaders/download_wikisource_whitney_av.py
"""

from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_FILE = PROJECT_ROOT / "raw" / "wikisource" / "atharvaveda_whitney.json"

ROMAN = {
    1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI", 7: "VII",
    8: "VIII", 9: "IX", 10: "X", 11: "XI", 12: "XII", 13: "XIII",
    14: "XIV", 15: "XV", 16: "XVI", 17: "XVII", 18: "XVIII", 19: "XIX",
}
BOOKS_TO_FETCH = list(range(1, 20))  # 1..19 — skip 20 (Whitney didn't translate)
PARYAYA_BOOKS = {15, 16}  # use /Paryaya_N instead of /Hymn_N

USER_AGENT = (
    "hindu-scriptures-rag/0.1 (research, contact: sanjeevkathiravanpro@gmail.com)"
)
REQUEST_DELAY_SEC = 0.5


# ────────────────────────────────────────────────────────────────────────────
# HTTP

def fetch(url: str) -> str:
    """GET a Wikisource page with a polite UA, return decoded text."""
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=30) as r:
        raw = r.read()
    return raw.decode("utf-8", errors="replace")


# ────────────────────────────────────────────────────────────────────────────
# Minimal HTML → paragraph-text extractor (no bs4 dependency)

class _ParagraphExtractor(HTMLParser):
    """Collect the text content of every <p> tag in document order."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._in_p = 0
        self._buf: list[str] = []
        self.paragraphs: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "p":
            self._in_p += 1
            self._buf = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "p" and self._in_p:
            self._in_p -= 1
            if self._in_p == 0:
                text = re.sub(r"\s+", " ", "".join(self._buf)).strip()
                if text:
                    self.paragraphs.append(text)
                self._buf = []

    def handle_data(self, data: str) -> None:
        if self._in_p:
            self._buf.append(data)


def extract_verses(html: str) -> list[tuple[int, str]]:
    """Return [(verse_num, text), ...] from a Whitney hymn page.

    Pattern: paragraphs starting with "<N>. <text>" — the first match is the
    hymn title (its number equals the hymn number), subsequent are verses.
    """
    parser = _ParagraphExtractor()
    parser.feed(html)
    numbered = []
    for p in parser.paragraphs:
        m = re.match(r"^(\d+)\.\s+(.+)$", p)
        if m:
            numbered.append((int(m.group(1)), m.group(2)))
    if len(numbered) < 2:
        return []  # missing title or no verses
    return numbered[1:]  # drop title


# ────────────────────────────────────────────────────────────────────────────
# Book-index parsing

_HYMN_LINK_RE = re.compile(
    r'href="(/wiki/Atharva-Veda_Samhita/Book_([IVX]+)/(?:Hymn|Paryaya)_[^"]+)"'
)
_HYMN_PATH_RE = re.compile(r"/(?:Hymn|Paryaya)_(\d+)(?:_\(([\d,_\s]+)\))?$")


def parse_book_index(html: str, book_roman: str) -> list[dict]:
    """Return [{path, whitney_num, canonical_nums}, ...] for one book index."""
    seen: dict[str, dict] = {}
    for m in _HYMN_LINK_RE.finditer(html):
        path, roman = m.group(1), m.group(2)
        if roman != book_roman:
            continue
        if path in seen:
            continue
        nm = _HYMN_PATH_RE.search(path)
        if not nm:
            continue
        whitney = int(nm.group(1))
        if nm.group(2):
            canonical = [
                int(s) for s in re.split(r",_?", nm.group(2)) if s.strip().isdigit()
            ]
        else:
            canonical = [whitney]
        seen[path] = {"path": path, "whitney": whitney, "canonical": canonical}
    return sorted(seen.values(), key=lambda x: x["whitney"])


# ────────────────────────────────────────────────────────────────────────────
# Verse-record assembly

PROVENANCE = {
    "download_source": "wikisource",
    "original_url_base": "https://en.wikisource.org/wiki/Atharva-Veda_Samhita",
    "translator": "William Dwight Whitney",
    "translation_year": 1905,
    "license": "Public Domain",
}


def build_verse_record(book_num: int, hymn_num: int, verse_num: int, text: str,
                        whitney_hymn: int, source_path: str) -> dict:
    """Assemble a record matching the english merger's expected schema.

    IDs are minted to align with main corpus av_<book>_<sukta>_<verse>.
    """
    return {
        "id": f"av_{book_num}_{hymn_num}_{verse_num}",
        "source": {
            "text": "Atharvaveda",
            "chapter": book_num,
            "chapter_name": f"Kaanda {book_num}",
            "verse": verse_num,
            "section": f"Sukta {hymn_num}",
        },
        "content": {
            "sanskrit": "",
            "transliteration": "",
            "translation": text,
        },
        "metadata": {
            "category": "shruti",
            "tradition": "vedic",
        },
        "provenance": {
            **PROVENANCE,
            "original_url": f"https://en.wikisource.org{source_path}",
            "whitney_hymn_num": whitney_hymn,
            "processed_date": datetime.now(timezone.utc).isoformat(),
        },
    }


# ────────────────────────────────────────────────────────────────────────────
# Main

def main() -> int:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    print(f"Output → {OUTPUT_FILE.relative_to(PROJECT_ROOT)}")
    all_records: list[dict] = []
    per_book: dict[int, dict] = {}

    for book_num in BOOKS_TO_FETCH:
        roman = ROMAN[book_num]
        index_url = f"https://en.wikisource.org/wiki/Atharva-Veda_Samhita/Book_{roman}"
        try:
            print(f"[Book {book_num}/{roman}] index: {index_url}")
            index_html = fetch(index_url)
            time.sleep(REQUEST_DELAY_SEC)
        except (HTTPError, URLError) as e:
            print(f"  ! index fetch failed: {e}")
            per_book[book_num] = {"hymns": 0, "verses": 0, "error": str(e)}
            continue

        hymn_infos = parse_book_index(index_html, roman)
        print(f"  → {len(hymn_infos)} hymn pages found")

        book_records = []
        for info in hymn_infos:
            url = f"https://en.wikisource.org{info['path']}"
            try:
                hymn_html = fetch(url)
                time.sleep(REQUEST_DELAY_SEC)
            except (HTTPError, URLError) as e:
                print(f"    ! {info['path']} fetch failed: {e}")
                continue
            verses = extract_verses(hymn_html)
            # Whitney may group multiple canonical hymns on one page; use the
            # first canonical number as the merging key. Multi-canonical pages
            # produce partial coverage of the secondary canonical hymn.
            canonical_hymn = info["canonical"][0] if info["canonical"] else info["whitney"]
            for verse_num, text in verses:
                rec = build_verse_record(
                    book_num=book_num,
                    hymn_num=canonical_hymn,
                    verse_num=verse_num,
                    text=text,
                    whitney_hymn=info["whitney"],
                    source_path=info["path"],
                )
                book_records.append(rec)

        per_book[book_num] = {
            "roman": roman,
            "hymns": len(hymn_infos),
            "verses": len(book_records),
        }
        all_records.extend(book_records)
        print(f"  ← {len(book_records)} verses captured")

    # Write output
    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(all_records, f, ensure_ascii=False, indent=2)

    # Summary
    print()
    print("=" * 60)
    print(f"  Total: {len(all_records):,} verses across {len(BOOKS_TO_FETCH)} books")
    print("=" * 60)
    print(f"{'Book':<6} {'Hymns':>6} {'Verses':>7}")
    for b in BOOKS_TO_FETCH:
        s = per_book.get(b, {"hymns": 0, "verses": 0})
        print(f"  {b:<4} {s.get('hymns', 0):>6} {s.get('verses', 0):>7}")
    print(f"\nSaved → {OUTPUT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
