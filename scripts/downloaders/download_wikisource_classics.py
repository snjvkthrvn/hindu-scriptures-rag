#!/usr/bin/env python3
"""Download Vedanta / Bhakti / devotional classics from Wikisource.

Targets texts that aren't in the main DharmicData corpus and that use
Wikisource's standard `<span class="wst-verse" id="ch:v">…</span>` verse
template. The verse markers are anchors; the actual translation text lies
between consecutive markers in document order.

Current targets:
  - Ashtavakra Gita        (298 verses, 20 chapters — Advaita classic)
  - The Crest Jewel of Wisdom / Vivekacūḍāmaṇi (Shankara, ~580 verses)
  - Gita Govinda           (Jayadeva, Krishna/Radha devotional)

Skipped (different format — need bespoke parsers):
  - Aditya Hridayam, Shri Rudram (devotional hymns, often one long block)

Output: raw/wikisource/vedanta_classics.json — flat list of records ready
for the merger's append-new-entries path. IDs use a slug-based prefix
(`ashtavakra_<ch>_<v>`) and source.text names align with what we want to
show users.

Usage:
    PYTHONUTF8=1 python scripts/downloaders/download_wikisource_classics.py
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
OUTPUT_FILE = PROJECT_ROOT / "raw" / "wikisource" / "vedanta_classics.json"

USER_AGENT = (
    "hindu-scriptures-rag/0.1 (research, contact: sanjeevkathiravanpro@gmail.com)"
)
REQUEST_DELAY_SEC = 0.5

# Each target = (slug, source_text_label, id_prefix, metadata, translator).
# Only sources confirmed to use Wikisource's wst-verse template are included.
# The Crest Jewel of Wisdom (Vivekachudamani) and Gita Govinda Wikisource pages
# are just landing stubs — the actual translations live elsewhere; those need
# separate downloaders against other public sources.
TARGETS = [
    (
        "Ashtavakra_Gita",
        "Ashtavakra Gita",
        "ashtavakra",
        {"category": "smriti", "tradition": "vedanta", "themes": ["advaita", "knowledge", "liberation"]},
        "John Henry Richards",
    ),
]


def fetch(url: str) -> str:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


# ────────────────────────────────────────────────────────────────────────────
# HTML walker: split text between consecutive .wst-verse anchors

class _WstVerseExtractor(HTMLParser):
    """Collect (id, text) pairs by treating each <span class~='wst-verse'> as
    a verse-start anchor. Text between two anchors belongs to the first.
    """

    SKIP_TAGS = {"sup", "script", "style"}  # sup = the marker's "1" superscript

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._current_id: str | None = None
        self._buf: list[str] = []
        self._skip_depth = 0
        self._in_marker = False
        self.verses: list[tuple[str, str]] = []

    def _flush(self) -> None:
        if self._current_id and self._buf:
            text = re.sub(r"\s+", " ", "".join(self._buf)).strip()
            if text:
                self.verses.append((self._current_id, text))
        self._buf = []

    def handle_starttag(self, tag: str, attrs) -> None:
        attrs_d = dict(attrs)
        cls = attrs_d.get("class", "")
        if tag == "span" and "wst-verse" in cls:
            self._flush()
            self._current_id = attrs_d.get("id")
            self._in_marker = True
            return
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
        # Skip references blocks
        if cls and ("reference" in cls or "mw-references" in cls):
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if self._in_marker and tag == "span":
            self._in_marker = False
            return
        if tag in self.SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._in_marker or self._skip_depth > 0:
            return
        if self._current_id:
            self._buf.append(data)

    def close(self) -> None:
        self._flush()
        super().close()


def extract_wst_verses(html: str) -> list[tuple[str, str]]:
    p = _WstVerseExtractor()
    p.feed(html)
    p.close()
    # Drop trailing footnotes / notes that bleed into the last verse — cut at
    # common "translator's notes" / "notes" boundaries
    cleaned: list[tuple[str, str]] = []
    for vid, text in p.verses:
        # Truncate at common footer markers if present
        for marker in ("Translator's Notes", "Translator’s Notes", "Notes [", "References", "↑"):
            i = text.find(marker)
            if i > 50:  # don't truncate if it's at the start
                text = text[:i].strip()
                break
        if text:
            cleaned.append((vid, text))
    return cleaned


# ────────────────────────────────────────────────────────────────────────────
# Verse-record assembly (main-corpus schema)

def build_record(source_text: str, id_prefix: str, chapter: int, verse: int,
                 translation: str, metadata: dict, translator: str,
                 source_path: str) -> dict:
    return {
        "id": f"{id_prefix}_{chapter}_{verse}",
        "source": {
            "text": source_text,
            "chapter": chapter,
            "chapter_name": f"Chapter {chapter}",
            "verse": verse,
            "section": None,
        },
        "content": {
            "sanskrit": "",
            "transliteration": "",
            "translation": translation,
        },
        "metadata": metadata,
        "provenance": {
            "download_source": "wikisource",
            "original_url": f"https://en.wikisource.org{source_path}",
            "translator": translator,
            "license": "Public Domain",
            "processed_date": datetime.now(timezone.utc).isoformat(),
        },
    }


# ────────────────────────────────────────────────────────────────────────────
# Main

def main() -> int:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    print(f"Output → {OUTPUT_FILE.relative_to(PROJECT_ROOT)}")
    all_records: list[dict] = []
    per_target: dict[str, int] = {}

    for slug, source_text, id_prefix, metadata, translator in TARGETS:
        url = f"https://en.wikisource.org/wiki/{slug}"
        source_path = f"/wiki/{slug}"
        print(f"[{source_text}] {url}")
        try:
            html = fetch(url)
            time.sleep(REQUEST_DELAY_SEC)
        except (HTTPError, URLError) as e:
            print(f"  ! fetch failed: {e}")
            per_target[source_text] = 0
            continue

        verses = extract_wst_verses(html)
        records = []
        for vid, text in verses:
            # id format expected: "<ch>:<v>"
            m = re.match(r"^(\d+):(\d+)$", vid)
            if not m:
                continue  # skip non-conforming ids
            ch, v = int(m.group(1)), int(m.group(2))
            records.append(
                build_record(source_text, id_prefix, ch, v, text, metadata, translator, source_path)
            )
        all_records.extend(records)
        per_target[source_text] = len(records)
        print(f"  ← {len(records)} verses captured")

    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(all_records, f, ensure_ascii=False, indent=2)

    print()
    print("=" * 60)
    print(f"  Total: {len(all_records):,} verses across {len(TARGETS)} texts")
    print("=" * 60)
    for src, n in per_target.items():
        print(f"  {src:<30} {n:>5}")
    print(f"\nSaved → {OUTPUT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
