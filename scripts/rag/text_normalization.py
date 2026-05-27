"""Lexical normalization helpers for sparse Sanskrit search.

Dense embeddings handle cross-lingual matching. These helpers are only
for BM25, where exact token spelling matters: `kṛṣṇa`, `krsna`, `krishna`, and
`कृष्ण` should share at least one sparse-search token.
"""

from __future__ import annotations

import re
import unicodedata

DEVANAGARI_RE = re.compile(r"[\u0900-\u097f]")
SPACE_RE = re.compile(r"\s+")


def _collapse_spaces(text: str) -> str:
    return SPACE_RE.sub(" ", text).strip()


def _has_devanagari(text: str) -> bool:
    return bool(DEVANAGARI_RE.search(text))


def _has_latin_diacritics(text: str) -> bool:
    for char in text:
        if ord(char) <= 127:
            continue
        if "\u0900" <= char <= "\u097f":
            continue
        if unicodedata.category(char).startswith("L"):
            return True
    return False


def _strip_diacritics(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return unicodedata.normalize("NFC", stripped)


def _iast_to_common_ascii(text: str) -> str:
    """Convert common IAST spellings to the ASCII forms users type.

    This intentionally optimizes for search aliases, not scholarly display:
    `śiva` -> `shiva`, `mokṣa` -> `moksha`, `kṛṣṇa` -> `krishna`.
    """
    replacements = str.maketrans(
        {
            "ā": "a",
            "ī": "i",
            "ū": "u",
            "Ā": "a",
            "Ī": "i",
            "Ū": "u",
            "ṛ": "ri",
            "ṝ": "ri",
            "Ṛ": "ri",
            "Ṝ": "ri",
            "ḷ": "li",
            "ḹ": "li",
            "Ḷ": "li",
            "Ḹ": "li",
            "ṅ": "n",
            "ñ": "n",
            "ṇ": "n",
            "Ṅ": "n",
            "Ñ": "n",
            "Ṇ": "n",
            "ṭ": "t",
            "ḍ": "d",
            "Ṭ": "t",
            "Ḍ": "d",
            "ś": "sh",
            "ṣ": "sh",
            "Ś": "sh",
            "Ṣ": "sh",
            "ṃ": "m",
            "ṁ": "m",
            "Ṃ": "m",
            "Ṁ": "m",
            "ḥ": "h",
            "Ḥ": "h",
        }
    )
    return _strip_diacritics(text.translate(replacements)).lower()


def _devanagari_to_iast(text: str) -> str:
    try:
        from indic_transliteration import sanscript
    except ImportError:
        return ""

    return sanscript.transliterate(text, sanscript.DEVANAGARI, sanscript.IAST)


def lexical_aliases(text: str) -> list[str]:
    """Return normalized aliases for BM25 text/query expansion."""
    text = _collapse_spaces(text)
    if not text:
        return []

    candidates: list[str] = []
    if _has_devanagari(text):
        iast = _collapse_spaces(_devanagari_to_iast(text))
        if iast:
            candidates.append(iast)

    if _has_latin_diacritics(text):
        candidates.append(_strip_diacritics(text).lower())
        candidates.append(_iast_to_common_ascii(text))

    for candidate in list(candidates):
        if _has_latin_diacritics(candidate):
            candidates.append(_strip_diacritics(candidate).lower())
            candidates.append(_iast_to_common_ascii(candidate))

    # Preserve order while dropping empty/exact duplicates.
    seen: set[str] = set()
    aliases: list[str] = []
    for candidate in candidates:
        alias = _collapse_spaces(candidate)
        if not alias or alias == text or alias in seen:
            continue
        seen.add(alias)
        aliases.append(alias)
    return aliases


def build_sparse_text(parts: list[str]) -> str:
    """Build BM25 text with raw fields plus Sanskrit lexical aliases."""
    out: list[str] = []
    for part in parts:
        part = _collapse_spaces(part or "")
        if not part:
            continue
        out.append(part)
        out.extend(lexical_aliases(part))
    return " ".join(out)
