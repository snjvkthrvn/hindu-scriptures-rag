#!/usr/bin/env python3
"""Batch-translate Sanskrit/Awadhi verses to English using Claude.

Translates verses that lack English translations, saves results to a
sidecar cache file, and can merge them back into verses_enriched.json.

Uses array indices (idx_NNN) as cache keys because many verse IDs are
duplicated in the source data.

Usage:
    python scripts/rag/translate_verses.py --source "Isha Upanishad"
    python scripts/rag/translate_verses.py --resume
    python scripts/rag/translate_verses.py --dry-run
    python scripts/rag/translate_verses.py --dry-run --source "Isha Upanishad"
    python scripts/rag/translate_verses.py --merge
    python scripts/rag/translate_verses.py --clean-fake
"""

import argparse
import json
import re
import signal
import sys
import time
from pathlib import Path

import anthropic
from dotenv import load_dotenv

# Project paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")
VERSES_FILE = PROJECT_ROOT / "final" / "verses_enriched.json"
CACHE_FILE = PROJECT_ROOT / "final" / "translations_cache.json"
CHECKPOINT_FILE = PROJECT_ROOT / "final" / "_translation_checkpoint.json"
ERROR_LOG = PROJECT_ROOT / "final" / "_translation_errors.log"

# Translation priority order
SOURCE_PRIORITY = [
    "Isha Upanishad",
    "Kena Upanishad",
    "Katha Upanishad",
    "Prashna Upanishad",
    "Mundaka Upanishad",
    "Mandukya Upanishad",
    "Taittiriya Upanishad",
    "Aitareya Upanishad",
    "Brihadaranyaka Upanishad",
    "Svetasvatara Upanishad",
    "Ramcharitmanas",
    "Yajurveda",
    "Atharvaveda",
    "Rigveda",
    "Valmiki Ramayana",
    "Mahabharata (Critical Edition)",
]

AWADHI_SOURCES = {"Ramcharitmanas"}

SANSKRIT_SYSTEM_PROMPT = (
    "You are a scholarly translator of classical Sanskrit texts. "
    "Translate accurately while maintaining readability. "
    "Preserve important Sanskrit terms (dharma, karma, brahman, atman) "
    "with parenthetical explanations on first use. "
    "Return ONLY a JSON object mapping the given verse labels (v1, v2, ...) "
    "to their English translations. No markdown, no explanation, just the JSON object."
)

AWADHI_SYSTEM_PROMPT = (
    "You are a scholarly translator of Tulsidas's Ramcharitmanas, written in Awadhi Hindi. "
    "Translate to modern English, maintaining the devotional bhakti tone. "
    "Preserve important terms (Ram, Sita, dharma, bhakti) with context where needed. "
    "Return ONLY a JSON object mapping the given verse labels (v1, v2, ...) "
    "to their English translations. No markdown, no explanation, just the JSON object."
)

# Batch sizes
UPANISHAD_BATCH_SIZE = 10  # Short verses
DEFAULT_BATCH_SIZE = 5     # Longer verses

# Rate-limit backoff schedule (seconds)
BACKOFF_SCHEDULE = [15, 30, 60, 120, 300]


# ── Graceful shutdown ────────────────────────────────────────────────────

_shutdown_requested = False


def _signal_handler(signum, frame):
    global _shutdown_requested
    if _shutdown_requested:
        print("\nForced exit.")
        sys.exit(1)
    _shutdown_requested = True
    print("\nShutdown requested — finishing current batch and saving...")


signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


# ── Cache & checkpoint helpers ───────────────────────────────────────────

def load_cache() -> dict[str, str]:
    """Load cache keyed by idx_NNN -> translation."""
    if CACHE_FILE.exists():
        with open(CACHE_FILE) as f:
            return json.load(f)
    return {}


def save_cache(cache: dict[str, str]) -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = CACHE_FILE.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(cache, f, ensure_ascii=False, indent=1)
    tmp.rename(CACHE_FILE)


