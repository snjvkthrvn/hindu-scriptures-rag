"""Parse Mahabharata from Gutenberg plain text (Kisari Mohan Ganguli translation)."""

import re
from datetime import datetime, timezone
from pathlib import Path

# Roman numerals for SECTION headers
_ROMAN_LIST = (
    "I II III IV V VI VII VIII IX X XI XII XIII XIV XV XVI XVII XVIII XIX XX "
    "XXI XXII XXIII XXIV XXV XXVI XXVII XXVIII XXIX XXX XXXI XXXII XXXIII XXXIV XXXV "
    "XXXVI XXXVII XXXVIII XXXIX XL XLI XLII XLIII XLIV XLV XLVI XLVII XLVIII XLIX L "
    "LI LII LIII LIV LV LVI LVII LVIII LIX LX LXI LXII LXIII LXIV LXV LXVI LXVII LXVIII LXIX LXX"
).split()
ROMAN_MAP = {r: i + 1 for i, r in enumerate(_ROMAN_LIST)}


def _section_num(s: str) -> int:
    s = s.upper().strip()
    if s.isdigit():
        return int(s)
    return ROMAN_MAP.get(s, 0)


def _prescan_parvas(text: str) -> list[tuple[int, str]]:
    """Pre-scan text for all BOOK/PARVA headers with their character positions.

    Returns sorted list of (position, parva_name) tuples.
    """
    parvas = []
    for m in re.finditer(r"BOOK\s+\d+\s*\n\s*([^\n]+)", text, re.IGNORECASE):
        parva_name = m.group(1).strip()
        # Skip lines that are clearly not parva names
        if parva_name and not re.match(r"^SECTION\s", parva_name, re.IGNORECASE):
            parvas.append((m.start(), parva_name))
    return sorted(parvas, key=lambda x: x[0])


def _lookup_parva(position: int, parvas: list[tuple[int, str]], default: str) -> str:
    """Find the parva name active at a given character position."""
    result = default
    for pos, name in parvas:
        if pos <= position:
            result = name
        else:
            break
    return result


def parse_mahabharata_ganguli(txt_path: Path) -> list[dict]:
    """Extract sections from Ganguli's Mahabharata prose translation.

    Structure: BOOK N, PARVA NAME, SECTION N, then prose paragraphs.
    Chunks by SECTION; each paragraph becomes a verse-like unit.
    Short paragraphs (<20 chars) are merged with the next paragraph.
    """
    text = txt_path.read_text(encoding="utf-8", errors="replace")

    # Skip Gutenberg header
    start_marker = "*** START OF THE PROJECT GUTENBERG"
    if start_marker in text:
        text = text.split(start_marker, 1)[1]

    # Find THE MAHABHARATA + first section
    m = re.search(
        r"THE MAHABHARATA\s*\n\s*([^\n]+)\s*\n\s*SECTION\s+([IVXLCDM]+|\d+)\s*\n",
        text,
        re.IGNORECASE,
    )
    if m:
        default_parva = m.group(1).strip()
        text = text[m.start() :]
    else:
        default_parva = "Adi Parva"
        sec1 = re.search(r"SECTION\s+([IVXLCDM]+|\d+)\s*\n", text, re.IGNORECASE)
        if sec1:
            text = text[sec1.start() :]

    # Pre-scan all BOOK/PARVA headers with positions
    parvas = _prescan_parvas(text)

    verses = []
    section_pat = re.compile(r"\n\s*SECTION\s+([IVXLCDM]+|\d+)\s*\n", re.IGNORECASE)
    for match in section_pat.finditer(text):
        section_num = _section_num(match.group(1))
        start = match.end()
        next_m = section_pat.search(text, start)
        chunk = text[start : next_m.start()] if next_m else text[start:]

        # Look up parva name from pre-scanned positions
        current_parva = _lookup_parva(match.start(), parvas, default_parva)

        raw_paras = re.split(r"\n\s{3,}|\n\n+", chunk)

        # Clean and merge short paragraphs
        cleaned = []
        pending = ""
        for para in raw_paras:
            para = re.sub(r"\s+", " ", para).strip()
            if not para:
                continue
            combined = (pending + " " + para).strip() if pending else para
            if len(combined) < 20:
                pending = combined
            else:
                cleaned.append(combined)
                pending = ""
        if pending and cleaned:
            cleaned[-1] = cleaned[-1] + " " + pending
        elif pending:
            cleaned.append(pending)

        for pi, para in enumerate(cleaned):
            if len(para) < 20:
                continue
            verses.append(
                {
                    "id": f"mbh_s{section_num}_v{pi + 1}",
                    "source": {
                        "text": "Mahabharata",
                        "chapter": section_num,
                        "chapter_name": current_parva,
                        "verse": pi + 1,
                    },
                    "content": {
                        "sanskrit": "",
                        "transliteration": "",
                        "translation": para,
                    },
                    "metadata": {
                        "category": "smriti",
                        "tradition": "itihasa",
                        "themes": ["mahabharata", "epic"],
                    },
                    "commentaries": [],
                    "provenance": {
                        "download_source": "gutenberg",
                        "original_url": "https://www.gutenberg.org/ebooks/15474",
                        "license": "Public Domain",
                        "translator": "Kisari Mohan Ganguli",
                        "processed_date": datetime.now(timezone.utc).isoformat(),
                    },
                }
            )

    return verses
