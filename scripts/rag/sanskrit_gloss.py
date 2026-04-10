"""Sanskrit reading aids via Claude Haiku (prep step before main Sonnet RAG answer)."""

from __future__ import annotations

import logging

import llm as llm_module
from config import LLMProvider, RAGConfig

logger = logging.getLogger(__name__)

_MAX_PASSAGE_CHARS = 12000

_SYSTEM = """You are a Sanskrit reader's assistant for Hindu scripture retrieval.
Given Devanagari passages (and any transliteration/translation already provided), add concise aids only:
- IAST or key phrase transliteration where it helps disambiguate
- Short English glosses for important terms or compounds when useful
Do not invent verses or doctrine beyond what is shown. Output plain text."""

_USER = """Research question: {question}

Passages (focus on Sanskrit lines):
{passages}

Provide compact reading notes that help someone parse the Devanagari. If a full English translation is already given for a verse, keep notes minimal (term highlights only)."""


def _verse_sanskrit_excerpt(results: list[dict]) -> str:
    parts: list[str] = []
    for r in results:
        if r.get("chunk_type") != "verse":
            continue
        sk = (r.get("sanskrit") or "").strip()
        if not sk:
            continue
        header = r.get("source_text") or ""
        if r.get("chapter_name"):
            header += f" — {r['chapter_name']}"
        if r.get("verse_num"):
            header += f", Verse {r['verse_num']}"
        tl = (r.get("transliteration") or "").strip()
        tr = (r.get("translation") or "").strip()
        block = f"[{header}]\nSanskrit: {sk}"
        if tl:
            block += f"\nTransliteration: {tl}"
        if tr:
            block += f"\nTranslation: {tr}"
        parts.append(block)
    return "\n\n".join(parts)


def augment_context_with_sanskrit_gloss(
    base_context: str,
    results: list[dict],
    question: str,
    config: RAGConfig,
) -> str:
    """If verses include Sanskrit, call Haiku once for glosses; then Sonnet uses full context + notes."""
    if config.llm_provider != LLMProvider.ANTHROPIC:
        return base_context

    excerpt = _verse_sanskrit_excerpt(results)
    if not excerpt.strip():
        return base_context

    if len(excerpt) > _MAX_PASSAGE_CHARS:
        excerpt = excerpt[:_MAX_PASSAGE_CHARS] + "\n... [truncated]"

    try:
        gloss = llm_module.generate_haiku(
            system=_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": _USER.format(question=question, passages=excerpt),
                }
            ],
            config=config,
            max_tokens=2048,
            temperature=0.2,
        ).strip()
    except Exception:
        logger.debug("Sanskrit Haiku gloss failed", exc_info=True)
        return base_context

    if not gloss:
        return base_context

    return base_context + "\n\n--- Sanskrit reading aids (assistant) ---\n" + gloss
