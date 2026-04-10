#!/usr/bin/env python3
"""Quick parser for Bhagavad Gita from DharmicData."""

import json
from datetime import datetime
from pathlib import Path


def parse_gita_chapters():
    """Parse all Gita chapter files."""
    base_dir = Path.home() / "hindu-scriptures-rag"
    gita_dir = base_dir / "raw" / "dharmicdata" / "SrimadBhagvadGita"

    all_verses = []

    for chapter_file in sorted(gita_dir.glob("bhagavad_gita_chapter_*.json")):
        print(f"Parsing {chapter_file.name}...")

        with open(chapter_file, encoding="utf-8") as f:
            data = json.load(f)

        chapter_verses = data.get("BhagavadGitaChapter", [])

        for verse_data in chapter_verses:
            chapter = verse_data.get("chapter")
            verse_num = verse_data.get("verse")
            text = verse_data.get("text", "")
            translations = verse_data.get("translations", {})

            # Get first available translation
            translation = ""
            for key in ["swami sivananda", "swami gambir ananda", "swami ramsukhdas"]:
                if key in translations:
                    translation = translations[key]
                    break

            if not translation:
                # Get any translation
                for trans in translations.values():
                    if trans and "No such translation" not in trans:
                        translation = trans
                        break

            verse_id = f"bg_{chapter}_{verse_num}"

            verse_obj = {
                "id": verse_id,
                "source": {
                    "text": "Bhagavad Gita",
                    "chapter": chapter,
                    "chapter_name": f"Chapter {chapter}",
                    "verse": verse_num,
                    "section": None,
                },
                "content": {
                    "sanskrit": text.split("\n\n")[0] if "\n\n" in text else text,
                    "transliteration": "",
                    "translation": translation,
                    "word_by_word": {},
                },
                "metadata": {
                    "category": "smriti",
                    "tradition": "vedanta",
                    "themes": ["bhagavad_gita"],
                    "philosophical_schools": ["advaita", "dvaita", "vishishtadvaita"],
                },
                "commentaries": [],
                "provenance": {
                    "download_source": "dharmic-data",
                    "original_url": "https://github.com/bhavykhatri/DharmicData",
                    "license": "ODbL-1.0",
                    "processed_date": datetime.now().isoformat(),
                },
            }

            all_verses.append(verse_obj)

    print(f"\nTotal verses parsed: {len(all_verses)}")

    # Save
    output_dir = base_dir / "processed" / "tier1-essential"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "bhagavad_gita.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_verses, f, ensure_ascii=False, indent=2)

    print(f"Saved to: {output_file}")
    return len(all_verses)


if __name__ == "__main__":
    parse_gita_chapters()
