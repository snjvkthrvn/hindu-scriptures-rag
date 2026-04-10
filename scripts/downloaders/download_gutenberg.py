"""Download Hindu scriptures from Project Gutenberg."""

from dataclasses import dataclass
from pathlib import Path

import requests
from tqdm import tqdm


@dataclass
class GutenbergText:
    """Project Gutenberg text metadata."""

    id: int
    title: str
    description: str
    format: str  # 'txt' or 'epub'


class GutenbergDownloader:
    """Download texts from Project Gutenberg."""

    TEXTS = [
        GutenbergText(
            id=2388, title="Bhagavad Gita", description="Edwin Arnold's translation", format="txt"
        ),
        GutenbergText(id=15474, title="Mahabharata", description="Complete epic", format="txt"),
        GutenbergText(
            id=34125, title="Vedanta Sutras", description="With Shankara's commentary", format="txt"
        ),
        GutenbergText(
            id=42541, title="Yoga Sutras", description="Patanjali's Yoga Sutras", format="txt"
        ),
    ]

    BASE_URL = "https://www.gutenberg.org/cache/epub"

    def __init__(self, base_dir: Path):
        """Initialize with base download directory."""
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0 (Hindu Scripture RAG Pipeline)"})

    def build_url(self, text: GutenbergText) -> str:
        """Build download URL for a text."""
        if text.format == "txt":
            return f"{self.BASE_URL}/{text.id}/pg{text.id}.txt"
        elif text.format == "epub":
            return f"{self.BASE_URL}/{text.id}/pg{text.id}.epub"
        else:
            raise ValueError(f"Unknown format: {text.format}")

    def download_text(self, text: GutenbergText) -> tuple[bool, str]:
        """
        Download a single text.

        Returns:
            (success: bool, message: str)
        """
        url = self.build_url(text)
        filename = f"pg{text.id}_{text.title.lower().replace(' ', '_')}.{text.format}"
        filepath = self.base_dir / filename

        # Skip if already exists
        if filepath.exists():
            return True, f"File already exists: {filepath.name}"

        print(f"\nDownloading: {text.title}")
        print(f"  ID: {text.id}")
        print(f"  URL: {url}")

        try:
            response = self.session.get(url, timeout=60, stream=True)
            response.raise_for_status()

            # Get file size
            total_size = int(response.headers.get("content-length", 0))

            # Download with progress bar
            with open(filepath, "wb") as f:
                with tqdm(total=total_size, unit="B", unit_scale=True) as pbar:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            pbar.update(len(chunk))

            return True, f"Downloaded: {filepath.name} ({total_size / 1024 / 1024:.1f} MB)"

        except requests.RequestException as e:
            return False, f"Download error: {str(e)}"
        except OSError as e:
            return False, f"File write error: {str(e)}"
        except Exception as e:
            return False, f"Unexpected error: {str(e)}"

    def download_all(self) -> dict[str, dict[str, str]]:
        """
        Download all Project Gutenberg texts.

        Returns:
            Dictionary with download status
        """
        results = {}

        print(f"{'=' * 60}")
        print("PROJECT GUTENBERG DOWNLOADS")
        print(f"{'=' * 60}")

        for text in self.TEXTS:
            success, message = self.download_text(text)

            results[text.title] = {"success": success, "message": message, "id": str(text.id)}

            if success:
                print(f"  ✓ {message}")
            else:
                print(f"  ❌ {message}")

        return results

    def verify_downloads(self) -> dict[str, bool]:
        """Verify that all expected files were downloaded."""
        verified = {}

        for text in self.TEXTS:
            filename = f"pg{text.id}_*.{text.format}"
            matches = list(self.base_dir.glob(filename))
            verified[text.title] = len(matches) > 0

        return verified


def main():
    """Main entry point for Gutenberg downloads."""
    import argparse

    parser = argparse.ArgumentParser(description="Download Hindu texts from Project Gutenberg")
    parser.add_argument(
        "--base-dir",
        default="~/hindu-scriptures-rag/raw/gutenberg",
        help="Base directory for downloads",
    )
    parser.add_argument("--verify-only", action="store_true", help="Only verify existing downloads")
    parser.add_argument("--list", action="store_true", help="List available texts")

    args = parser.parse_args()
    base_dir = Path(args.base_dir).expanduser()

    if args.list:
        print("\nAvailable texts:")
        for text in GutenbergDownloader.TEXTS:
            print(f"\n  {text.title} (ID: {text.id})")
            print(f"    Description: {text.description}")
            print(f"    Format: {text.format}")
        return

    downloader = GutenbergDownloader(base_dir)

    if args.verify_only:
        verified = downloader.verify_downloads()
        print(f"\n{'=' * 60}")
        print("VERIFICATION RESULTS")
        print(f"{'=' * 60}")
        for title, status in verified.items():
            status_str = "✓ Present" if status else "❌ Missing"
            print(f"{title}: {status_str}")
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
