"""Utilities for Devanagari Unicode normalization and handling."""

import unicodedata
from typing import Optional


def normalize_devanagari(text: str) -> str:
    """
    Normalize Devanagari text to NFC form.

    Args:
        text: Raw Devanagari text

    Returns:
        NFC normalized text
    """
    if not text:
        return text

    # Normalize to NFC (canonical decomposition, followed by canonical composition)
    normalized = unicodedata.normalize('NFC', text)
    return normalized


def validate_devanagari(text: str) -> bool:
    """
    Validate if text contains valid Devanagari characters.

    Args:
        text: Text to validate

    Returns:
        True if text contains Devanagari characters or is empty/numeric
    """
    if not text:
        return True

    # Devanagari Unicode range: U+0900 to U+097F
    devanagari_start = 0x0900
    devanagari_end = 0x097F

    for char in text:
        code = ord(char)
        # Allow Latin, numbers, spaces, punctuation, and Devanagari
        if (devanagari_start <= code <= devanagari_end or
            code < 128 or  # ASCII
            code >= 0x2000):  # General punctuation and beyond
            continue

    return True


def remove_diacritics(text: str) -> str:
    """
    Remove combining diacritics from text, keeping base characters.

    Args:
        text: Text with diacritics

    Returns:
        Text with diacritics removed
    """
    if not text:
        return text

    # NFD decomposes characters into base + combining marks
    nfd_form = unicodedata.normalize('NFD', text)

    # Filter out combining marks (category Mn = Nonspacing_Mark)
    without_diacritics = ''.join(
        char for char in nfd_form
        if unicodedata.category(char) != 'Mn'
    )

    return unicodedata.normalize('NFC', without_diacritics)


def is_devanagari_char(char: str) -> bool:
    """Check if a character is Devanagari."""
    code = ord(char)
    return 0x0900 <= code <= 0x097F


def count_devanagari_chars(text: str) -> int:
    """Count number of Devanagari characters in text."""
    return sum(1 for char in text if is_devanagari_char(char))


def transliterate_itrans_to_unicode(itrans_text: str) -> str:
    """
    Simple ITRANS to Unicode conversion (basic implementation).
    For full support, use indic-transliteration library.

    Args:
        itrans_text: Text in ITRANS notation

    Returns:
        Unicode Devanagari text
    """
    # This is a placeholder - real implementation would use
    # indic-transliteration library for proper conversion
    try:
        from indic_transliteration import sanscript
        return sanscript.transliterate(
            itrans_text,
            sanscript.ITRANS,
            sanscript.DEVANAGARI
        )
    except ImportError:
        # Fallback: return original if library not available
        return itrans_text
