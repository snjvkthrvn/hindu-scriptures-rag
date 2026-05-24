"""Merge English translations from verses_english_only.json into verses_enriched.json.

For each main-corpus verse with an empty `content.translation`, look up an
English translation from the english-only corpus using a multi-key strategy:

1. Verse id (exact match) — covers Rigveda where both pipelines mint the
   same `rv_<mandala>_<sukta>_<rik>` ids.
2. Compound key (normalised source, chapter_or_chapter_name, verse) — covers
   Upanishads where the main corpus stores `chapter=None, chapter_name='Isha
   Upanishad'` while the english-only corpus stores `chapter=1, chapter_name=
   'Isha Upanishad'`.

Mahabharata (Critical Edition) and Valmiki Ramayana are deliberately SKIPPED.
The main corpus uses the Critical Edition (Mahabharata) and the Baroda
recension (Ramayana); the available English (Ganguli, Griffith) follows the
Calcutta vulgate / older recensions with different verse numbering. Joining
by (chapter, verse) produces many false matches that would associate the
wrong English with a Sanskrit verse. Those sources need recension-aware
ingestion (Step 2).

Usage:
    PYTHONUTF8=1 python -m scripts.formatters.merge_english
"""

from __future__ import annotations

import json
import shutil
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MAIN_FILE = PROJECT_ROOT / "final" / "verses_enriched.json"
ENG_FILE = PROJECT_ROOT / "english-v1-rag" / "verses_english_only.json"
BACKUP_FILE = MAIN_FILE.with_suffix(".json.bak")

# Additional English source files merged on top of ENG_FILE when present.
# Each holds a flat list of verse records in the same shape as ENG_FILE
# (id, source.text/chapter/chapter_name/verse, content.translation). Files
# are silently skipped when absent — they're produced on demand by the
# scripts/downloaders/download_wikisource_*.py scripts.
EXTRA_ENG_SOURCES = [
    PROJECT_ROOT / "raw" / "wikisource" / "atharvaveda_whitney.json",
    PROJECT_ROOT / "raw" / "wikisource" / "yajurveda_griffith.json",
    PROJECT_ROOT / "raw" / "wikisource" / "ramcharitmanas_hill.json",
]

# Sources where recension/numbering disagrees between the two corpora — leaving
# these alone avoids associating wrong English with Sanskrit verses.
SKIP_SOURCES = {
    "Mahabharata (Critical Edition)",
    "Valmiki Ramayana",
}

# Sources with sukta-level structure where (source, chapter, verse) alone is
# AMBIGUOUS — many verses share the same (mandala, verse-in-sukta) but live
# in different suktas. For these, only the verse-id exact-match path is safe;
# compound-key fallback would produce false matches with the wrong sukta.
ID_MATCH_ONLY_SOURCES = {"Rigveda", "Atharvaveda"}

# Map English-only source names → main-corpus source names.
SOURCE_RENAMES = {
    "Rig Veda": "Rigveda",
    "Bhagavad Gita (Arnold)": "Bhagavad Gita",
}

# When multiple english entries match a key, prefer in this order (earliest wins).
SOURCE_PREFERENCE = {
    "Bhagavad Gita": ["Bhagavad Gita", "Bhagavad Gita (Arnold)"],
    "Isha Upanishad": ["Isha Upanishad", "Isha Upanishad (Claude)"],
    "Mundaka Upanishad": ["Mundaka Upanishad", "Mundaka Upanishad (Claude)"],
}


def normalise_source(name: str) -> str:
    if name in SOURCE_RENAMES:
        return SOURCE_RENAMES[name]
    if name.endswith(" (Claude)"):
        return name[: -len(" (Claude)")]
    return name


def build_index(eng_verses: list[dict]) -> dict:
    by_id: dict[str, dict] = {}
    by_key: dict[tuple, list[dict]] = defaultdict(list)
    for v in eng_verses:
        translation = ((v.get("content") or {}).get("translation") or "").strip()
        if not translation:
            continue
        if v.get("id"):
            by_id.setdefault(v["id"], v)
        src = normalise_source(v["source"].get("text", ""))
        s = v["source"]
        verse = s.get("verse")
        # Index under BOTH chapter and chapter_name so either-side mismatches still hit.
        for ch_field in (s.get("chapter"), s.get("chapter_name")):
            if ch_field is None:
                continue
            by_key[(src, ch_field, verse)].append(v)
    return {"by_id": by_id, "by_key": by_key}


def pick_preferred(matches: list[dict], main_source: str) -> dict:
    if len(matches) == 1:
        return matches[0]
    for preferred in SOURCE_PREFERENCE.get(main_source, []):
        for m in matches:
            if m["source"].get("text") == preferred:
                return m
    return matches[0]


