"""Generate follow-up questions using Claude Haiku.

Called after the main answer is complete. Fails silently to an empty list —
never blocks the answer stream.
"""

from __future__ import annotations

import json
import logging

from anthropic import Anthropic

logger = logging.getLogger(__name__)

FOLLOWUP_PROMPT = """\
Given this Q&A about Hindu scripture, suggest 3 natural follow-up questions \
the reader might want to ask next. Return JSON only:
{{"questions": ["...", "...", "..."]}}

Question: {q}

Answer: {a}"""

_MODEL = "claude-haiku-4-5-20251001"
_MAX_ANSWER_CHARS = 3000
_MAX_TOKENS = 400


def generate_followups(
    client: Anthropic,
    question: str,
    answer: str,
) -> list[str]:
    """Ask Haiku for 3 follow-up questions. Returns [] on any failure."""
    try:
        truncated = answer[:_MAX_ANSWER_CHARS]
        resp = client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            messages=[
                {
                    "role": "user",
                    "content": FOLLOWUP_PROMPT.format(q=question, a=truncated),
                }
            ],
        )
        text = resp.content[0].text.strip()

        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0]

        data = json.loads(text)
        questions = data.get("questions", [])
        return [q for q in questions if isinstance(q, str)][:3]

    except Exception:
        logger.debug("Follow-up generation failed", exc_info=True)
        return []