def load_checkpoint() -> dict:
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE) as f:
            return json.load(f)
    return {}


def save_checkpoint(source: str, batch_index: int) -> None:
    CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump({"source": source, "batch_index": batch_index}, f)


def clear_checkpoint() -> None:
    if CHECKPOINT_FILE.exists():
        CHECKPOINT_FILE.unlink()


def log_error(batch_info: str, error: str) -> None:
    with open(ERROR_LOG, "a") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} | {batch_info} | {error}\n")


# ── Verse selection ──────────────────────────────────────────────────────

def load_verses() -> list[dict]:
    print(f"Loading {VERSES_FILE}...")
    with open(VERSES_FILE) as f:
        return json.load(f)


def is_fake_translation(verse: dict) -> bool:
    """Detect verses where translation is just a copy of sanskrit."""
    content = verse.get("content", {})
    translation = (content.get("translation") or "").strip()
    sanskrit = (content.get("sanskrit") or "").strip()
    if not translation or not sanskrit:
        return False
    return translation == sanskrit


def needs_translation(verse: dict, idx: int, cache: dict[str, str]) -> bool:
    """True if this verse has no real English translation and isn't cached."""
    cache_key = f"idx_{idx}"
    if cache_key in cache:
        return False

    content = verse.get("content", {})
    translation = (content.get("translation") or "").strip()
    if not translation:
        return True
    if is_fake_translation(verse):
        return True
    return False


def get_source_text(verse: dict) -> str:
    return verse.get("source", {}).get("text", "")


def get_sanskrit_text(verse: dict) -> str:
    content = verse.get("content", {})
    return (content.get("sanskrit") or "").strip()


def get_verse_location(verse: dict) -> str:
    src = verse.get("source", {})
    parts = [get_source_text(verse)]
    if src.get("chapter"):
        parts.append(f"chapter: {src['chapter']}")
    if src.get("section"):
        parts.append(f"section: {src['section']}")
    if src.get("verse"):
        parts.append(f"verse: {src['verse']}")
    return ", ".join(parts)


def select_verses(verses: list[dict], source_filter: str | None,
                  cache: dict[str, str]) -> list[tuple[int, dict]]:
    """Select (index, verse) pairs that need translation."""
    selected: list[tuple[int, dict]] = []
    for idx, v in enumerate(verses):
        src = get_source_text(v)
        if src == "Bhagavad Gita":
            continue
        if source_filter and src != source_filter:
            continue
        if needs_translation(v, idx, cache):
            selected.append((idx, v))

    # Sort by source priority, then by array index
    priority_map = {s: i for i, s in enumerate(SOURCE_PRIORITY)}
    selected.sort(key=lambda pair: (
        priority_map.get(get_source_text(pair[1]), 999),
        pair[0],
    ))
    return selected


# ── API call with retry ──────────────────────────────────────────────────

def build_batch_prompt(batch: list[tuple[int, dict]]) -> tuple[str, list[tuple[str, int]]]:
    """Build the user message for a batch. Returns (prompt, [(label, array_idx), ...])."""
    source = get_source_text(batch[0][1])
    lang = "Awadhi Hindi" if source in AWADHI_SOURCES else "Sanskrit"
    lines = [
        f"Translate the following {source} verses from {lang} to English.",
        "Return ONLY a JSON object mapping the verse label (v1, v2, ...) to translation.",
        "No other text.",
        "",
    ]
    label_map: list[tuple[str, int]] = []
    for i, (idx, v) in enumerate(batch, 1):
        label = f"v{i}"
        label_map.append((label, idx))
        loc = get_verse_location(v)
        text = get_sanskrit_text(v)
        lines.append("---")
        lines.append(f"[{label}]")
        lines.append(f"[{loc}]")
        lines.append(text)
        lines.append("")
    return "\n".join(lines), label_map


