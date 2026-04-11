"""Routing heuristics for adaptive English/full-corpus retrieval."""

from __future__ import annotations

import re
from enum import Enum


class RetrievalMode(str, Enum):
    ENGLISH = "english"
    FULL = "full"
    BOTH = "both"


FULL_REF_RE = re.compile(
    r"\b(?:BG|RV|AV|YV|VR|MBh|RCM|Bhagavad\s+Gita|Gita)\s*\d",
    re.IGNORECASE,
)
ENGLISH_ONLY_REF_RE = re.compile(r"\b(?:YS|Yoga\s+Sutra(?:s)?)\s*\d", re.IGNORECASE)
DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
DIACRITIC_RE = re.compile(r"[āīūṛṝḷḹṅñṭḍṇśṣḥṃṁ]")
FULL_KEYWORD_PATTERNS = (
    re.compile(r"commentar(?:y|ies|ial)?"),
    re.compile(r"school(?:s)?"),
    re.compile(r"advaita"),
    re.compile(r"compar(?:e|es|ed|ing|ison|isons)?"),
    re.compile(r"original(?:s)?"),
    re.compile(r"transliterat(?:e|es|ed|ing|ion|ions)?"),
    re.compile(r"sanskrit"),
    re.compile(r"quot(?:e|es|ed|ing|ation|ations)?"),
    re.compile(r"stor(?:y|ies)"),
    re.compile(r"dialog(?:ue|ues)"),
)
ESCALATION_KEYWORD_PATTERNS = (
    re.compile(r"compar(?:e|es|ed|ing|ison|isons)?"),
    re.compile(r"commentar(?:y|ies|ial)?"),
    re.compile(r"original(?:s)?"),
    re.compile(r"sanskrit"),
)


def _contains_keyword(text: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
    words = re.findall(r"[a-z]+", text)
    return any(pattern.fullmatch(word) for word in words for pattern in patterns)


def route_question(question: str) -> RetrievalMode:
    text = question.strip()
    lowered = text.lower()
    english_only_ref = bool(ENGLISH_ONLY_REF_RE.search(text))
    full_signal = bool(
        FULL_REF_RE.search(text)
        or DEVANAGARI_RE.search(text)
        or DIACRITIC_RE.search(lowered)
        or _contains_keyword(lowered, FULL_KEYWORD_PATTERNS)
    )

    if full_signal:
        return RetrievalMode.FULL
    if english_only_ref:
        return RetrievalMode.ENGLISH
    return RetrievalMode.ENGLISH


def should_escalate(question: str, mode: RetrievalMode, results: list[dict], top_k: int) -> bool:
    if mode == RetrievalMode.BOTH:
        return False
    if len(results) < max(2, top_k // 3):
        return True

    source_diversity = len({r.get("source_text", "") for r in results if r.get("source_text")})
    if source_diversity <= 1 and top_k >= 6:
        return True

    if mode == RetrievalMode.FULL:
        return False

    lowered = question.lower()
    return _contains_keyword(lowered, ESCALATION_KEYWORD_PATTERNS)
