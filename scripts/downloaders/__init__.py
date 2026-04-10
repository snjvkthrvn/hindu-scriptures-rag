"""Downloader modules for fetching Hindu scripture sources."""

from .download_github import GitHubDownloader
from .download_gutenberg import GutenbergDownloader
from .download_sacred_texts import SacredTextsDownloader

__all__ = ["GitHubDownloader", "GutenbergDownloader", "SacredTextsDownloader"]