def parse_response(text: str, label_map: list[tuple[str, int]]) -> dict[str, str]:
    """Parse Claude's JSON response. Returns {idx_NNN: translation}."""
    cleaned = re.sub(r"^```(?:json)?\s*\n?", "", text.strip())
    cleaned = re.sub(r"\n?```\s*$", "", cleaned)

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError:
        m = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
        if m:
            result = json.loads(m.group())
        else:
            raise ValueError(f"Could not parse JSON from response: {text[:200]}")

    if not isinstance(result, dict):
        raise ValueError(f"Expected dict, got {type(result).__name__}")

    expected_labels = {label for label, _ in label_map}
    missing = expected_labels - set(result.keys())
    if missing:
        print(f"  Warning: {len(missing)} label(s) missing from response: {sorted(missing)[:5]}")

    # Map labels back to idx_NNN cache keys
    label_to_idx = {label: idx for label, idx in label_map}
    cache_updates: dict[str, str] = {}
    for label, translation in result.items():
        if label in label_to_idx and isinstance(translation, str) and translation.strip():
            cache_key = f"idx_{label_to_idx[label]}"
            cache_updates[cache_key] = translation.strip()

    return cache_updates


def translate_batch(client: anthropic.Anthropic,
                    batch: list[tuple[int, dict]],
                    model: str) -> dict[str, str]:
    """Translate a batch of verses. Returns {idx_NNN: translation}."""
    source = get_source_text(batch[0][1])
    system = AWADHI_SYSTEM_PROMPT if source in AWADHI_SOURCES else SANSKRIT_SYSTEM_PROMPT
    prompt, label_map = build_batch_prompt(batch)

    for attempt, backoff in enumerate(BACKOFF_SCHEDULE):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=4096,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text
            return parse_response(text, label_map)

        except anthropic.RateLimitError:
            print(f"  Rate limited — waiting {backoff}s (attempt {attempt + 1}/{len(BACKOFF_SCHEDULE)})...")
            time.sleep(backoff)
        except anthropic.APIStatusError as e:
            if e.status_code == 529:
                print(f"  API overloaded — waiting {backoff}s...")
                time.sleep(backoff)
            else:
                raise

    raise RuntimeError(f"Failed after {len(BACKOFF_SCHEDULE)} retries")


# ── Main pipeline ────────────────────────────────────────────────────────

def run_translate(source_filter: str | None, dry_run: bool, resume: bool,
                  model: str) -> None:
    cache = load_cache()
    verses = load_verses()

    todo = select_verses(verses, source_filter, cache)
    if not todo:
        print("No verses need translation. All done!")
        return

    # Group by source for reporting
    by_source: dict[str, int] = {}
    for _, v in todo:
        src = get_source_text(v)
        by_source[src] = by_source.get(src, 0) + 1

    print(f"\nVerses needing translation: {len(todo)}")
    for src, count in by_source.items():
        print(f"  {src}: {count}")

    if dry_run:
        print("\n[DRY RUN] No translations will be performed.")
        for idx, v in todo[:5]:
            text = get_sanskrit_text(v)[:100]
            print(f"  idx_{idx} ({v.get('id','')}): {text}...")
        if len(todo) > 5:
            print(f"  ... and {len(todo) - 5} more")
        return

    # Determine resume point
    start_batch = 0
    if resume:
        cp = load_checkpoint()
        if cp and cp.get("source") == (source_filter or "__all__"):
            start_batch = cp.get("batch_index", 0)
            print(f"Resuming from batch {start_batch}")

    # Determine batch size
    upanishad_names = {s for s in SOURCE_PRIORITY if "Upanishad" in s}
    all_upanishads = source_filter in upanishad_names if source_filter else False
    batch_size = UPANISHAD_BATCH_SIZE if all_upanishads else DEFAULT_BATCH_SIZE

    # Build batches
    batches: list[list[tuple[int, dict]]] = []
    for i in range(0, len(todo), batch_size):
        batches.append(todo[i : i + batch_size])

    print(f"\nTotal batches: {len(batches)} (batch size: {batch_size})")
    print(f"Model: {model}")

    client = anthropic.Anthropic()
    translated_count = 0
    cp_source = source_filter or "__all__"

    for batch_idx in range(start_batch, len(batches)):
        if _shutdown_requested:
            print(f"\nStopping at batch {batch_idx}. Run with --resume to continue.")
            break

        batch = batches[batch_idx]
        src = get_source_text(batch[0][1])
        print(f"\n[{batch_idx + 1}/{len(batches)}] Translating {len(batch)} {src} verses...")

        try:
            translations = translate_batch(client, batch, model)
            cache.update(translations)
            translated_count += len(translations)
            print(f"  Got {len(translations)} translations (total cached: {len(cache)})")
        except Exception as e:
            info = f"batch {batch_idx}, indices {[idx for idx, _ in batch]}"
            print(f"  ERROR: {e}")
            log_error(info, str(e))
            continue

        save_cache(cache)
        save_checkpoint(cp_source, batch_idx + 1)

        if batch_idx < len(batches) - 1:
            time.sleep(1)

    print(f"\nDone! Translated {translated_count} verses this run.")
    print(f"Total cached translations: {len(cache)}")
    print(f"Cache file: {CACHE_FILE}")

    if not _shutdown_requested:
        clear_checkpoint()


