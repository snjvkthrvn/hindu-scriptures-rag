#!/usr/bin/env python3
"""
Scrape the Rigveda English translation from sacred-texts.com.

Ralph T.H. Griffith translation (1896), 10 books (Mandalas), ~1000+ hymns.
Source: https://sacred-texts.com/hin/rigveda/

Uses Playwright for fetching (bypasses Cloudflare). Falls back to requests if
Playwright unavailable; note that requests may get 403 from sacred-texts.com.
"""

import re
import json
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

from bs4 import BeautifulSoup
from tqdm import tqdm

# Prefer curl_cffi (bypasses Cloudflare); then Playwright; fall back to requests
try:
    from curl_cffi import requests as curl_requests
    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

try:
    import requests
except ImportError:
    requests = None


@dataclass
class HymnRef:
    """Reference to a hymn from a book index."""
    book: int
    hymn_num: int
    title: str
    filename: str


@dataclass 
class Verse:
    """A single verse from the Rigveda."""
    book: int
    hymn: int
    verse_num: int
    hymn_name: str
    text: str


class RigvedaScraper:
    """Scrape Rigveda from sacred-texts.com."""

    BASE_URL = "https://www.sacred-texts.com/hin/rigveda"

    def __init__(self, delay: float = 1.5, use_playwright: bool = True):
        """
        Args:
            delay: Seconds between requests (be respectful to the server)
            use_playwright: Use Playwright if curl_cffi unavailable (bypasses Cloudflare)
        """
        self.delay = delay
        self.use_curl_cffi = HAS_CURL_CFFI
        self.use_playwright = use_playwright and HAS_PLAYWRIGHT and not self.use_curl_cffi
        self._playwright = None
        self._browser = None
        self._context = None
        if self.use_curl_cffi:
            self.session = curl_requests.Session(impersonate="chrome")
        elif not self.use_playwright and requests:
            self.session = requests.Session()
            if hasattr(self, 'session') and self.session:
                self.session.headers.update({
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                })

    def __enter__(self):
        if self.use_playwright and not self.use_curl_cffi:
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"]
            )
            self._context = self._browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            )
            # Warm up: visit main page first to pass Cloudflare
            page = self._context.new_page()
            page.goto("https://www.sacred-texts.com/hin/rigveda/index.htm", wait_until="load", timeout=60000)
            page.wait_for_timeout(2000)
            page.close()
        return self

    def __exit__(self, *args):
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

    def _fetch(self, path: str) -> Optional[str]:
        """Fetch a page from sacred-texts.com."""
        url = f"{self.BASE_URL}/{path}" if not path.startswith("http") else path
        try:
            time.sleep(self.delay)
            if self.use_playwright and self._browser and not self.use_curl_cffi:
                page = self._context.new_page()
                try:
                    resp = page.goto(url, wait_until="load", timeout=60000)
                    if resp and resp.status == 403:
                        # Cloudflare challenge - wait a bit and retry
                        page.wait_for_timeout(3000)
                        resp = page.reload(wait_until="load", timeout=60000)
                    if resp and resp.status == 403:
                        print(f"  Error: 403 Forbidden for {path}")
                        return None
                    if resp and resp.status >= 400:
                        print(f"  Error {resp.status} for {path}")
                        return None
                    page.wait_for_timeout(500)  # Allow any JS to run
                    html = page.content()
                finally:
                    page.close()
                return html
            elif self.session:
                resp = self.session.get(url, timeout=30)
                resp.raise_for_status()
                encoding = getattr(resp, 'encoding', None) or getattr(resp, 'apparent_encoding', None) or 'utf-8'
                if hasattr(resp, 'apparent_encoding') and resp.apparent_encoding:
                    encoding = resp.apparent_encoding
                resp.encoding = encoding
                return resp.text
        except Exception as e:
            print(f"  Error fetching {url}: {e}")
            return None

    def get_book_hymns(self, book: int) -> List[HymnRef]:
        """Parse a book index page to get all hymn references."""
        path = f"rvi{book:02d}.htm"
        html = self._fetch(path)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        hymns = []

        # Find all links to hymn pages: rvXXYYY.htm
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            match = re.match(r"rv(\d{2})(\d{3})\.htm", href)
            if match:
                b, h = int(match.group(1)), int(match.group(2))
                if b == book:
                    title = a.get_text(strip=True)
                    # Clean title: "HYMN I. Agni." -> "Agni"
                    hymns.append(HymnRef(book=b, hymn_num=h, title=title, filename=href))

        return hymns

    def parse_hymn_page(self, html: str, book: int, hymn: int, hymn_name: str) -> List[Verse]:
        """Parse a hymn page to extract verses."""
        soup = BeautifulSoup(html, "html.parser")

        # Get main text - sacred-texts often uses table layout
        # Try to find the content area (skip nav, ads, etc.)
        body = soup.find("body")
        if not body:
            return []

        text = body.get_text(separator="\n", strip=True)
        lines = [l.strip() for l in text.split("\n") if l.strip()]

        verses = []
        current_verse_num = None
        current_lines = []

        for line in lines:
            # Match verse number at start: "1 I Laud...", "2 Worthy..."
            match = re.match(r"^(\d+)\s+(.+)$", line)
            if match:
                # Save previous verse if any
                if current_verse_num is not None and current_lines:
                    verses.append(Verse(
                        book=book,
                        hymn=hymn,
                        verse_num=current_verse_num,
                        hymn_name=hymn_name,
                        text=" ".join(current_lines).strip()
                    ))

                current_verse_num = int(match.group(1))
                current_lines = [match.group(2)]
            elif current_verse_num is not None:
                # Continuation of current verse (multi-line)
                current_lines.append(line)

        if current_verse_num is not None and current_lines:
            verses.append(Verse(
                book=book,
                hymn=hymn,
                verse_num=current_verse_num,
                hymn_name=hymn_name,
                text=" ".join(current_lines).strip()
            ))

        return verses

    def extract_hymn_name(self, title: str) -> str:
        """Extract deity/subject from hymn title. E.g. 'HYMN I. Agni.' -> 'Agni'"""
        # Format: "HYMN I. Agni." or "HYMN CXXV. Svanaya."
        match = re.search(r"HYMN\s+[IVXLCDM]+\s*\.?\s*(.+?)(?:\.|$)", title, re.I)
        if match:
            return match.group(1).strip()
        return title

    def scrape_all(self, books: Optional[List[int]] = None, save_html_dir: Optional[Path] = None) -> List[Dict]:
        """Scrape the complete Rigveda and return verses as JSON-serializable dicts."""
        all_verses = []
        books = books or list(range(1, 11))
        self._save_html_dir = Path(save_html_dir) if save_html_dir else None

        for book in books:
            print(f"\n=== Book {book} ===")
            hymns = self.get_book_hymns(book)
            print(f"  Found {len(hymns)} hymns")

            for ref in tqdm(hymns, desc=f"  Book {book}", leave=False):
                html = self._fetch(ref.filename)
                if not html:
                    continue

                if getattr(self, "_save_html_dir", None):
                    save_path = self._save_html_dir / ref.filename
                    save_path.parent.mkdir(parents=True, exist_ok=True)
                    save_path.write_text(html, encoding="utf-8")

                hymn_name = self.extract_hymn_name(ref.title)
                verses = self.parse_hymn_page(html, book, ref.hymn_num, hymn_name)

                for v in verses:
                    verse_id = f"rv_{v.book}_{v.hymn}_{v.verse_num}"
                    all_verses.append({
                        "id": verse_id,
                        "source": {
                            "text": "Rig Veda",
                            "book": v.book,
                            "book_name": f"Mandala {v.book}",
                            "hymn": v.hymn,
                            "hymn_name": v.hymn_name,
                            "verse": v.verse_num,
                        },
                        "content": {
                            "sanskrit": "",
                            "transliteration": "",
                            "translation": v.text,
                            "word_by_word": {}
                        },
                        "metadata": {
                            "category": "shruti",
                            "tradition": "vedic",
                            "themes": ["rigveda"],
                            "philosophical_schools": []
                        },
                        "commentaries": [],
                        "provenance": {
                            "download_source": "sacred-texts",
                            "original_url": f"{self.BASE_URL}/{ref.filename}",
                            "translator": "Ralph T.H. Griffith",
                            "translation_year": 1896,
                            "license": "Public Domain",
                            "processed_date": datetime.now(timezone.utc).isoformat()
                        }
                    })

        return all_verses


