#!/usr/bin/env python3
"""Build verses_english_only.json from all English sources for the RAG.

Aggregates:
- raw/sacred-texts/rigveda.json
- raw/gutenberg/ramayana.json
- processed/tier1-essential/parsed_verses.json (Bhagavad Gita only)
- translations/isha_upanishad_mueller.csv
- translations/mundaka_upanishad_mueller.csv
- raw/sacred-texts/yoga_sutras.html (parsers)
- raw/gutenberg/pg2388_bhagavad_gita.txt (Arnold Gita)
- raw/gutenberg/pg15474_mahabharata.txt (Ganguli Mahabharata)
- final/verses_enriched.json (Claude-translated Upanishads)

Output: english-v1-rag/verses_english_only.json
"""

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_FILE = Path(__file__).resolve().parent / "verses_english_only.json"

# Allow running from project root
sys.path.insert(0, str(Path(__file__).resolve().parent))


def ensure_source_fields(source: dict) -> dict:
    """Ensure source has text, chapter, verse for schema validation."""
    s = dict(source)
    if "chapter" not in s and "book" in s:
        s["chapter"] = s["book"]
    if "chapter" not in s:
        s["chapter"] = 0
    if "verse" not in s:
        s["verse"] = 0
    return s


def normalize_verse(verse: dict) -> dict:
    """Ensure verse has all required schema fields."""
    v = dict(verse)
    v["source"] = ensure_source_fields(v.get("source", {}))
    v.setdefault("content", {})
    v["content"].setdefault("sanskrit", "")
    v["content"].setdefault("transliteration", "")
    v["content"].setdefault("translation", "")
    v.setdefault("metadata", {})
    v["metadata"].setdefault("category", "")
    v["metadata"].setdefault("tradition", "")
    v["metadata"].setdefault("themes", [])
    v.setdefault("provenance", {})
    v["provenance"].setdefault("download_source", "unknown")
    v["provenance"].setdefault("license", "Unknown")
    v["provenance"].setdefault("processed_date", datetime.now(timezone.utc).isoformat())
    v.setdefault("commentaries", [])
    return v


def has_translation(verse: dict) -> bool:
    """True if verse has a non-empty English translation."""
    trans = (verse.get("content") or {}).get("translation") or ""
    return bool(trans.strip())


def _is_english_text(text: str) -> bool:
    """True if text appears to be English (not Sanskrit/Devanagari)."""
    if not text or len(text) < 10:
        return False
    # Devanagari range – if present, likely Sanskrit
    devanagari = sum(1 for c in text if "\u0900" <= c <= "\u097f")
    return devanagari < len(text) * 0.1


def load_rigveda() -> list:
    """Load Rigveda from sacred-texts JSON (English only)."""
    path = PROJECT_ROOT / "raw" / "sacred-texts" / "rigveda.json"
    if not path.exists():
        return []
    with open(path) as f:
        verses = json.load(f)
    return [normalize_verse(v) for v in verses if has_translation(v)]


def load_ramayana() -> list:
    """Load Ramayana from Gutenberg JSON (English only)."""
    path = PROJECT_ROOT / "raw" / "gutenberg" / "ramayana.json"
    if not path.exists():
        return []
    with open(path) as f:
        verses = json.load(f)
    return [normalize_verse(v) for v in verses if has_translation(v)]


def load_bhagavad_gita() -> list:
    """Load Bhagavad Gita from parsed_verses (has both Sanskrit + English)."""
    path = PROJECT_ROOT / "processed" / "tier1-essential" / "parsed_verses.json"
    if not path.exists():
        path = PROJECT_ROOT / "processed" / "tier1-essential" / "bhagavad_gita.json"
    if not path.exists():
        return []
    with open(path) as f:
        verses = json.load(f)
    gita = [v for v in verses if v.get("source", {}).get("text") == "Bhagavad Gita"]
    return [normalize_verse(v) for v in gita if has_translation(v)]


def load_yoga_sutras() -> list:
    """Load Yoga Sutras from sacred-texts HTML via parser."""
    from parsers.yoga_sutras import parse_yoga_sutras_html

    path = PROJECT_ROOT / "raw" / "sacred-texts" / "yoga_sutras.html"
    if not path.exists():
        return []
    return [normalize_verse(v) for v in parse_yoga_sutras_html(path) if has_translation(v)]


def load_arnold_gita() -> list:
    """Load Bhagavad Gita from Arnold's Gutenberg text via parser."""
    from parsers.gutenberg_gita import parse_arnold_gita

    path = PROJECT_ROOT / "raw" / "gutenberg" / "pg2388_bhagavad_gita.txt"
    if not path.exists():
        return []
    return [normalize_verse(v) for v in parse_arnold_gita(path) if has_translation(v)]


def load_mahabharata_ganguli() -> list:
    """Load Mahabharata from Ganguli's Gutenberg text via parser."""
    from parsers.gutenberg_mahabharata import parse_mahabharata_ganguli

    path = PROJECT_ROOT / "raw" / "gutenberg" / "pg15474_mahabharata.txt"
    if not path.exists():
        return []
    return [normalize_verse(v) for v in parse_mahabharata_ganguli(path) if has_translation(v)]


