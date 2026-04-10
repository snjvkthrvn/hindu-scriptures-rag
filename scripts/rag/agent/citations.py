"""Extract scripture references from answer text.

Recognises references like:
  BG 2.47, RV 10.129.1, Katha Up 1.2.20, MBh 12.259.5
Returns a deduplicated list preserving order of first appearance.
"""

from __future__ import annotations

import re

_UPANISHAD_NAMES = (
    r"Isha|Kena|Katha|Prashna|Mundaka|Mandukya|Taittiriya|Aitareya"
    r"|Brihadaranyaka|Svetasvatara|Chandogya"
)

_PATTERNS: list[tuple[re.Pattern, bool]] = [
    (re.compile(r"\b(BG)\s+(\d+\.\d+)\b"), False),
    (re.compile(r"\b(RV|AV|YV|SV)\s+(\d+\.\d+(?:\.\d+)?)\b"), False),
    (re.compile(r"\b(MBh|Ram)\s+(\d+\.\d+(?:\.\d+)?)\b"), False),
    (re.compile(
        rf"\b({_UPANISHAD_NAMES})\s+Up\.?\s+(\d+(?:\.\d+){{0,2}})\b"
    ), True),
]


def extract_refs(text: str) -> list[str]:
    """Extract unique scripture references from text, preserving first-appearance order."""
    seen: list[str] = []
    for pattern, is_upanishad in _PATTERNS:
        for match in pattern.finditer(text):
            abbrev = match.group(1)
            num = match.group(2)
            ref = f"{abbrev} Up {num}" if is_upanishad else f"{abbrev} {num}"
            if ref not in seen:
                seen.append(ref)
    return seen