def _extract_hymn_name(title: str) -> str:
    """Extract deity/subject from hymn title."""
    match = re.search(r"HYMN\s+[IVXLCDM]+\s*\.?\s*(.+?)(?:\.|$)", title, re.I)
    return match.group(1).strip() if match else title


def scrape_from_html_dir(html_dir: Path, books: List[int]) -> List[Dict]:
    """Load and parse Rigveda from pre-downloaded HTML files.
    
    Expected structure: html_dir/rv01001.htm, rv01002.htm, etc.
    """
    html_dir = Path(html_dir)
    all_verses = []
    scraper = RigvedaScraper(delay=0)  # Dummy for parsing only

    for book in books:
        # Find all hymn files for this book
        pattern = f"rv{book:02d}*.htm"
        for filepath in sorted(html_dir.glob(pattern)):
            match = re.match(r"rv(\d{2})(\d{3})\.htm", filepath.name)
            if not match:
                continue
            b, h = int(match.group(1)), int(match.group(2))
            if b != book:
                continue

            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                html = f.read()

            soup = BeautifulSoup(html, "html.parser")
            title_el = soup.find("h3") or soup.find("h2")
            hymn_name = title_el.get_text(strip=True) if title_el else ""
            hymn_name = _extract_hymn_name(hymn_name)

            verses = scraper.parse_hymn_page(html, book, h, hymn_name)
            
            for v in verses:
                verse_id = f"rv_{v.book}_{v.hymn}_{v.verse_num}"
                all_verses.append({
                    "id": verse_id,
                    "source": {
                        "text": "Rig Veda",
                        "book": v.book,
                        "book_name": f"Mandala {v.book}",
                        "hymn": v.hymn,
                        "hymn_name": v.hymn_name,
                        "verse": v.verse_num,
                    },
                    "content": {
                        "sanskrit": "",
                        "transliteration": "",
                        "translation": v.text,
                        "word_by_word": {}
                    },
                    "metadata": {
                        "category": "shruti",
                        "tradition": "vedic",
                        "themes": ["rigveda"],
                        "philosophical_schools": []
                    },
                    "commentaries": [],
                    "provenance": {
                        "download_source": "sacred-texts",
                        "original_url": f"{RigvedaScraper.BASE_URL}/{filepath.name}",
                        "translator": "Ralph T.H. Griffith",
                        "translation_year": 1896,
                        "license": "Public Domain",
                        "processed_date": datetime.now(timezone.utc).isoformat()
                    }
                })

    return all_verses


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Scrape Rigveda from sacred-texts.com")
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output JSON file path (default: raw/sacred-texts/rigveda.json)"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.5,
        help="Delay between requests in seconds (default: 1.5)"
    )
    parser.add_argument(
        "--books",
        type=str,
        default="1-10",
        help="Book range to scrape, e.g. '1-3' or '1' (default: 1-10)"
    )
    parser.add_argument(
        "--from-html-dir",
        type=str,
        default=None,
        help="Load from pre-downloaded HTML files instead of fetching (for when Cloudflare blocks requests)"
    )
    parser.add_argument(
        "--save-html",
        type=str,
        default=None,
        metavar="DIR",
        help="Save fetched HTML to directory (enables Option B: HTML first, then parse)"
    )

    args = parser.parse_args()

    # Parse book range
    if "-" in args.books:
        start, end = map(int, args.books.split("-"))
        books_to_scrape = range(start, end + 1)
    else:
        books_to_scrape = [int(args.books)]

    # Resolve output path
    if args.output:
        out_path = Path(args.output)
    else:
        out_path = Path(__file__).resolve().parents[2] / "raw" / "sacred-texts" / "rigveda.json"

    out_path.parent.mkdir(parents=True, exist_ok=True)

    print("Rigveda Scraper - sacred-texts.com")
    print("=" * 50)
    print(f"Output: {out_path}")

    if args.from_html_dir:
        html_dir = Path(args.from_html_dir)
        print(f"Loading from: {html_dir}")
        verses = scrape_from_html_dir(html_dir, books=list(books_to_scrape))
    else:
        print(f"Delay: {args.delay}s between requests")
        print(f"Using: {'curl_cffi (Chrome)' if HAS_CURL_CFFI else 'Playwright (browser)' if HAS_PLAYWRIGHT else 'requests (may get 403)'}")
        print("Note: sacred-texts.com uses Cloudflare; requests from data centers may get 403.")
        print("      Try --from-html-dir with manually saved HTML if blocked.")
        print("Please be respectful - this will make 1000+ requests.")
        print()

        save_html = Path(args.save_html) if args.save_html else None
        with RigvedaScraper(delay=args.delay) as scraper:
            verses = scraper.scrape_all(books=list(books_to_scrape), save_html_dir=save_html)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(verses, f, indent=2, ensure_ascii=False)

    print(f"\nDone! Saved {len(verses)} verses to {out_path}")


if __name__ == "__main__":
    main()
