#!/usr/bin/env python3
"""
Comprehensive JSON validation for Hindu Scriptures RAG pipeline.

Validates:
  1. Raw DharmicData JSON files - structure and parseability
  2. Final verses JSON - schema compliance (id, source, content, metadata, provenance)
  3. Processed intermediate JSONs
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent))
from utils.quality_checker import VersValidator


def validate_raw_dharmic_json(filepath: Path) -> Tuple[bool, List[str]]:
    """Validate raw DharmicData JSON structure."""
    errors = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if data is None:
            errors.append("File is null/empty")
            return False, errors
        # DharmicData can be list of verses or dict with chapter structure
        if isinstance(data, list):
            if len(data) == 0:
                errors.append("Empty list")
            else:
                # Check first item has expected structure
                sample = data[0]
                if isinstance(sample, dict):
                    if 'content' in sample or 'sanskrit' in str(sample).lower() or 'translation' in str(sample).lower():
                        pass  # Valid structure
                    elif 'verse' in sample or 'text' in sample or 'mantra' in sample:
                        pass  # Alternate structure
                    else:
                        errors.append(f"Unexpected structure: {list(sample.keys())[:5]}")
        elif isinstance(data, dict):
            # Could be chapter with verses array, BhagavadGitaChapter, or verse dict
            vals = list(data.values()) if data else []
            has_list = any(isinstance(v, list) for v in vals)
            if ('verses' in data or 'chapter' in data or has_list or
                    any(k.isdigit() for k in data.keys())):
                pass
            else:
                errors.append(f"Unexpected dict keys: {list(data.keys())[:5]}")
        else:
            errors.append(f"Root must be list or dict, got {type(data)}")
        return len(errors) == 0, errors
    except json.JSONDecodeError as e:
        return False, [f"JSON decode error: {e}"]
    except Exception as e:
        return False, [f"Error: {e}"]


def validate_verse_schema(verse: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate a verse against unified schema."""
    return VersValidator.validate_verse(verse)


def validate_final_verses(filepath: Path) -> Dict[str, Any]:
    """Validate final verses.json schema compliance."""
    result = {
        'file': str(filepath),
        'valid_json': True,
        'total': 0,
        'valid': 0,
        'invalid': 0,
        'errors': [],
        'by_source': {}
    }
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            verses = json.load(f)
        if not isinstance(verses, list):
            result['errors'].append("Root must be a list")
            result['valid_json'] = False
            return result
        result['total'] = len(verses)
        for i, verse in enumerate(verses):
            is_valid, errs = validate_verse_schema(verse)
            if is_valid:
                result['valid'] += 1
                src = verse.get('source', {}).get('text', 'Unknown')
                result['by_source'][src] = result['by_source'].get(src, 0) + 1
            else:
                result['invalid'] += 1
                if len(result['errors']) < 5:
                    result['errors'].append({
                        'id': verse.get('id', f'idx_{i}'),
                        'errors': errs[:3]
                    })
    except json.JSONDecodeError as e:
        result['valid_json'] = False
        result['errors'].append(f"JSON decode error: {e}")
    except Exception as e:
        result['valid_json'] = False
        result['errors'].append(f"Error: {e}")
    return result


def main():
    base = Path(__file__).parent.parent
    raw_dir = base / 'raw' / 'dharmicdata'
    final_dir = base / 'final'
    processed_dir = base / 'processed'

    print("\n" + "=" * 70)
    print("  HINDU SCRIPTURES RAG - JSON VALIDATION REPORT")
    print("=" * 70)

    # 1. Validate raw DharmicData JSONs
    print("\n[1] Raw DharmicData JSON files")
    print("-" * 50)
    raw_ok = 0
    raw_fail = 0
    raw_failures = []
    if raw_dir.exists():
        for jf in raw_dir.rglob('*.json'):
            ok, errs = validate_raw_dharmic_json(jf)
            if ok:
                raw_ok += 1
            else:
                raw_fail += 1
                if len(raw_failures) < 5:
                    raw_failures.append((jf.name, errs[:2]))
        print(f"  Valid: {raw_ok}")
        print(f"  Invalid: {raw_fail}")
        for name, errs in raw_failures:
            print(f"    - {name}: {errs}")
    else:
        print("  raw/dharmicdata not found")

    # 2. Validate final verses
    print("\n[2] Final output (verses.json)")
    print("-" * 50)
    verses_file = final_dir / 'verses.json'
    if verses_file.exists():
        r = validate_final_verses(verses_file)
        pct = 100 * r['valid'] / max(r['total'], 1)
        print(f"  Total verses: {r['total']:,}")
        print(f"  Schema-valid: {r['valid']:,} ({pct:.1f}%)")
        print(f"  Invalid: {r['invalid']:,}")
        if r['by_source']:
            print("  By source:")
            for src, count in sorted(r['by_source'].items(), key=lambda x: -x[1])[:15]:
                print(f"    - {src}: {count:,}")
        if r['errors']:
            print("  Sample errors:")
            for e in r['errors'][:3]:
                print(f"    {e}")
    else:
        print("  verses.json not found")

    # 3. Validate other final JSONs
    for fname in ['verses_enriched.json', 'verses_deduped.json']:
        fp = final_dir / fname
        if fp.exists():
            print(f"\n[2b] {fname}")
            r = validate_final_verses(fp)
            pct = 100 * r['valid'] / max(r['total'], 1)
            print(f"  Valid: {r['valid']:,}/{r['total']:,} ({pct:.1f}%)")

    # 4. Processed tier JSONs
    print("\n[3] Processed JSON files")
    print("-" * 50)
    for jf in processed_dir.rglob('*.json'):
        try:
            with open(jf, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list):
                valid = sum(1 for v in data if validate_verse_schema(v)[0])
                print(f"  {jf.relative_to(processed_dir)}: {valid}/{len(data)} verses valid")
            else:
                print(f"  {jf.relative_to(processed_dir)}: OK (not verse list)")
        except Exception as e:
            print(f"  {jf.name}: ERROR - {e}")

    # 5. Indian-scriptures - check CSV (not JSON but report)
    is_dir = base / 'raw' / 'indian-scriptures'
    if is_dir.exists():
        csv_count = len(list((is_dir / 'data' / 'processed' / 'upanishads').rglob('*.csv')))
        print(f"\n[4] Indian-Scriptures (Upanishads)")
        print(f"  CSV files: {csv_count}")

    print("\n" + "=" * 70)
    print("  VALIDATION COMPLETE")
    print("=" * 70 + "\n")

    # Exit with error only on critical failures
    if raw_fail > 0 and raw_ok == 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