def load_claude_upanishads() -> list:
    """Load Claude-translated Upanishads from final/verses_enriched.json.

    Covers: Isha, Kena, Katha, Prashna, Mundaka, Mandukya, Taittiriya,
    Aitareya, Brihadaranyaka, Svetasvatara (from translate_verses.py).
    Verse numbers inferred from order (source often has duplicate verse ids).
    """
    path = PROJECT_ROOT / "final" / "verses_enriched.json"
    if not path.exists():
        return []
    with open(path) as f:
        verses = json.load(f)
    out = []
    verse_counter: dict[str, int] = {}
    for v in verses:
        src = v.get("source") or {}
        if not isinstance(src, dict):
            continue
        text_name = (src.get("text") or "").strip()
        if "Upanishad" not in text_name:
            continue
        trans = (v.get("content") or {}).get("translation") or ""
        trans = trans.strip()
        if not trans or not _is_english_text(trans):
            continue
        # Assign verse number by order within each Upanishad
        verse_counter[text_name] = verse_counter.get(text_name, 0) + 1
        vn = verse_counter[text_name]
        slug = text_name.lower().replace(" ", "_")
        vid = f"up_claude_{slug}_{vn}"
        out.append(
            normalize_verse(
                {
                    "id": vid,
                    "source": {
                        "text": f"{text_name} (Claude)",
                        "chapter": src.get("chapter") or 1,
                        "chapter_name": src.get("chapter_name") or text_name,
                        "verse": vn,
                    },
                    "content": {
                        "sanskrit": (v.get("content") or {}).get("sanskrit", ""),
                        "transliteration": "",
                        "translation": trans,
                    },
                    "metadata": {
                        "category": "shruti",
                        "tradition": "vedanta",
                        "themes": ["upanishad", slug],
                    },
                    "commentaries": v.get("commentaries", []),
                    "provenance": {
                        "download_source": "final",
                        "translator": "Claude (Anthropic)",
                        "license": "Project",
                        "processed_date": datetime.now(timezone.utc).isoformat(),
                    },
                }
            )
        )
    return out


def load_upanishad_csv(csv_path: Path, upanishad_name: str) -> list:
    """Load Upanishad from Mueller CSV into verse format."""
    verses = []
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            verse_num = row.get("verse_number", "").strip()
            trans = (row.get("translation") or "").strip()
            if not trans:
                continue
            # Skip non-numeric verse numbers (e.g. commentary rows)
            try:
                vn = int(verse_num)
            except ValueError:
                continue
            # Isha has 18 verses; Mundaka has 64. Restrict to standard counts.
            if "Isha" in upanishad_name and vn > 18:
                continue
            if "Mundaka" in upanishad_name and vn > 64:
                continue
            verse = {
                "id": f"up_{upanishad_name.lower().replace(' ', '_')}_{vn}",
                "source": {
                    "text": upanishad_name,
                    "chapter": 1,
                    "chapter_name": upanishad_name,
                    "verse": vn,
                },
                "content": {
                    "sanskrit": "",
                    "transliteration": "",
                    "translation": trans,
                },
                "metadata": {
                    "category": "shruti",
                    "tradition": "vedanta",
                    "themes": ["upanishad", upanishad_name.lower().replace(" ", "_")],
                },
                "commentaries": [],
                "provenance": {
                    "download_source": "translations",
                    "original_url": "sacred-texts.com (Max Müller)",
                    "license": "Public Domain",
                    "processed_date": datetime.now(timezone.utc).isoformat(),
                },
            }
            verses.append(normalize_verse(verse))
    return verses


def main():
    all_verses = []

    # Rigveda
    rv = load_rigveda()
    all_verses.extend(rv)
    print(f"Rigveda: {len(rv):,} verses")

    # Ramayana
    ram = load_ramayana()
    all_verses.extend(ram)
    print(f"Ramayana: {len(ram):,} verses")

    # Bhagavad Gita
    bg = load_bhagavad_gita()
    all_verses.extend(bg)
    print(f"Bhagavad Gita: {len(bg):,} verses")

    # Isha Upanishad
    isha_path = PROJECT_ROOT / "translations" / "isha_upanishad_mueller.csv"
    if isha_path.exists():
        isha = load_upanishad_csv(isha_path, "Isha Upanishad")
        all_verses.extend(isha)
        print(f"Isha Upanishad: {len(isha):,} verses")

    # Mundaka Upanishad
    mundaka_path = PROJECT_ROOT / "translations" / "mundaka_upanishad_mueller.csv"
    if mundaka_path.exists():
        mundaka = load_upanishad_csv(mundaka_path, "Mundaka Upanishad")
        all_verses.extend(mundaka)
        print(f"Mundaka Upanishad: {len(mundaka):,} verses")

    # Claude-translated Upanishads (Kena, Katha, Prashna, Mandukya, Taittiriya, etc.)
    claude_up = load_claude_upanishads()
    all_verses.extend(claude_up)
    print(f"Upanishads (Claude): {len(claude_up):,} verses")

    # Yoga Sutras
    ys = load_yoga_sutras()
    all_verses.extend(ys)
    print(f"Yoga Sutras: {len(ys):,} verses")

    # Bhagavad Gita (Arnold - alternate translation)
    arnold = load_arnold_gita()
    all_verses.extend(arnold)
    print(f"Bhagavad Gita (Arnold): {len(arnold):,} verses")

    # Mahabharata
    mbh = load_mahabharata_ganguli()
    all_verses.extend(mbh)
    print(f"Mahabharata: {len(mbh):,} verses")

    # Deduplicate by id (later sources overwrite)
    by_id = {}
    for v in all_verses:
        by_id[v["id"]] = v
    final = list(by_id.values())

    # Sort by source then verse for reproducibility
    def sort_key(v):
        s = v.get("source", {})
        return (s.get("text", ""), s.get("chapter", 0), s.get("verse", 0))

    final.sort(key=sort_key)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(final, f, ensure_ascii=False, indent=2)

    print(f"\nTotal: {len(final):,} verses")
    print(f"Written to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
