#!/usr/bin/env python3
"""
Comprehensive parser for all Hindu scripture formats in the repository.

Handles:
  - Bhagavad Gita (DharmicData JSON, per-chapter files)
  - Rigveda, Atharvaveda (DharmicData JSON, verses in combined text field)
  - Yajurveda (DharmicData JSON, verses in combined text field)
  - Mahabharata (DharmicData JSON, per-shloka entries)
  - Mahabharata Critical Edition (DharmicData JSON, dict with half-verse keys)
  - Valmiki Ramayana (DharmicData JSON, per-shloka entries)
  - Ramcharitmanas (DharmicData JSON, mixed type entries)
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from parsers.parse_upanishad_csv import UpanishadCSVParser
from utils.unicode_utils import normalize_devanagari

PROVENANCE_DHARMICDATA = {
    "download_source": "dharmicdata",
    "original_url": "https://github.com/bhavykhatri/DharmicData",
    "license": "ODbL-1.0",
}


def make_verse(
    verse_id,
    source_text,
    chapter,
    chapter_name,
    verse_num,
    sanskrit,
    translation="",
    transliteration="",
    category="shruti",
    tradition="vedic",
    themes=None,
    schools=None,
    section=None,
    commentaries=None,
    translations=None,
):
    """Create a verse dict in unified schema."""
    return {
        "id": verse_id,
        "source": {
            "text": source_text,
            "chapter": chapter,
            "chapter_name": chapter_name,
            "verse": verse_num,
            "section": section,
        },
        "content": {
            "sanskrit": normalize_devanagari(sanskrit),
            "transliteration": transliteration,
            "translation": translation,
            "translations": translations or {},
            "word_by_word": {},
        },
        "metadata": {
            "category": category,
            "tradition": tradition,
            "themes": themes or [],
            "philosophical_schools": schools or [],
        },
        "commentaries": commentaries or [],
        "provenance": {**PROVENANCE_DHARMICDATA, "processed_date": datetime.now().isoformat()},
    }


def split_verses_by_marker(text):
    """Split combined verse text by Devanagari verse markers like ॥1॥ or ॥१॥."""
    # Match verse markers: ॥N॥ where N is Devanagari or ASCII digits
    parts = re.split(r"॥\s*(\d+|[०-९]+)\s*॥", text)

    verses = []
    # parts alternates: [text_before, verse_num, text_before, verse_num, ...]
    for i in range(0, len(parts) - 1, 2):
        verse_text = parts[i].strip()
        verse_num_str = parts[i + 1]

        # Convert Devanagari digits
        devanagari_digits = "०१२३४५६७८९"
        verse_num = 0
        for ch in verse_num_str:
            idx = devanagari_digits.find(ch)
            if idx >= 0:
                verse_num = verse_num * 10 + idx
            elif ch.isdigit():
                verse_num = verse_num * 10 + int(ch)

        if verse_text and verse_num > 0:
            # Remove header lines (rishi, devata, chandas info)
            lines = verse_text.split("\n")
            clean_lines = []
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                # Skip header-like lines (short lines with metadata)
                if (
                    verse_num == 1
                    and not clean_lines
                    and not any(c in line for c in "।॥")
                    and len(line) < 80
                ):
                    continue
                clean_lines.append(line)
            verse_text = " ".join(clean_lines)

            if verse_text:
                verses.append((verse_num, verse_text))

    return verses


# =============================================================================
# BHAGAVAD GITA
# =============================================================================

# Map commentator names to philosophical school
COMMENTATOR_SCHOOLS = {
    "Sri Shankaracharya": "advaita",
    "Sri Ramanuja": "vishishtadvaita",
    "Sri Madhavacharya": "dvaita",
    "Sri Vallabhacharya": "shuddhadvaita",
    "Sri Abhinavgupta": "kashmir_shaivism",
    "Swami Chinmayananda": "advaita",
    "Sri Jayatritha": "dvaita",
    "Sri Sridhara Swami": "advaita",
    "Sri Anandgiri": "advaita",
    "Sri Madhusudan Saraswati": "advaita",
    "Swami Sivananda": "advaita",
    "Swami Gambirananda": "advaita",
    "Swami Ramsukhdas": "common",
    "Sri Harikrishnadas Goenka": "common",
    "Sri Dhanpati": "common",
    "Sri Neelkanth": "common",
    "Sri Purushottamji": "shuddhadvaita",
    "Dr. S. Sankaranarayan": "common",
    "Swami Adidevananda": "vishishtadvaita",
}


def parse_bhagavad_gita(base_dir: Path) -> list[dict[str, Any]]:
    """Parse Bhagavad Gita from DharmicData chapter files."""
    verses = []
    gita_dir = base_dir / "raw" / "dharmicdata" / "SrimadBhagvadGita"

    if not gita_dir.exists():
        return verses

    commentary_count = 0

    for chapter_file in sorted(gita_dir.glob("bhagavad_gita_chapter_*.json")):
        try:
            with open(chapter_file, encoding="utf-8") as f:
                data = json.load(f)

            for verse_data in data.get("BhagavadGitaChapter", []):
                ch = verse_data.get("chapter", 0)
                v = verse_data.get("verse", 0)
                text = verse_data.get("text", "").strip()
                raw_translations = verse_data.get("translations", {})

                # Pick best English translation for primary display
                translation = ""
                for key in [
                    "swami sivananda",
                    "shri purohit swami",
                    "swami gambirananda",
                    "dr. s. sankaranarayan",
                ]:
                    if key in raw_translations:
                        t = raw_translations[key].strip()
                        if t and not t.startswith("।।"):
                            translation = t
                            break

                # Store all translations
                all_translations = {}
                for tkey, tval in raw_translations.items():
                    tval_clean = tval.strip() if tval else ""
                    if tval_clean and not tval_clean.startswith("।।"):
                        all_translations[tkey] = tval_clean

                # Extract commentaries with school mapping
                raw_commentaries = verse_data.get("commentaries", {})
                commentaries = []
                for author, comm_text in raw_commentaries.items():
                    comm_text_clean = (comm_text or "").strip()
                    if not comm_text_clean:
                        continue
                    school = COMMENTATOR_SCHOOLS.get(author, "common")
                    commentaries.append(
                        {
                            "author": author,
                            "school": school,
                            "text": comm_text_clean,
                        }
                    )
                    commentary_count += 1

                if not text:
                    continue

                verses.append(
                    make_verse(
                        f"bg_{ch}_{v}",
                        "Bhagavad Gita",
                        ch,
                        f"Chapter {ch}",
                        v,
                        text,
                        translation,
                        category="smriti",
                        tradition="vedanta",
                        schools=["advaita", "dvaita", "vishishtadvaita"],
                        commentaries=commentaries,
                        translations=all_translations,
                    )
                )
        except Exception as e:
            print(f"  Error: {chapter_file.name}: {e}")

    print(f"  -> {commentary_count} commentary entries extracted")
    return verses


# =============================================================================
# VEDAS (Rigveda, Atharvaveda, Yajurveda)
# =============================================================================


def parse_rigveda(base_dir: Path) -> list[dict[str, Any]]:
    """Parse Rigveda. Each sukta has all verses in one text field."""
    verses = []
    rig_dir = base_dir / "raw" / "dharmicdata" / "Rigveda"
    if not rig_dir.exists():
        return verses

    for mandala_file in sorted(rig_dir.glob("rigveda_mandala_*.json")):
        try:
            with open(mandala_file, encoding="utf-8") as f:
                data = json.load(f)

            for sukta_data in data:
                mandala = sukta_data.get("mandala", 0)
                sukta = sukta_data.get("sukta", 0)
                text = sukta_data.get("text", "")

                for verse_num, verse_text in split_verses_by_marker(text):
                    verses.append(
                        make_verse(
                            f"rv_{mandala}_{sukta}_{verse_num}",
                            "Rigveda",
                            mandala,
                            f"Mandala {mandala}",
                            verse_num,
                            verse_text,
                            category="shruti",
                            tradition="vedic",
                            themes=["vedic_hymns", "mantras"],
                            section=f"Sukta {sukta}",
                        )
                    )
        except Exception as e:
            print(f"  Error: {mandala_file.name}: {e}")

    return verses


def parse_atharvaveda(base_dir: Path) -> list[dict[str, Any]]:
    """Parse Atharvaveda. Each sukta has all verses in one text field."""
    verses = []
    av_dir = base_dir / "raw" / "dharmicdata" / "AtharvaVeda"
    if not av_dir.exists():
        return verses

    for kaanda_file in sorted(av_dir.glob("atharvaveda_kaanda_*.json")):
        try:
            with open(kaanda_file, encoding="utf-8") as f:
                data = json.load(f)

            for sukta_data in data:
                kaanda = sukta_data.get("kaanda", 0)
                sukta = sukta_data.get("sukta", 0)
                text = sukta_data.get("text", "")

                for verse_num, verse_text in split_verses_by_marker(text):
                    verses.append(
                        make_verse(
                            f"av_{kaanda}_{sukta}_{verse_num}",
                            "Atharvaveda",
                            kaanda,
                            f"Kaanda {kaanda}",
                            verse_num,
                            verse_text,
                            category="shruti",
                            tradition="vedic",
                            themes=["vedic_hymns", "mantras", "healing"],
                            section=f"Sukta {sukta}",
                        )
                    )
        except Exception as e:
            print(f"  Error: {kaanda_file.name}: {e}")

    return verses


def parse_yajurveda(base_dir: Path) -> list[dict[str, Any]]:
    """Parse Yajurveda. Each adhyaya has all verses in one text field."""
    verses = []
    yv_dir = base_dir / "raw" / "dharmicdata" / "Yajurveda"
    if not yv_dir.exists():
        return verses

    for yv_file in sorted(yv_dir.glob("*.json")):
        try:
            with open(yv_file, encoding="utf-8") as f:
                data = json.load(f)

            samhita_name = yv_file.stem  # e.g. vajasneyi_madhyadina_samhita

            for chapter_data in data:
                adhyaya = chapter_data.get("adhyaya", 0)
                text = chapter_data.get("text", "")

                for verse_num, verse_text in split_verses_by_marker(text):
                    verses.append(
                        make_verse(
                            f"yv_{adhyaya}_{verse_num}",
                            "Yajurveda",
                            adhyaya,
                            f"Adhyaya {adhyaya}",
                            verse_num,
                            verse_text,
                            category="shruti",
                            tradition="vedic",
                            themes=["vedic_hymns", "yajnas"],
                            section=samhita_name.replace("_", " ").title(),
                        )
                    )
        except Exception as e:
            print(f"  Error: {yv_file.name}: {e}")

    return verses


# =============================================================================
# MAHABHARATA
# =============================================================================


def parse_mahabharata(base_dir: Path) -> list[dict[str, Any]]:
    """Parse Mahabharata from per-shloka JSON files."""
    verses = []
    mbh_dir = base_dir / "raw" / "dharmicdata" / "Mahabharata"
    if not mbh_dir.exists():
        return verses

    parva_names = {
        1: "Adi Parva",
        2: "Sabha Parva",
        3: "Vana Parva",
        4: "Virata Parva",
        5: "Udyoga Parva",
        6: "Bhishma Parva",
        7: "Drona Parva",
        8: "Karna Parva",
        9: "Shalya Parva",
        10: "Sauptika Parva",
        11: "Stri Parva",
        12: "Shanti Parva",
        13: "Anushasana Parva",
        14: "Ashvamedhika Parva",
        15: "Ashramvasika Parva",
        16: "Mausala Parva",
        17: "Mahaprasthanika Parva",
        18: "Svargarohana Parva",
    }

    for book_file in sorted(mbh_dir.glob("mahabharata_book_*.json")):
        try:
            with open(book_file, encoding="utf-8") as f:
                data = json.load(f)

            for entry in data:
                book = entry.get("book", 0)
                chapter = entry.get("chapter", 0)
                shloka = entry.get("shloka", 0)
                text = entry.get("text", "").strip()

                if not text:
                    continue

                parva = parva_names.get(book, f"Book {book}")
                verses.append(
                    make_verse(
                        f"mbh_{book}_{chapter}_{shloka}",
                        "Mahabharata",
                        book,
                        parva,
                        shloka,
                        text,
                        category="itihasa",
                        tradition="common",
                        themes=["dharma", "duty", "morality"],
                        section=f"Chapter {chapter}",
                    )
                )
        except Exception as e:
            print(f"  Error: {book_file.name}: {e}")

    return verses


def parse_mahabharata_critical(base_dir: Path) -> list[dict[str, Any]]:
    """Parse Mahabharata Critical Edition (dict with half-verse keys)."""
    verses = []
    ce_dir = base_dir / "raw" / "dharmicdata" / "Mahabharata" / "Critical Edition"
    if not ce_dir.exists():
        return verses

    for mbh_file in sorted(ce_dir.glob("MBh*.json")):
        if mbh_file.name == "MBh18UR.json":
            continue
        try:
            with open(mbh_file, encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, dict):
                continue

            # Group half-verses by shloka number
            # Keys like 01001001a, 01001001c -> book 01, chapter 001, shloka 001
            grouped = {}
            for key, val in data.items():
                # Extract book, chapter, shloka from key
                match = re.match(r"(\d{2})(\d{3})(\d{3})", key)
                if not match:
                    continue
                book = int(match.group(1))
                chapter = int(match.group(2))
                shloka = int(match.group(3))
                group_key = (book, chapter, shloka)

                if group_key not in grouped:
                    grouped[group_key] = {"ud": [], "ur": []}

                text_data = val.get("text", {})
                if isinstance(text_data, dict):
                    ud = text_data.get("ud", "").strip()
                    ur = text_data.get("ur", "").strip()
                    if ud:
                        grouped[group_key]["ud"].append(ud)
                    if ur:
                        grouped[group_key]["ur"].append(ur)

            for (book, chapter, shloka), parts in sorted(grouped.items()):
                sanskrit = " ".join(parts["ud"])
                transliteration = " ".join(parts["ur"])

                if not sanskrit:
                    continue

                verses.append(
                    make_verse(
                        f"mbhce_{book}_{chapter}_{shloka}",
                        "Mahabharata (Critical Edition)",
                        book,
                        f"Book {book}",
                        shloka,
                        sanskrit,
                        transliteration=transliteration,
                        category="itihasa",
                        tradition="common",
                        themes=["dharma", "duty", "morality"],
                        section=f"Chapter {chapter}",
                    )
                )
        except Exception as e:
            print(f"  Error: {mbh_file.name}: {e}")

    return verses


# =============================================================================
# RAMAYANA
# =============================================================================


def parse_valmiki_ramayana(base_dir: Path) -> list[dict[str, Any]]:
    """Parse Valmiki Ramayana. Each entry is a single shloka."""
    verses = []
    rama_dir = base_dir / "raw" / "dharmicdata" / "ValmikiRamayana"
    if not rama_dir.exists():
        return verses

    kanda_names = {
        "balakanda": "Bala Kanda",
        "ayodhyakanda": "Ayodhya Kanda",
        "aranyakanda": "Aranya Kanda",
        "kishkindhakanda": "Kishkindha Kanda",
        "sundarakanda": "Sundara Kanda",
        "yudhhakanda": "Yuddha Kanda",
        "uttarakanda": "Uttara Kanda",
    }

    kanda_order = {
        "balakanda": 1,
        "ayodhyakanda": 2,
        "aranyakanda": 3,
        "kishkindhakanda": 4,
        "sundarakanda": 5,
        "yudhhakanda": 6,
        "uttarakanda": 7,
    }

    for rama_file in sorted(rama_dir.glob("*.json")):
        try:
            with open(rama_file, encoding="utf-8") as f:
                data = json.load(f)

            for entry in data:
                kaanda = entry.get("kaanda", "")
                sarg = entry.get("sarg", 0)
                shloka = entry.get("shloka", 0)
                text = entry.get("text", "").strip()

                if not text:
                    continue

                kanda_num = kanda_order.get(kaanda, 0)
                kanda_display = kanda_names.get(kaanda, kaanda)

                verses.append(
                    make_verse(
                        f"vr_{kanda_num}_{sarg}_{shloka}",
                        "Valmiki Ramayana",
                        kanda_num,
                        kanda_display,
                        shloka,
                        text,
                        category="itihasa",
                        tradition="common",
                        themes=["dharma", "devotion", "virtue", "duty"],
                        section=f"Sarga {sarg}",
                    )
                )
        except Exception as e:
            print(f"  Error: {rama_file.name}: {e}")

    return verses


def parse_ramcharitmanas(base_dir: Path) -> list[dict[str, Any]]:
    """Parse Ramcharitmanas. Mixed entry types (shloka, doha, chaupai)."""
    verses = []
    rcm_dir = base_dir / "raw" / "dharmicdata" / "Ramcharitmanas"
    if not rcm_dir.exists():
        return verses

    kanda_order = {
        "बालकाण्ड": 1,
        "अयोध्याकाण्ड": 2,
        "अरण्यकाण्ड": 3,
        "किष्किन्धाकाण्ड": 4,
        "सुंदरकाण्ड": 5,
        "लंकाकाण्ड": 6,
        "उत्तरकाण्ड": 7,
    }

    kanda_english = {
        "बालकाण्ड": "Bala Kanda",
        "अयोध्याकाण्ड": "Ayodhya Kanda",
        "अरण्यकाण्ड": "Aranya Kanda",
        "किष्किन्धाकाण्ड": "Kishkindha Kanda",
        "सुंदरकाण्ड": "Sundara Kanda",
        "लंकाकाण्ड": "Lanka Kanda",
        "उत्तरकाण्ड": "Uttara Kanda",
    }

    for rcm_file in sorted(rcm_dir.glob("*_data.json")):
        try:
            with open(rcm_file, encoding="utf-8") as f:
                data = json.load(f)

            for idx, entry in enumerate(data, 1):
                entry_type = entry.get("type", "").strip()
                content = entry.get("content", "").strip()
                kaand = entry.get("kaand", "").strip()

                if not content:
                    continue

                kanda_num = kanda_order.get(kaand, 0)
                kanda_en = kanda_english.get(kaand, kaand)

                verses.append(
                    make_verse(
                        f"rcm_{kanda_num}_{idx}",
                        "Ramcharitmanas",
                        kanda_num,
                        kanda_en,
                        idx,
                        content,
                        category="smriti",
                        tradition="bhakti",
                        themes=["devotion", "dharma", "rama_bhakti"],
                        section=entry_type,
                    )
                )
        except Exception as e:
            print(f"  Error: {rcm_file.name}: {e}")

    return verses


def parse_upanishads(base_dir):
    """Parse Upanishads from indian-scriptures CSV files."""
    indian_scriptures = base_dir / "raw" / "indian-scriptures"
    if not indian_scriptures.exists():
        return []
    parser = UpanishadCSVParser(indian_scriptures)
    count, verses = parser.parse_directory()
    return verses


# =============================================================================
# MAIN
# =============================================================================


def main():
    base_dir = Path.home() / "hindu-scriptures-rag"

    print("\n" + "=" * 70)
    print("  HINDU SCRIPTURE RAG - COMPREHENSIVE PARSING")
    print("=" * 70)

    results = {}

    parsers = [
        ("Bhagavad Gita", parse_bhagavad_gita),
        ("Upanishads", parse_upanishads),
        ("Rigveda", parse_rigveda),
        ("Atharvaveda", parse_atharvaveda),
        ("Yajurveda", parse_yajurveda),
        # Regular Mahabharata dropped — Critical Edition has Devanagari + IAST
        ("Mahabharata (Critical Edition)", parse_mahabharata_critical),
        ("Valmiki Ramayana", parse_valmiki_ramayana),
        ("Ramcharitmanas", parse_ramcharitmanas),
    ]

    all_verses = []
    for i, (name, parser_fn) in enumerate(parsers, 1):
        print(f"\n[{i}/{len(parsers)}] Parsing {name}...")
        try:
            verses = parser_fn(base_dir)
            all_verses.extend(verses)
            results[name] = len(verses)
            print(f"  -> {len(verses)} verses")
        except Exception as e:
            print(f"  -> ERROR: {e}")
            results[name] = 0

    # Save output
    output_file = base_dir / "final" / "verses.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_verses, f, ensure_ascii=False, indent=2)

    # Print summary
    print("\n" + "=" * 70)
    print("  PARSING COMPLETE")
    print("=" * 70)
    print(f"\n{'Scripture':<40} {'Verses':>10}")
    print("-" * 52)
    for name, count in results.items():
        print(f"  {name:<38} {count:>10,}")
    print("-" * 52)
    print(f"  {'TOTAL':<38} {len(all_verses):>10,}")
    print(f"\nSaved to: {output_file}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
