"""Download Hindu scriptures from GitHub repositories."""

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class GitHubRepo:
    """GitHub repository metadata."""

    name: str
    url: str
    description: str
    expected_files: list[str]


class GitHubDownloader:
    """Download and verify GitHub repositories."""

    REPOS = [
        GitHubRepo(
            name="DharmicData",
            url="https://github.com/bhavykhatri/DharmicData.git",
            description="Structured Hindu scripture data (JSON)",
            expected_files=["gita.json", "mahabharata.json", "ramayana.json"],
        ),
        GitHubRepo(
            name="indian-scriptures",
            url="https://github.com/hrgupta/indian-scriptures.git",
            description="11 Principal Upanishads in CSV format",
            expected_files=["upanishads.csv", "isha_upanishad.csv"],
        ),
    ]

    def __init__(self, base_dir: Path):
        """Initialize with base download directory."""
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def clone_repo(self, repo: GitHubRepo) -> tuple[bool, str]:
        """
        Clone a GitHub repository.

        Returns:
            (success: bool, message: str)
        """
        target_dir = self.base_dir / repo.name.lower()

        # Skip if already exists
        if target_dir.exists():
            return True, f"Repository already exists at {target_dir}"

        print(f"\nCloning {repo.name}...")
        print(f"  URL: {repo.url}")
        print(f"  Target: {target_dir}")

        try:
            result = subprocess.run(
                ["git", "clone", "--depth", "1", repo.url, str(target_dir)],
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode == 0:
                return True, f"Successfully cloned {repo.name}"
            else:
                return False, f"Git error: {result.stderr}"

        except subprocess.TimeoutExpired:
            return False, "Clone operation timed out"
        except FileNotFoundError:
            return False, "Git not installed or not in PATH"
        except Exception as e:
            return False, f"Unexpected error: {str(e)}"

    def verify_repo(self, repo: GitHubRepo) -> tuple[bool, list[str]]:
        """
        Verify that expected files exist in cloned repository.

        Returns:
            (all_found: bool, found_files: List[str])
        """
        target_dir = self.base_dir / repo.name.lower()

        if not target_dir.exists():
            return False, []

        found_files = []
        for expected_file in repo.expected_files:
            # Search recursively for the file
            matches = list(target_dir.rglob(expected_file))
            if matches:
                found_files.append(str(matches[0]))

        return len(found_files) > 0, found_files

    def download_all(self) -> dict[str, dict[str, str]]:
        """
        Download and verify all repositories.

        Returns:
            Dictionary with repo status and file locations
        """
        results = {}

        for repo in self.REPOS:
            print(f"\n{'=' * 60}")
            print(f"Processing: {repo.name}")
            print(f"Description: {repo.description}")
            print(f"{'=' * 60}")

            # Clone
            success, message = self.clone_repo(repo)
            results[repo.name] = {
                "cloned": success,
                "clone_message": message,
                "files_found": [],
                "verified": False,
            }

            if not success:
                print(f"  ❌ Clone failed: {message}")
                continue

            print(f"  ✓ {message}")

            # Verify
            verified, files = self.verify_repo(repo)
            results[repo.name]["verified"] = verified
            results[repo.name]["files_found"] = files

            if verified:
                print(f"  ✓ Verification passed - {len(files)} expected file(s) found")
                for file in files:
                    print(f"    - {file}")
            else:
                print("  ⚠ Could not verify all expected files")

        return results

    def list_contents(self, repo_name: str) -> list[str]:
        """List all files in a cloned repository."""
        target_dir = self.base_dir / repo_name.lower()

        if not target_dir.exists():
            return []

        files = []
        for file in target_dir.rglob("*"):
            if file.is_file():
                files.append(str(file.relative_to(target_dir)))

        return sorted(files)


def main():
    """Main entry point for GitHub downloads."""
    import argparse

    parser = argparse.ArgumentParser(description="Download Hindu scripture GitHub repos")
    parser.add_argument(
        "--base-dir", default="~/hindu-scriptures-rag/raw", help="Base directory for downloads"
    )
    parser.add_argument("--list", action="store_true", help="List available repositories")

    args = parser.parse_args()
    base_dir = Path(args.base_dir).expanduser()

    if args.list:
        print("\nAvailable repositories:")
        for repo in GitHubDownloader.REPOS:
            print(f"\n  {repo.name}")
            print(f"    URL: {repo.url}")
            print(f"    Description: {repo.description}")
        return

    # Download all
    downloader = GitHubDownloader(base_dir)
    results = downloader.download_all()

    print(f"\n\n{'=' * 60}")
    print("DOWNLOAD SUMMARY")
    print(f"{'=' * 60}")

    for repo_name, result in results.items():
        status = "✓ Complete" if result["verified"] else "⚠ Incomplete"
        print(f"{repo_name}: {status}")

    print(f"\nDownloads saved to: {base_dir}")


if __name__ == "__main__":
    main()
