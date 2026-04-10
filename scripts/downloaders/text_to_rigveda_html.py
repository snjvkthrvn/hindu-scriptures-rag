#!/usr/bin/env python3
"""Convert Rigveda text (from MCP/web fetch) to HTML for the parser."""

import re
import sys


def text_to_html(text: str) -> str:
    """Convert fetched Rigveda text to HTML our parser expects."""
    # Find hymn title (### HYMN I. Agni. or HYMN II. Vāyu.)
    title_match = re.search(r"#+\s*(HYMN\s+[IVXLCDM]+\.\s*[^.]+\.?)", text, re.I)
    title = title_match.group(1).strip() if title_match else ""

    # Collect all verse text - handle both line-by-line and concatenated formats
    raw = re.sub(r"\[.*?\]\(.*?\)", "", text)  # Remove markdown links
    raw = re.sub(r"\*+\s*", "", raw)  # Remove asterisks
    raw = re.sub(r"---+", "\n", raw)  # Treat --- as separator

    verses = []
    # Split by verse number pattern: "1 " or " 2 " or "\n1 " etc.
    chunks = re.split(r"(?:\n|^)\s*(\d+)\s+", raw)
    for i in range(1, len(chunks), 2):
        if i + 1 < len(chunks):
            num, content = int(chunks[i]), chunks[i + 1]
            # Clean: remove nav, next links, extra whitespace
            content = re.sub(r"\s*Next:.*$", "", content, flags=re.DOTALL)
            content = re.sub(r"\s+", " ", content).strip()
            if content and not content.startswith("http"):
                verses.append((num, content))

    if not verses and "HYMN" in text:
        # Fallback: line-by-line parse
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        for line in lines:
            if re.match(r"^(\d+)\s+", line) and not line.startswith("["):
                m = re.match(r"^(\d+)\s+(.+)$", line)
                if m:
                    verses.append((int(m.group(1)), m.group(2).strip()))

    html_parts = ["<!DOCTYPE html><html><body>"]
    if title:
        html_parts.append(f"<h3>{title}</h3>")
    for num, text in verses:
        html_parts.append(f"<p>{num} {text}</p>")
    html_parts.append("</body></html>")
    return "\n".join(html_parts)


if __name__ == "__main__":
    content = sys.stdin.read()
    print(text_to_html(content))