def find_english(main_verse: dict, idx: dict) -> dict | None:
    src = main_verse["source"].get("text", "")
    if src in SKIP_SOURCES:
        return None
    # Verse-id exact match — always safe when ids align across corpora (RV, BG)
    vid = main_verse.get("id")
    if vid and vid in idx["by_id"]:
        candidate = idx["by_id"][vid]
        if normalise_source(candidate["source"].get("text", "")) == src:
            return candidate
    # For sukta-structured sources, refuse the compound-key fallback — its
    # (chapter, verse) tuple collides across suktas and produces false matches.
    if src in ID_MATCH_ONLY_SOURCES:
        return None
    s = main_verse["source"]
    for ch_field in (s.get("chapter"), s.get("chapter_name")):
        if ch_field is None:
            continue
        matches = idx["by_key"].get((src, ch_field, s.get("verse")))
        if matches:
            return pick_preferred(matches, src)
    return None


def main() -> int:
    print(f"Loading main corpus from {MAIN_FILE.relative_to(PROJECT_ROOT)} ...")
    main_verses = json.loads(MAIN_FILE.read_text(encoding="utf-8"))
    print(f"  {len(main_verses):,} verses")

    print(f"Loading English-only corpus from {ENG_FILE.relative_to(PROJECT_ROOT)} ...")
    eng_verses = json.loads(ENG_FILE.read_text(encoding="utf-8"))
    for v in eng_verses:
        v["_origin_file"] = str(ENG_FILE.relative_to(PROJECT_ROOT)).replace("\\", "/")
    print(f"  {len(eng_verses):,} verses")

    for extra_path in EXTRA_ENG_SOURCES:
        if not extra_path.exists():
            continue
        extra = json.loads(extra_path.read_text(encoding="utf-8"))
        rel = str(extra_path.relative_to(PROJECT_ROOT)).replace("\\", "/")
        for v in extra:
            v["_origin_file"] = rel
        print(f"  + {rel}: {len(extra):,} verses")
        eng_verses.extend(extra)

    idx = build_index(eng_verses)
    print(f"  index: {len(idx['by_id']):,} by id, {len(idx['by_key']):,} compound keys")

    before_total: dict[str, int] = defaultdict(int)
    before_has: dict[str, int] = defaultdict(int)
    for v in main_verses:
        src = v["source"].get("text", "?")
        before_total[src] += 1
        if ((v.get("content") or {}).get("translation") or "").strip():
            before_has[src] += 1

    added: dict[str, int] = defaultdict(int)
    for v in main_verses:
        content = v.setdefault("content", {})
        if (content.get("translation") or "").strip():
            continue
        match = find_english(v, idx)
        if not match:
            continue
        content["translation"] = match["content"]["translation"]
        prov = v.setdefault("provenance", {})
        prov["translation_source_text"] = match["source"].get("text", "")
        prov["translation_source_file"] = match.get(
            "_origin_file", "english-v1-rag/verses_english_only.json"
        )
        # Carry through translator info when the english record provides it
        match_prov = match.get("provenance") or {}
        for k in ("translator", "translation_year"):
            if k in match_prov:
                prov[f"translation_{k}"] = match_prov[k]
        added[v["source"].get("text", "?")] += 1

    print()
    print(f"{'Source':<40} {'verses':>7} {'before':>7} {'added':>7} {'after':>7} {'after %':>8}")
    print("-" * 82)
    for src in sorted(before_total, key=lambda k: -before_total[k]):
        b = before_has[src]
        a = added[src]
        after = b + a
        pct = 100 * after / before_total[src]
        marker = " (skipped)" if src in SKIP_SOURCES else ""
        print(
            f"{src + marker:<40} {before_total[src]:>7} {b:>7} {a:>7} {after:>7} {pct:>7.1f}%"
        )
    tot = sum(before_total.values())
    tb = sum(before_has.values())
    ta = sum(added.values())
    print("-" * 82)
    print(f"{'TOTAL':<40} {tot:>7} {tb:>7} {ta:>7} {tb + ta:>7} {100 * (tb + ta) / tot:>7.2f}%")

    if not BACKUP_FILE.exists():
        print(f"\nBacking up original → {BACKUP_FILE.name}")
        shutil.copy2(MAIN_FILE, BACKUP_FILE)
    else:
        print(f"\n(backup {BACKUP_FILE.name} already exists, leaving as-is)")
    print(f"Writing merged corpus → {MAIN_FILE.name}")
    with MAIN_FILE.open("w", encoding="utf-8") as f:
        json.dump(main_verses, f, ensure_ascii=False, indent=2)
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