def run_merge() -> None:
    """Merge cached translations (keyed by idx_NNN) into verses_enriched.json."""
    cache = load_cache()
    if not cache:
        print("No translations in cache. Nothing to merge.")
        return

    print(f"Loading {VERSES_FILE}...")
    with open(VERSES_FILE) as f:
        verses = json.load(f)

    merged = 0
    for key, translation in cache.items():
        if not key.startswith("idx_"):
            continue
        idx = int(key[4:])
        if 0 <= idx < len(verses):
            verses[idx].setdefault("content", {})["translation"] = translation
            merged += 1

    print(f"Merged {merged} translations into {len(verses)} verses.")

    tmp = VERSES_FILE.with_suffix(".tmp")
    print(f"Writing {tmp}...")
    with open(tmp, "w") as f:
        json.dump(verses, f, ensure_ascii=False, indent=1)
    tmp.rename(VERSES_FILE)
    print(f"Saved to {VERSES_FILE}")
    print(f"\nNext step: re-index with 'python scripts/rag/indexer.py'")


def run_clean_fake() -> None:
    """Clear fake translations (where translation == sanskrit)."""
    print(f"Loading {VERSES_FILE}...")
    with open(VERSES_FILE) as f:
        verses = json.load(f)

    cleaned = 0
    for v in verses:
        if is_fake_translation(v):
            v["content"]["translation"] = ""
            cleaned += 1

    if cleaned == 0:
        print("No fake translations found.")
        return

    print(f"Cleared {cleaned} fake translations.")

    tmp = VERSES_FILE.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(verses, f, ensure_ascii=False, indent=1)
    tmp.rename(VERSES_FILE)
    print(f"Saved to {VERSES_FILE}")


def main():
    parser = argparse.ArgumentParser(
        description="Translate Hindu scripture verses to English using Claude"
    )
    parser.add_argument("--source", type=str, default=None,
                        help="Translate only this source (e.g., 'Isha Upanishad')")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be translated without calling the API")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from the last checkpoint")
    parser.add_argument("--merge", action="store_true",
                        help="Merge cached translations into verses_enriched.json")
    parser.add_argument("--clean-fake", action="store_true",
                        help="Clear fake translations (translation == sanskrit)")
    parser.add_argument("--model", type=str, default="claude-sonnet-4-5-20250929",
                        help="Anthropic model to use (default: claude-sonnet-4-5-20250929)")

    args = parser.parse_args()

    if args.merge:
        run_merge()
    elif args.clean_fake:
        run_clean_fake()
    else:
        run_translate(args.source, args.dry_run, args.resume, args.model)


if __name__ == "__main__":
    main()
