#!/usr/bin/env python3
"""
Verify that all verses from raw sources are present in the final verses.json.

Compares verse IDs from freshly parsing raw data against final/verses.json
to detect any missing verses.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from parse_all_scriptures import (
    parse_atharvaveda,
    parse_bhagavad_gita,
    parse_mahabharata_critical,
    parse_ramcharitmanas,
    parse_rigveda,
    parse_upanishads,
    parse_valmiki_ramayana,
    parse_yajurveda,
)


def main():
    base_dir = Path(__file__).parent.parent
    final_file = base_dir / "final" / "verses.json"

    if not final_file.exists():
        print("ERROR: final/verses.json not found")
        sys.exit(1)

    print("\n" + "=" * 70)
    print("  VERSE COMPLETENESS CHECK")
    print("=" * 70)

    # Load final verses
    with open(final_file, encoding="utf-8") as f:
        final_verses = json.load(f)

    final_by_id = {v["id"]: v for v in final_verses}
    final_ids = set(final_by_id.keys())
    final_by_source = {}
    for v in final_verses:
        src = v.get("source", {}).get("text", "Unknown")
        final_by_source.setdefault(src, set()).add(v["id"])

    print(f"\nFinal verses.json: {len(final_verses):,} total verses")
    print(f"Unique IDs: {len(final_ids):,}")

    # Parse raw data to get expected verse IDs
    # Only sources actually in the pipeline (parse_all_scriptures main())
    parsers = [
        ("Bhagavad Gita", parse_bhagavad_gita),
        ("Upanishads", parse_upanishads),
        ("Rigveda", parse_rigveda),
        ("Atharvaveda", parse_atharvaveda),
        ("Yajurveda", parse_yajurveda),
        ("Mahabharata (Critical Edition)", parse_mahabharata_critical),
        ("Valmiki Ramayana", parse_valmiki_ramayana),
        ("Ramcharitmanas", parse_ramcharitmanas),
    ]

    all_ok = True
    missing_total = 0

    # ID prefix for each source
    prefix_map = {
        "Bhagavad Gita": "bg_",
        "Upanishads": "upanishad_",
        "Rigveda": "rv_",
        "Atharvaveda": "av_",
        "Yajurveda": "yv_",
        "Mahabharata": "mbh_",
        "Mahabharata (Critical Edition)": "mbhce_",
        "Valmiki Ramayana": "vr_",
        "Ramcharitmanas": "rcm_",
    }

    for name, parser_fn in parsers:
        try:
            verses = parser_fn(base_dir)
            expected_ids = {v["id"] for v in verses}
            prefix = prefix_map.get(name, "")

            # Get final IDs for this source by prefix
            final_for_source = {i for i in final_ids if i.startswith(prefix)}

            missing = expected_ids - final_for_source
            extra = final_for_source - expected_ids

            missing_count = len(missing)
            extra_count = len(extra)

            if missing_count > 0:
                all_ok = False
                missing_total += missing_count
                print(f"\n  [{name}]")
                print(
                    f"    Expected: {len(expected_ids):,}  |  In final: {len(final_for_source):,}"
                )
                print(f"    MISSING: {missing_count:,} verses not in final/verses.json")
                # Show first 10 missing IDs
                sample = sorted(missing)[:10]
                for mid in sample:
                    print(f"      - {mid}")
                if missing_count > 10:
                    print(f"      ... and {missing_count - 10} more")
            else:
                status = "OK"
                if extra_count > 0:
                    status += f" (+{extra_count} extra in final)"
                print(f"\n  [{name}] {len(expected_ids):,} verses  {status}")

        except Exception as e:
            print(f"\n  [{name}] ERROR: {e}")
            all_ok = False

    # Also check for duplicate IDs in final
    from collections import Counter

    id_counts = Counter(v["id"] for v in final_verses)
    dups = [(i, c) for i, c in id_counts.items() if c > 1]
    if dups:
        print(f"\n  DUPLICATE IDs in final: {len(dups)}")
        for vid, cnt in dups[:5]:
            print(f"      {vid}: appears {cnt} times")
        all_ok = False

    # Check for empty content
    empty_content = [
        v
        for v in final_verses
        if not (
            v.get("content", {}).get("sanskrit", "").strip()
            or v.get("content", {}).get("translation", "").strip()
        )
    ]
    if empty_content:
        print(f"\n  WARNING: {len(empty_content)} verses have empty sanskrit AND translation")
        for v in empty_content[:3]:
            print(f"      {v.get('id', '?')}")

    print("\n" + "=" * 70)
    if all_ok:
        print("  RESULT: All expected verses are present in final/verses.json")
    else:
        print(f"  RESULT: Found {missing_total} missing verse(s) - see details above")
    print("=" * 70 + "\n")

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
