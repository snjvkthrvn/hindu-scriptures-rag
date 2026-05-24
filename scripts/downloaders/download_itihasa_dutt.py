#!/usr/bin/env python3
"""Ingest the rahular/itihasa parallel Sanskrit-English corpus as supplementary
sources alongside the main Critical Edition.

Source: github.com/rahular/itihasa — ~93,000 line-paired Sanskrit-English
shlokas extracted from M.N. Dutt's late-19th-century translations of:
  - The Rāmāyaṇa (Valmiki, Calcutta vulgate recension)
  - The Mahābhārata (Calcutta vulgate, not the Pune Critical Edition)

Why supplementary (not merged):
  Earlier merge attempt against main-corpus Sanskrit hit 0.64% / 0.00%
  match rates because the recensions differ — Dutt's verses are not
  literally identical to the Critical Edition verses our DharmicData
  pipeline produced. Rather than discard the 93k high-quality English
  translations, we add them as separate sources so users can still find
  Dutt's English when searching for MBH/Ramayana topics; the Critical
  Edition Sanskrit remains intact for scholars who need it.

Classification:
  Itihasa files don't carry per-line source labels, so we heuristically
  classify each line as Ramayana or Mahabharata based on which set of
  characteristic Devanagari keywords appears in the Sanskrit. Mis-
  classification rate should be low because Ramayana and Mahabharata
  share few distinctive nouns even when content overlaps thematically.

Output:
  raw/wikisource/itihasa_dutt.json — line-level records keyed by source
  + sequence number. Each carries the full line's Sanskrit and English
  (some lines may contain 2-3 joined shlokas, which we keep together to
  preserve the alignment).

Usage:
    PYTHONUTF8=1 python scripts/downloaders/download_itihasa_dutt.py
"""

from __future__ import annotations

import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_FILE = PROJECT_ROOT / "raw" / "wikisource" / "itihasa_dutt.json"
CACHE_DIR = PROJECT_ROOT / "raw" / "wikisource" / "_itihasa_cache"

BASE_URL = "https://raw.githubusercontent.com/rahular/itihasa/main/data"
SPLITS = ["train", "dev", "test"]  # downloads <split>.sn and <split>.en

USER_AGENT = "hindu-scriptures-rag/0.1 (research, contact: sanjeevkathiravanpro@gmail.com)"

# Characteristic Devanagari keywords. Words shared by both epics (kṛṣṇa,
# dharma, deva) are excluded; only signature names are kept.
RAMAYANA_KEYWORDS_SN = {
    "राम", "सीता", "लक्ष्मण", "हनुमान्", "हनुमान", "रावण", "अयोध्या",
    "वाल्मीकि", "विभीषण", "सुग्रीव", "जटायु", "दशरथ", "कैकेयी",
    "विश्वामित्र", "जनक", "लङ्का", "इक्ष्वाकु", "रघु", "भरत",
}
MBH_KEYWORDS_SN = {
    "युधिष्ठिर", "अर्जुन", "भीष्म", "द्रोण", "कर्ण", "द्रौपदी",
    "दुर्योधन", "धृतराष्ट्र", "विदुर", "कौरव", "पाण्डव", "पाण्डु",
    "कुन्ती", "गान्धारी", "अश्वत्थामन्", "अश्वत्थामा", "जयद्रथ",
    "कुरुक्षेत्र", "हस्तिनापुर", "व्यास", "धर्मराज", "वैशम्पायन",
    "जनमेजय", "भीम", "नकुल", "सहदेव", "शकुनि", "द्रुपद",
}
# English keyword fallback — Dutt's English uses these names verbatim
RAMAYANA_KEYWORDS_EN = {
    "Rama", "Sita", "Lakshmana", "Hanuman", "Ravana", "Ayodhya", "Valmiki",
    "Vibhishana", "Sugriva", "Jatayu", "Dasaratha", "Dasharatha", "Kaikeyi",
    "Vishvamitra", "Vis'wamitra", "Vishwamitra", "Janaka", "Lanka", "Ikshvaku",
    "Raghu", "Bharata",
}
MBH_KEYWORDS_EN = {
    "Yudhishthira", "Yudhisthira", "Arjuna", "Bhishma", "Drona", "Karna",
    "Draupadi", "Duryodhana", "Dhritarashtra", "Vidura", "Kaurava", "Pandava",
    "Kunti", "Gandhari", "Aswatthama", "Ashvatthama", "Jayadratha",
    "Kurukshetra", "Hastinapura", "Vyasa", "Vaishampayana", "Vaisampayana",
    "Janamejaya", "Bhima", "Nakula", "Sahadeva", "Sakuni", "Drupada",
    "Pandavas", "Kauravas",
}


