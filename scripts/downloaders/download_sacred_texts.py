"""Download Hindu scriptures from sacred-texts.com."""

import time
from dataclasses import dataclass
from pathlib import Path

import requests


@dataclass
class SacredText:
    """Sacred Texts resource metadata."""

    path: str
    title: str
    description: str
    format: str  # Usually 'html'


class SacredTextsDownloader:
    """Download and scrape texts from sacred-texts.com."""

    BASE_URL = "https://sacred-texts.com/hin"

    TEXTS = [
        SacredText(
            path="/sbe01/",
            title="Upanishads Part I (SBE)",
            description="Sacred Books of the East Vol 1",
            format="html",
        ),
        SacredText(
            path="/sbe15/",
            title="Upanishads Part II (SBE)",
            description="Sacred Books of the East Vol 15",
            format="html",
        ),
        SacredText(
            path="/tmu/",
            title="Thirty Minor Upanishads",
            description="Complete collection of minor Upanishads",
            format="html",
        ),
        SacredText(
            path="/yogasutr.htm",
            title="Yoga Sutras",
            description="Patanjali's Yoga Sutras with commentary",
            format="html",
        ),
        SacredText(
            path="/vp/", title="Vishnu Purana", description="Complete Vishnu Purana", format="html"
        ),
        SacredText(
            path="/cjw/",
            title="Viveka Chudamani",
            description="Viveka Chudamani (Crest Jewel of Discrimination)",
            format="html",
        ),
    ]

    def __init__(self, base_dir: Path, delay: float = 1.0):
        """
        Initialize with base download directory.

        Args:
            base_dir: Where to save downloaded files
            delay: Seconds to wait between requests (be respectful)
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0 (Hindu Scripture RAG Pipeline)"})

    def download_text(self, text: SacredText) -> tuple[bool, str]:
        """
        Download a sacred text resource.

        Returns:
            (success: bool, message: str)
        """
        url = f"{self.BASE_URL}{text.path}"

        # Create safe filename
        filename = text.title.lower().replace(" ", "_").replace("(", "").replace(")", "")
        filepath = self.base_dir / f"{filename}.html"

        # Skip if already exists
        if filepath.exists():
            return True, f"File already exists: {filepath.name}"

        print(f"\nDownloading: {text.title}")
        print(f"  URL: {url}")
        print(f"  Description: {text.description}")

        try:
            # Respectful delay between requests
            time.sleep(self.delay)

            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            # Save HTML file
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(response.text)

            file_size = len(response.text) / 1024  # KB
            return True, f"Downloaded: {filepath.name} ({file_size:.1f} KB)"

        except requests.RequestException as e:
            return False, f"Download error: {str(e)}"
        except OSError as e:
            return False, f"File write error: {str(e)}"
        except Exception as e:
            return False, f"Unexpected error: {str(e)}"

    def download_all(self) -> dict[str, dict[str, str]]:
        """
        Download all sacred texts.

        Returns:
            Dictionary with download status
        """
        results = {}

        print(f"{'=' * 60}")
        print("SACRED TEXTS DOWNLOADS")
        print(f"{'=' * 60}")
        print(f"Note: Respecting rate limits (1 request/{self.delay}sec)")

        for text in self.TEXTS:
            success, message = self.download_text(text)

            results[text.title] = {
                "success": success,
                "message": message,
                "url": f"{self.BASE_URL}{text.path}",
            }

            if success:
                print(f"  ✓ {message}")
            else:
                print(f"  ❌ {message}")

        return results

    def list_texts(self) -> None:
        """List all available texts."""
        print("\nAvailable sacred texts:")
        for text in self.TEXTS:
            print(f"\n  {text.title}")
            print(f"    Path: {text.path}")
            print(f"    Description: {text.description}")


def main():
    """Main entry point for sacred-texts.com downloads."""
    import argparse

    parser = argparse.ArgumentParser(description="Download Hindu texts from sacred-texts.com")
    parser.add_argument(
        "--base-dir",
        default="~/hindu-scriptures-rag/raw/sacred-texts",
        help="Base directory for downloads",
    )
    parser.add_argument(
        "--delay", type=float, default=1.0, help="Delay between requests in seconds (default: 1.0)"
    )
    parser.add_argument("--list", action="store_true", help="List available texts")

    args = parser.parse_args()
    base_dir = Path(args.base_dir).expanduser()

    downloader = SacredTextsDownloader(base_dir, delay=args.delay)

    if args.list:
        downloader.list_texts()
        return

    # Download all
    results = downloader.download_all()

    print(f"\n\n{'=' * 60}")
    print("DOWNLOAD SUMMARY")
    print(f"{'=' * 60}")

    successful = sum(1 for r in results.values() if r["success"])
    total = len(results)

    print(f"Downloaded: {successful}/{total}")
    print(f"Location: {base_dir}")


if __name__ == "__main__":
    main()
