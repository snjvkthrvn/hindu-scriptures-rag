"""Post-processing and optional provider moderation (OpenAI) / Anthropic short classifier."""

from __future__ import annotations

import os
import re

from config import RAGConfig, LLMProvider

# API key shapes (broad) — only redact when pattern matches; reduce accidental leaks in answers.
_PATTERNS = [
    re.compile(r"sk-(?:ant|live|proj)-[A-Za-z0-9_\-]{10,}"),
    re.compile(r"sk_[A-Za-z0-9]{20,}"),
    re.compile(r"AIza[0-9A-Za-z_\-]{20,}"),
    re.compile(r"eyJ[a-zA-Z0-9_\-]*\.[a-zA-Z0-9_\-]*\.[a-zA-Z0-9_\-]*"),  # JWT shape
    re.compile(
        r"xox[baprs]-[0-9]+-[0-9]+-[A-Za-z0-9]+",
    ),
]


def redact_likely_secrets(text: str) -> str:
    """Redact substrings that look like API keys or tokens from model output."""
    if not text:
        return text
    out = text
    for pat in _PATTERNS:
        out = pat.sub("[redacted]", out)
    return out


def _anthropic_fast_unsafe_check(text: str, config: RAGConfig) -> bool:
    """One Haiku call: returns True if content should be blocked (replaced)."""
    import anthropic

    if config is None:
        config = RAGConfig()
    if not (config.anthropic_api_key or "").strip():
        return False

    model = os.environ.get("RAG_LLM_MODERATION_MODEL", "claude-3-5-haiku-20241022")
    sample = (text or "")[:12000]
    if not sample.strip():
        return False

    system = (
        "You are a content classifier for a public scripture Q&A app. "
        "Reply with exactly one token: 0 = acceptable (including religious or philosophical text), "
        "1 = must block (illegal how-to, sexual content involving minors, graphic violence, "
        "hate, or exfiltration of secret keys). No explanation."
    )
    try:
        client = anthropic.Anthropic(api_key=config.anthropic_api_key)
        from llm import _anthropic_extras

        resp = client.messages.create(
            model=model,
            max_tokens=3,
            temperature=0.0,
            system=system,
            messages=[{"role": "user", "content": sample}],
            **_anthropic_extras(),
        )
        out = "".join(
            b.text for b in resp.content if getattr(b, "type", None) == "text"
        )
    except Exception:
        return False

    return out.strip().startswith("1")


def finalize_model_output(text: str, config: RAGConfig) -> str:
    """Secret redact + optional Anthropic classifier (non-streaming paths only)."""
    if config is None:
        config = RAGConfig()
    t = redact_likely_secrets(text or "")
    if not config.llm_moderation_enabled or config.llm_provider != LLMProvider.ANTHROPIC:
        return t
    if _anthropic_fast_unsafe_check(t, config):
        return "This response was withheld pending safety review. Please rephrase your question in terms of the scriptures."
    return t


def check_openai_user_moderation(question: str, config: RAGConfig) -> None:
    """Call OpenAI moderation on user text; raises api_security.UserInputError if blocked."""
    from api_security import UserInputError

    if not config.openai_moderation_enabled or config.llm_provider != LLMProvider.OPENAI:
        return
    if not (config.openai_api_key or "").strip():
        return
    try:
        from openai import OpenAI
    except ImportError:
        return

    client = OpenAI(api_key=config.openai_api_key)
    try:
        m = client.moderations.create(
            model="omni-moderation-latest",
            input=question[:32000],
        )
    except Exception:
        return
    r0 = m.results[0] if m.results else None
    if r0 and getattr(r0, "flagged", False):
        raise UserInputError("This request could not be processed for content policy reasons.")


def check_openai_output_moderation(text: str, config: RAGConfig) -> str:
    """If OpenAI moderation flags model output, replace with a safe string."""
    if not config.openai_moderation_enabled or config.llm_provider is not LLMProvider.OPENAI:
        return text
    if not (config.openai_api_key or "").strip() or not (text or "").strip():
        return text
    try:
        from openai import OpenAI
    except ImportError:
        return text

    client = OpenAI(api_key=config.openai_api_key)
    try:
        m = client.moderations.create(
            model="omni-moderation-latest",
            input=(text or "")[:32000],
        )
    except Exception:
        return text
    r0 = m.results[0] if m.results else None
    if r0 and getattr(r0, "flagged", False):
        return "This response was withheld pending content review."
    return text