def fetch_to_cache(name: str) -> str:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_DIR / name
    if cache_path.exists():
        return cache_path.read_text(encoding="utf-8", errors="replace")
    url = f"{BASE_URL}/{name}"
    print(f"  Fetching {name} from {url} ...")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    text = data.decode("utf-8", errors="replace")
    cache_path.write_text(text, encoding="utf-8")
    print(f"  Cached → {cache_path.relative_to(PROJECT_ROOT)} ({len(data):,} bytes)")
    return text


def classify(sanskrit: str, english: str = "") -> str:
    """Return 'ramayana', 'mahabharata', or 'unknown' based on keywords in
    either Sanskrit or English. English fallback catches lines where the
    Sanskrit doesn't mention a proper noun but the translator named a person
    or place explicitly (the common case).
    """
    has_ram = (
        any(k in sanskrit for k in RAMAYANA_KEYWORDS_SN)
        or any(k in english for k in RAMAYANA_KEYWORDS_EN)
    )
    has_mbh = (
        any(k in sanskrit for k in MBH_KEYWORDS_SN)
        or any(k in english for k in MBH_KEYWORDS_EN)
    )
    if has_ram and not has_mbh:
        return "ramayana"
    if has_mbh and not has_ram:
        return "mahabharata"
    return "unknown"


# Provenance
PROV = {
    "download_source": "github.com/rahular/itihasa",
    "translator": "Manmatha Nath Dutt",
    "translation_year": 1891,
    "license": "Public Domain",
    "note": (
        "Dutt's recension differs from the Pune Critical Edition (Mahabharata) "
        "and Baroda Critical Edition (Valmiki Ramayana); use for textual content, "
        "not as a verse-aligned commentary on the Critical Editions."
    ),
}

SOURCE_LABELS = {
    "ramayana": ("Ramayana (Dutt)", "ram_dutt"),
    "mahabharata": ("Mahabharata (Dutt)", "mbh_dutt"),
    "unknown": ("Itihasa (Dutt, unclassified)", "itihasa_dutt"),
}


def build_record(source_label: str, id_prefix: str, sequence: int,
                 sanskrit: str, english: str) -> dict:
    return {
        "id": f"{id_prefix}_{sequence}",
        "source": {
            "text": source_label,
            "chapter": None,
            "chapter_name": source_label,
            "verse": sequence,
            "section": None,
        },
        "content": {
            "sanskrit": sanskrit,
            "transliteration": "",
            "translation": english,
        },
        "metadata": {
            "category": "itihasa",
            "tradition": "common",
        },
        "provenance": {
            **PROV,
            "processed_date": datetime.now(timezone.utc).isoformat(),
        },
    }


def main() -> int:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    print(f"Output → {OUTPUT_FILE.relative_to(PROJECT_ROOT)}")

    # Fetch & combine all splits
    all_sn: list[str] = []
    all_en: list[str] = []
    for split in SPLITS:
        try:
            sn = fetch_to_cache(f"{split}.sn")
            en = fetch_to_cache(f"{split}.en")
        except (HTTPError, URLError) as e:
            print(f"  ! {split} fetch failed: {e}")
            continue
        sn_lines = sn.split("\n")
        en_lines = en.split("\n")
        if len(sn_lines) != len(en_lines):
            print(f"  ! {split}: line count mismatch ({len(sn_lines)} sn vs {len(en_lines)} en) — truncating to min")
        n = min(len(sn_lines), len(en_lines))
        for i in range(n):
            s = sn_lines[i].strip()
            e = en_lines[i].strip()
            if not s or not e:
                continue
            all_sn.append(s)
            all_en.append(e)
        print(f"  {split}: {n:,} line pairs loaded")

    print(f"Total: {len(all_sn):,} line-paired Sanskrit-English shlokas")

    # Classify & build records with per-source sequential ids
    per_source_seq: dict[str, int] = {"ramayana": 0, "mahabharata": 0, "unknown": 0}
    counts: dict[str, int] = {"ramayana": 0, "mahabharata": 0, "unknown": 0}
    records: list[dict] = []
    for sn, en in zip(all_sn, all_en):
        cls = classify(sn, en)
        per_source_seq[cls] += 1
        counts[cls] += 1
        label, prefix = SOURCE_LABELS[cls]
        records.append(build_record(label, prefix, per_source_seq[cls], sn, en))

    # Write
    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    print()
    print("=" * 60)
    print(f"  Total records: {len(records):,}")
    print("=" * 60)
    for cls in ("ramayana", "mahabharata", "unknown"):
        label, _ = SOURCE_LABELS[cls]
        print(f"  {label:<40} {counts[cls]:>7,}")
    print(f"\nSaved → {OUTPUT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
