"""Parsers for English texts (HTML, plain text) into RAG verse schema."""

from .yoga_sutras import parse_yoga_sutras_html
from .gutenberg_gita import parse_arnold_gita
from .gutenberg_mahabharata import parse_mahabharata_ganguli

__all__ = [
    "parse_yoga_sutras_html",
    "parse_arnold_gita",
    "parse_mahabharata_ganguli",
]
