"""Extract English translations for target Upanishads.

This script downloads and parses English translations for:
- Isha Upanishad (Max Muller, sacred-texts SBE01)
- Mundaka Upanishad (Max Muller, sacred-texts SBE15)
- Taittiriya Upanishad (Max Muller, sacred-texts SBE15)
- Mandukya Upanishad (Sri Aurobindo, ancienttexts.org)
"""

from __future__ import annotations

import argparse
import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import cloudscraper
from bs4 import BeautifulSoup


@dataclass(frozen=True)
class UpanishadSource:
    name: str
    translator: str
    source_label: str
    urls: list[str]
    output_stem: str


SOURCES: list[UpanishadSource] = [
    UpanishadSource(
        name="Isha Upanishad",
        translator="Max Muller",
        source_label="Sacred Books of the East (SBE01)",
        urls=["https://sacred-texts.com/hin/sbe01/sbe01243.htm"],
        output_stem="isha_upanishad_mueller",
    ),
    UpanishadSource(
        name="Mundaka Upanishad",
        translator="Max Muller",
        source_label="Sacred Books of the East (SBE15)",
        urls=[f"https://sacred-texts.com/hin/sbe15/sbe150{i}.htm" for i in range(16, 22)],
        output_stem="mundaka_upanishad_mueller",
    ),
    UpanishadSource(
        name="Taittiriya Upanishad",
        translator="Max Muller",
        source_label="Sacred Books of the East (SBE15)",
        urls=[f"https://sacred-texts.com/hin/sbe15/sbe150{i}.htm" for i in range(22, 53)],
        output_stem="taittiriya_upanishad_mueller",
    ),
    UpanishadSource(
        name="Mandukya Upanishad",
        translator="Sri Aurobindo",
        source_label="Ancient Texts Archive",
        urls=["https://www.ancienttexts.org/library/indian/upanishads/mandu.html"],
        output_stem="mandukya_upanishad_aurobindo",
    ),
]


def normalize_text(value: str) -> str:
    value = value.replace("\xa0", " ")
    value = re.sub(r"\s+", " ", value).strip()
    return value


def extract_numbered_lines_sacred_texts(html: str) -> list[tuple[int, str]]:
    """Extract numbered verse-like lines from sacred-texts pages."""
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n")
    lines = [normalize_text(line) for line in text.splitlines()]
    lines = [line for line in lines if line]

    verses: list[tuple[int, str]] = []
    current_num: int | None = None
    current_parts: list[str] = []
    in_footnotes = False

    verse_start = re.compile(r"^(\d+)\.\s*(.*)")
    drop_prefix = (
        "p. ",
        "The Upanishads",
        "Sacred Texts",
        "Hinduism",
        "Buy this Book",
        "Footnotes",
        "Next:",
        "Previous:",
        "Index",
    )

    def flush() -> None:
        nonlocal current_num, current_parts
        if current_num is None:
            return
        joined = normalize_text(" ".join(current_parts))
        if joined:
            verses.append((current_num, joined))
        current_num = None
        current_parts = []

    for raw in lines:
        line = raw
        if line == "Footnotes":
            in_footnotes = True
        if in_footnotes:
            continue
        if any(line.startswith(prefix) for prefix in drop_prefix):
            continue
        if line.startswith("[") and "fn_" in line:
            continue
        if line.startswith("###"):
            continue

        match = verse_start.match(line)
        if match:
            flush()
            current_num = int(match.group(1))
            current_parts = [match.group(2)] if match.group(2) else []
            continue

        # Continuation lines for current numbered verse.
        if current_num is not None:
            if line.startswith("[") and "paragraph continues" in line:
                continue
            current_parts.append(line)

    flush()
    return verses


def extract_numbered_lines_mandukya_aurobindo(html: str) -> list[tuple[int, str]]:
    """Extract 12 numbered mantras from the Aurobindo Mandukya page."""
    soup = BeautifulSoup(html, "html.parser")
    text = normalize_text(soup.get_text(" "))
    # Strip title/translator labels if present.
    text = re.sub(r"^Mandukya Upanishad translated by Sri Aurobindo\s*", "", text)
    # Keep content before navigation links.
    text = text.split("Aitar Upanishad")[0]
    pairs = re.findall(r"(\d+)\.\s*(.*?)(?=(?:\s+\d+\.\s)|$)", text)
    result: list[tuple[int, str]] = []
    for num_str, verse_text in pairs:
        verse = normalize_text(verse_text)
        if verse:
            result.append((int(num_str), verse))
    return result


def unique_by_number(items: Iterable[tuple[int, str]]) -> list[tuple[int, str]]:
    seen: set[int] = set()
    out: list[tuple[int, str]] = []
    for num, verse in items:
        if num in seen:
            continue
        seen.add(num)
        out.append((num, verse))
    return out


def write_outputs(
    output_dir: Path,
    source: UpanishadSource,
    verses: list[tuple[int, str]],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    txt_path = output_dir / f"{source.output_stem}.txt"
    csv_path = output_dir / f"{source.output_stem}.csv"

    with txt_path.open("w", encoding="utf-8") as f:
        f.write(f"{source.name}\n")
        f.write(f"Translator: {source.translator}\n")
        f.write(f"Source: {source.source_label}\n\n")
        for num, text in verses:
            f.write(f"{num}. {text}\n")

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["upanishad", "verse_number", "translation"])
        writer.writeheader()
        for num, text in verses:
            writer.writerow(
                {
                    "upanishad": source.name,
                    "verse_number": num,
                    "translation": text,
                }
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract English Upanishad translations")
    parser.add_argument(
        "--output-dir",
        default="translations",
        help="Directory to write output text/csv files",
    )
    args = parser.parse_args()
    output_dir = Path(args.output_dir).expanduser()

    scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "darwin", "mobile": False}
    )

    for source in SOURCES:
        all_verses: list[tuple[int, str]] = []
        for url in source.urls:
            response = scraper.get(url, timeout=45)
            response.raise_for_status()
            if "ancienttexts.org" in url:
                page_verses = extract_numbered_lines_mandukya_aurobindo(response.text)
            else:
                page_verses = extract_numbered_lines_sacred_texts(response.text)
            all_verses.extend(page_verses)

        deduped = unique_by_number(all_verses)
        write_outputs(output_dir, source, deduped)
        print(f"{source.name}: wrote {len(deduped)} verses")


if __name__ == "__main__":
    main()
