"""Parse Yoga Sutras from sacred-texts HTML (BonGiovanni translation)."""

import re
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup

# Pattern: "1.1 " or "1.2." - captures chapter, sutra, and text until next sutra or end
SUTRA_PATTERN = re.compile(r"(\d+)\.(\d+)\.?\s*(?:(.+?)(?=\s*\d+\.\d+\.?\s|$))", re.DOTALL)

CHAPTER_NAMES = {
    1: "Samadhi Pada (Contemplation)",
    2: "Sadhana Pada (Practice)",
    3: "Vibhuti Pada (Powers)",
    4: "Kaivalya Pada (Liberation)",
}


def parse_yoga_sutras_html(html_path: Path) -> list[dict]:
    """Extract Yoga Sutras verses from HTML into RAG verse schema.

    Handles HTML where multiple sutras can appear in one <p> block.
    """
    text = html_path.read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(text, "html.parser")
    for script in soup(["script", "style"]):
        script.decompose()

    body_text = soup.get_text(separator="\n", strip=True)
    verses = []
    seen = set()

    for m in SUTRA_PATTERN.finditer(body_text):
        chapter = int(m.group(1))
        sutra = int(m.group(2))
        trans = re.sub(r"\s+", " ", m.group(3)).strip()
        if chapter > 4 or chapter < 1 or len(trans) < 5:
            continue
        key = (chapter, sutra)
        if key in seen:
            continue
        seen.add(key)

        verses.append({
            "id": f"ys_{chapter}_{sutra}",
            "source": {
                "text": "Yoga Sutras of Patanjali",
                "chapter": chapter,
                "chapter_name": CHAPTER_NAMES.get(chapter, f"Part {chapter}"),
                "verse": sutra,
            },
            "content": {
                "sanskrit": "",
                "transliteration": "",
                "translation": trans,
            },
            "metadata": {
                "category": "smriti",
                "tradition": "yoga",
                "themes": ["yoga", "patanjali", "meditation"],
            },
            "commentaries": [],
            "provenance": {
                "download_source": "sacred-texts",
                "original_url": "https://sacred-texts.com/hin/yogasutr.htm",
                "license": "Public Domain",
                "translator": "BonGiovanni",
                "processed_date": datetime.now(timezone.utc).isoformat(),
            },
        })

    return verses
