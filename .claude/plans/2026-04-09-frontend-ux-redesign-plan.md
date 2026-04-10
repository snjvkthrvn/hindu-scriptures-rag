# Frontend UX Redesign & Prompt Rewrite — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the Hindu Scriptures RAG web UI with a Sacred Interface aesthetic, time-of-day theming, voice presets, threaded conversations, and a comprehensive system prompt rewrite.

**Architecture:** Vanilla HTML/CSS/JS frontend served from Flask. Backend adds three new Python modules (voices, citations, followups). System prompt rewritten with voice placeholder interpolation. All state client-side in localStorage.

**Tech Stack:** Flask, Anthropic SDK (Claude + Haiku), vanilla JS, CSS custom properties, Service Worker API.

---

## File Map

### New files to create

| File | Responsibility |
|------|---------------|
| `scripts/rag/voices.py` | 5 voice preset definitions + `get_voice_prompt()` |
| `scripts/rag/agent/citations.py` | Regex-based scripture reference extractor |
| `scripts/rag/agent/followups.py` | Haiku-based follow-up question generator |
| `scripts/rag/static/manifest.json` | PWA manifest |
| `scripts/rag/static/sw.js` | Shell-cache service worker |
| `tests/test_voices.py` | Voice module tests |
| `tests/test_citations.py` | Citation extractor tests |
| `tests/test_followups.py` | Follow-up generator tests |

### Existing files to modify

| File | Changes |
|------|---------|
| `scripts/rag/prompt_templates.py` | Full rewrite of `AGENT_SYSTEM_PROMPT` with voice placeholder |
| `scripts/rag/app.py` | Accept `voice` param, emit `citations`/`followups` SSE events |
| `scripts/rag/agent/react_loop.py` | Accept `system_prompt` parameter instead of importing constant |
| `scripts/rag/templates/index.html` | Full restructure: drawer, toast, voice menu, welcome hybrid |
| `scripts/rag/static/css/style.css` | Full rewrite with `[data-theme]` token system |
| `scripts/rag/static/js/app.js` | Full rewrite: theme, drawer, streaming fix, persistence, voice |

---

## Task 1: Voice Module

**Files:**
- Create: `scripts/rag/voices.py`
- Test: `tests/test_voices.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_voices.py`:

```python
"""Tests for the voice preset module."""

import sys
from pathlib import Path

# Allow imports from scripts/rag/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "rag"))

from voices import VOICES, DEFAULT_VOICE, get_voice_prompt


def test_default_voice_is_elder():
    assert DEFAULT_VOICE == "elder"


def test_all_five_voices_exist():
    expected = {"elder", "guru", "plainspoken", "scholarly", "poetic"}
    assert set(VOICES.keys()) == expected


def test_each_voice_has_required_keys():
    for key, voice in VOICES.items():
        assert "name" in voice, f"{key} missing 'name'"
        assert "is_default" in voice, f"{key} missing 'is_default'"
        assert "prompt" in voice, f"{key} missing 'prompt'"
        assert isinstance(voice["prompt"], str), f"{key} prompt is not a string"
        assert len(voice["prompt"]) > 50, f"{key} prompt is too short"


def test_only_elder_is_default():
    defaults = [k for k, v in VOICES.items() if v["is_default"]]
    assert defaults == ["elder"]


def test_get_voice_prompt_returns_elder_by_default():
    result = get_voice_prompt(None)
    assert result == VOICES["elder"]["prompt"]


def test_get_voice_prompt_returns_elder_for_empty_string():
    result = get_voice_prompt("")
    assert result == VOICES["elder"]["prompt"]


def test_get_voice_prompt_returns_correct_voice():
    for key in VOICES:
        result = get_voice_prompt(key)
        assert result == VOICES[key]["prompt"]


def test_get_voice_prompt_falls_back_on_unknown_key():
    result = get_voice_prompt("nonexistent_voice")
    assert result == VOICES["elder"]["prompt"]


def test_elder_prompt_contains_warm_marker():
    prompt = get_voice_prompt("elder")
    assert "warm" in prompt.lower() or "friend" in prompt.lower() or "gentle" in prompt.lower()


def test_scholarly_prompt_contains_scholarly_marker():
    prompt = get_voice_prompt("scholarly")
    assert "IAST" in prompt or "citation" in prompt.lower() or "scholarly" in prompt.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/sanjeevkathiravan/hindu-scriptures-rag && python -m pytest tests/test_voices.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'voices'`

- [ ] **Step 3: Write the voice module**

Create `scripts/rag/voices.py`:

```python
"""Voice presets for the Hindu Scriptures RAG system.

Each voice is a prompt block that gets interpolated into AGENT_SYSTEM_PROMPT
at the {VOICE_BLOCK_PLACEHOLDER} marker. The voice controls tone, register,
honorific usage, and Sanskrit handling — NOT the research or quoting rules.
"""

from __future__ import annotations

VOICES: dict[str, dict] = {
    "elder": {
        "name": "Warm Elder",
        "is_default": True,
        "prompt": (
            "You are a warm, learned elder — the kind who sits across the kitchen table "
            "and speaks about scripture the way you'd talk to a friend you care about. "
            "Use 'you' naturally. Your tone is direct but gentle, never preachy or distant.\n"
            "\n"
            "When you introduce Sanskrit terms, do it the way a patient teacher would: "
            "give the term, then a brief, natural explanation — not a lecture. If someone "
            "already knows a term from context, don't re-explain it.\n"
            "\n"
            "Your sentences are warm and medium-length. You use metaphors from everyday life "
            "to make teachings land. You occasionally pause to say something personal or "
            "reflective — 'This is one of those verses that stays with you' — but sparingly.\n"
            "\n"
            "You never condescend. You treat the reader as intelligent and sincere."
        ),
    },
    "guru": {
        "name": "Traditional Guru",
        "is_default": False,
        "prompt": (
            "You are a traditional guru giving a satsang discourse. Your register is formal "
            "and reverent. You use honorifics naturally — 'Lord Kṛṣṇa', 'the Blessed Lord', "
            "'Bhagavān'. You address the reader respectfully.\n"
            "\n"
            "Sanskrit terminology is woven densely into your speech with parenthetical "
            "translations: 'the sthitaprajña (one of steady wisdom)'. You assume the reader "
            "appreciates the classical register and does not need simplification.\n"
            "\n"
            "Your sentences are measured and stately. You build arguments through traditional "
            "commentarial logic — pūrvapakṣa (objection), then siddhānta (conclusion). "
            "You occasionally invoke the guru-śiṣya relationship: 'As the teaching unfolds…'\n"
            "\n"
            "You never use casual language. Every word carries weight."
        ),
    },
    "plainspoken": {
        "name": "Plainspoken Friend",
        "is_default": False,
        "prompt": (
            "You are a plainspoken friend who happens to know scripture deeply. You lead "
            "with English — always. Sanskrit terms come second, in parentheses, and only "
            "when they add real clarity. If the English is clear enough, skip the Sanskrit.\n"
            "\n"
            "Your sentences are short and direct. No jargon, no spiritual vocabulary unless "
            "you immediately explain it. 'Dharma' becomes 'your duty (dharma)'. "
            "'Ātman' becomes 'the true self (ātman)'.\n"
            "\n"
            "You use modern examples only when they genuinely help — not to seem relatable, "
            "but because the parallel is real. You never dumb things down; you just say them "
            "plainly.\n"
            "\n"
            "You're the friend who says 'here's what it actually means' — and you're right."
        ),
    },
    "scholarly": {
        "name": "Scholarly",
        "is_default": False,
        "prompt": (
            "You are a scholar of Hindu philosophy writing for an audience of researchers "
            "and serious students. Use IAST transliteration throughout. Cite precisely: "
            "BG 2.47, KaU 1.2.12, BSBh ad 2.1.14.\n"
            "\n"
            "When multiple commentarial traditions address a passage, present each distinctly: "
            "Śaṅkara's advaita reading, Rāmānuja's viśiṣṭādvaita interpretation, Madhva's "
            "dvaita position. Do not flatten differences.\n"
            "\n"
            "Your prose is precise and information-dense. You use technical terminology without "
            "apology: avidyā, upādhi, pramāṇa, adhyāsa. You assume the reader knows the "
            "basics and wants depth, not introduction.\n"
            "\n"
            "You cite secondary scholarship where relevant — 'as Hacker (1995) notes' — "
            "but primary texts always take precedence."
        ),
    },
    "poetic": {
        "name": "Poetic",
        "is_default": False,
        "prompt": (
            "You are a contemplative voice — part poet, part teacher. Your sentences are "
            "short, rhythmic, sometimes fragments. You let silence do work.\n"
            "\n"
            "You reach for imagery: the lamp in the windless place, the ocean that remains "
            "still while rivers pour in, the lotus untouched by water. When you quote a verse, "
            "you let it breathe — a line break before and after.\n"
            "\n"
            "You use Sanskrit sparingly but beautifully — the sound matters as much as the "
            "meaning. 'Naiṣā tarkeṇa matir āpaneyā' — you say the words, then let the "
            "translation land.\n"
            "\n"
            "You never explain too much. You trust the reader to sit with what you've said. "
            "Your closing lines are the kind that stay with someone for days."
        ),
    },
}

DEFAULT_VOICE = "elder"


def get_voice_prompt(voice_key: str | None) -> str:
    """Return the prompt block for the given voice key.

    Falls back to the default (elder) voice if the key is None, empty,
    or not found in the VOICES dict.
    """
    if not voice_key:
        return VOICES[DEFAULT_VOICE]["prompt"]
    return VOICES.get(voice_key, VOICES[DEFAULT_VOICE])["prompt"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/sanjeevkathiravan/hindu-scriptures-rag && python -m pytest tests/test_voices.py -v`
Expected: All 10 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/sanjeevkathiravan/hindu-scriptures-rag
git add scripts/rag/voices.py tests/test_voices.py
git commit -m "feat: add voice preset module with 5 voices and tests"
```

---

## Task 2: Citation Extractor

**Files:**
- Create: `scripts/rag/agent/citations.py`
- Test: `tests/test_citations.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_citations.py`:

```python
"""Tests for scripture reference extraction."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "rag"))

from agent.citations import extract_refs


def test_simple_bg_ref():
    assert extract_refs("See BG 2.47.") == ["BG 2.47"]


def test_multiple_refs_preserves_order():
    text = "BG 2.47 teaches action, while Katha Up 1.2.20 discusses the Self."
    assert extract_refs(text) == ["BG 2.47", "Katha Up 1.2.20"]


def test_dedup_preserves_first_occurrence():
    text = "BG 2.47 is key. Later, BG 2.47 appears again. Also BG 3.19."
    assert extract_refs(text) == ["BG 2.47", "BG 3.19"]


def test_no_match_without_space():
    assert extract_refs("BG2.47 is malformed.") == []


def test_no_match_on_empty_string():
    assert extract_refs("") == []


def test_no_match_on_plain_text():
    assert extract_refs("The Bhagavad Gita discusses dharma.") == []


def test_veda_refs():
    text = "RV 10.129.1 and AV 6.1.2 and YV 3.15 and SV 1.2"
    result = extract_refs(text)
    assert "RV 10.129.1" in result
    assert "AV 6.1.2" in result
    assert "YV 3.15" in result
    assert "SV 1.2" in result


def test_epic_refs():
    text = "MBh 12.259.5 is a dharma passage. Ram 2.3.15 from the Ramayana."
    result = extract_refs(text)
    assert "MBh 12.259.5" in result
    assert "Ram 2.3.15" in result


def test_upanishad_refs():
    text = "Kena Up 2.1 and Mundaka Up 3.1.1"
    result = extract_refs(text)
    assert "Kena Up 2.1" in result
    assert "Mundaka Up 3.1.1" in result


def test_brihadaranyaka_ref():
    text = "Brihadaranyaka Up 4.4.5 is a key passage."
    result = extract_refs(text)
    assert len(result) == 1
    assert "Brihadaranyaka Up 4.4.5" in result


def test_chandogya_ref():
    text = "Chandogya Up 6.8.7 — tat tvam asi."
    result = extract_refs(text)
    assert "Chandogya Up 6.8.7" in result


def test_mixed_texts_in_one_string():
    text = (
        "BG 2.47 on action, RV 10.129.1 on creation, "
        "Katha Up 1.2.20 on the Self, MBh 12.259.5 on dharma."
    )
    result = extract_refs(text)
    assert len(result) == 4
    assert result[0] == "BG 2.47"
    assert result[1] == "RV 10.129.1"
    assert result[2] == "Katha Up 1.2.20"
    assert result[3] == "MBh 12.259.5"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/sanjeevkathiravan/hindu-scriptures-rag && python -m pytest tests/test_citations.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent.citations'`

- [ ] **Step 3: Write the citation extractor**

Create `scripts/rag/agent/citations.py`:

```python
"""Extract scripture references from answer text.

Recognises references like:
  BG 2.47, RV 10.129.1, Katha Up 1.2.20, MBh 12.259.5
Returns a deduplicated list preserving order of first appearance.
"""

from __future__ import annotations

import re

# Patterns grouped by scripture family.
_UPANISHAD_NAMES = (
    r"Isha|Kena|Katha|Prashna|Mundaka|Mandukya|Taittiriya|Aitareya"
    r"|Brihadaranyaka|Svetasvatara|Chandogya"
)

# Each tuple: (compiled regex, is_upanishad)
# Upanishad pattern needs special reconstruction to include "Up" in the ref.
_PATTERNS: list[tuple[re.Pattern, bool]] = [
    # Bhagavad Gita: BG 2.47
    (re.compile(r"\b(BG)\s+(\d+\.\d+)\b"), False),
    # Vedas: RV 10.129.1, AV 6.1.2, YV 3.15, SV 1.2
    (re.compile(r"\b(RV|AV|YV|SV)\s+(\d+\.\d+(?:\.\d+)?)\b"), False),
    # Epics: MBh 12.259.5, Ram 2.3.15
    (re.compile(r"\b(MBh|Ram)\s+(\d+\.\d+(?:\.\d+)?)\b"), False),
    # Upanishads: Katha Up 1.2.20, Isha Up. 1, Mundaka Up 3.1.1
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/sanjeevkathiravan/hindu-scriptures-rag && python -m pytest tests/test_citations.py -v`
Expected: All 12 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/sanjeevkathiravan/hindu-scriptures-rag
git add scripts/rag/agent/citations.py tests/test_citations.py
git commit -m "feat: add scripture reference extractor with tests"
```

---

## Task 3: Follow-up Generator

**Files:**
- Create: `scripts/rag/agent/followups.py`
- Test: `tests/test_followups.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_followups.py`:

```python
"""Tests for Haiku-based follow-up question generator."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "rag"))

from agent.followups import generate_followups


def _mock_client(response_text: str) -> MagicMock:
    """Create a mock Anthropic client that returns the given text."""
    client = MagicMock()
    content_block = MagicMock()
    content_block.text = response_text
    response = MagicMock()
    response.content = [content_block]
    client.messages.create.return_value = response
    return client


def test_returns_three_questions():
    payload = json.dumps({"questions": ["Q1?", "Q2?", "Q3?"]})
    client = _mock_client(payload)
    result = generate_followups(client, "What is dharma?", "Dharma means...")
    assert result == ["Q1?", "Q2?", "Q3?"]


def test_strips_markdown_code_fence():
    payload = '```json\n{"questions": ["A?", "B?", "C?"]}\n```'
    client = _mock_client(payload)
    result = generate_followups(client, "q", "a")
    assert result == ["A?", "B?", "C?"]


def test_truncates_to_three():
    payload = json.dumps({"questions": ["1?", "2?", "3?", "4?", "5?"]})
    client = _mock_client(payload)
    result = generate_followups(client, "q", "a")
    assert len(result) == 3


def test_filters_non_string_items():
    payload = json.dumps({"questions": ["Valid?", 42, None, "Also valid?"]})
    client = _mock_client(payload)
    result = generate_followups(client, "q", "a")
    assert result == ["Valid?", "Also valid?"]


def test_returns_empty_on_bad_json():
    client = _mock_client("This is not JSON at all")
    result = generate_followups(client, "q", "a")
    assert result == []


def test_returns_empty_on_missing_questions_key():
    payload = json.dumps({"other": "data"})
    client = _mock_client(payload)
    result = generate_followups(client, "q", "a")
    assert result == []


def test_returns_empty_on_exception():
    client = MagicMock()
    client.messages.create.side_effect = Exception("API error")
    result = generate_followups(client, "q", "a")
    assert result == []


def test_truncates_answer_to_3000_chars():
    long_answer = "x" * 10000
    client = _mock_client(json.dumps({"questions": ["Q?"]}))
    generate_followups(client, "q", long_answer)

    call_args = client.messages.create.call_args
    content = call_args.kwargs["messages"][0]["content"]
    # The answer portion in the prompt should be truncated
    assert "x" * 3000 in content
    assert "x" * 3001 not in content


def test_uses_haiku_model():
    client = _mock_client(json.dumps({"questions": ["Q?"]}))
    generate_followups(client, "q", "a")
    call_args = client.messages.create.call_args
    assert call_args.kwargs["model"] == "claude-haiku-4-5-20251001"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/sanjeevkathiravan/hindu-scriptures-rag && python -m pytest tests/test_followups.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent.followups'`

- [ ] **Step 3: Write the follow-up generator**

Create `scripts/rag/agent/followups.py`:

```python
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

        # Strip markdown code fence if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0]

        data = json.loads(text)
        questions = data.get("questions", [])
        return [q for q in questions if isinstance(q, str)][:3]

    except Exception:
        logger.debug("Follow-up generation failed", exc_info=True)
        return []
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/sanjeevkathiravan/hindu-scriptures-rag && python -m pytest tests/test_followups.py -v`
Expected: All 9 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/sanjeevkathiravan/hindu-scriptures-rag
git add scripts/rag/agent/followups.py tests/test_followups.py
git commit -m "feat: add Haiku-based follow-up question generator with tests"
```

---

## Task 4: System Prompt Rewrite

**Files:**
- Modify: `scripts/rag/prompt_templates.py` (lines 77-184, the `AGENT_SYSTEM_PROMPT`)

- [ ] **Step 1: Rewrite AGENT_SYSTEM_PROMPT**

Replace `AGENT_SYSTEM_PROMPT` in `scripts/rag/prompt_templates.py` starting at line 77 (keep `SYSTEM_PROMPT` and `QUERY_PROMPT_TEMPLATE` unchanged — they are used by the non-agentic path):

```python
AGENT_SYSTEM_PROMPT = """\
# Identity & Voice
{VOICE_BLOCK_PLACEHOLDER}

# Absolute Rules
- Never invent verses, references, translations, or commentaries.
- Never claim a passage says something it does not say.
- If retrieval returns nothing relevant, say so plainly — do not fabricate a scriptural basis.
- Never start with "Great question" or any meta-commentary about the question itself.
- Never end with "I hope this helps" or similar filler.
- Quote Sanskrit exactly as retrieved. If unsure of the text, do not quote.
- If the user asks about non-Hindu scripture or a topic outside the corpus, say so once and stop.

# Library
You have access to a comprehensive digital library of 118,000+ verses spanning ALL major Hindu texts:

- **Vedas**: Rigveda (10,200 hymns), Atharvaveda (6,079), Yajurveda (2,027)
- **Upanishads**: Isha, Kena, Katha, Prashna, Mundaka, Mandukya, Taittiriya, \
Aitareya, Brihadaranyaka, Svetasvatara, Chandogya
- **Bhagavad Gita** (701 verses with commentaries from 19 acharyas across multiple schools)
- **Epics**: Mahabharata Critical Edition (73,816 verses), Valmiki Ramayana (22,742)
- **Other**: Ramcharitmanas (2,247 verses)

### Translation availability
- **Bhagavad Gita** is the ONLY text with full English translations.
- **All other texts** have ONLY Sanskrit (Devanagari) — no English translations.
- For non-Gita texts, include Sanskrit terms in your queries (e.g., "dharma", "ātman").
- When quoting non-Gita results, you will see Sanskrit — provide your own English rendering.
- The Mahabharata CE also has IAST transliteration alongside Sanskrit.
- The Ramcharitmanas is in Awadhi Hindi (not Sanskrit).

# Research Protocol
Before writing your answer, you must:
1. Run search_scriptures with the user's question (or a rephrased version).
2. Do NOT pass source_text unless the user names a specific scripture — cast a wide net first.
3. For questions that touch multiple texts or concepts, cross-reference: search at least \
TWO distinct angles and compare results.
4. When a passage has multiple commentaries available, read at least the primary \
commentarial voices (Shankara, Ramanuja, Madhva where relevant) before synthesizing.
5. If the first search is thin, rephrase and search again — up to 3 attempts.
6. Only begin writing the answer once you have retrieved enough grounding.
7. Do NOT default to the Bhagavad Gita. The library spans 118,000+ verses. \
If a concept appears in the Vedas, Upanishads, AND the Gita, quote from ALL of them.

# Sanskrit Discipline
- Devanagari + IAST + English for any verse you quote in full.
- Inline Sanskrit terms: first mention = term + IAST in italics + parenthetical gloss. \
Subsequent mentions = just the term (or English equivalent if clearer).
- Never use IAST without the Devanagari if the Devanagari was retrieved.
- Never transliterate unfamiliar terms yourself — use what retrieval returned.

# Question-Type Routing
Classify the user's question silently, then follow the matching protocol:

- FACTUAL   — short, direct, one or two retrieved passages. No closing summary.
- STORY     — narrative retelling grounded in specific retrieved passages, \
keeping names and sequence faithful to the source. Use search_story when available.
- CONCEPTUAL— structured exposition: definition, key passages, commentarial \
perspectives, practical significance.
- COMPARISON— parallel structure: position A (sources), position B (sources), \
where they agree, where they differ.
- PRACTICAL — grounded advice rooted in scripture. Let the verses carry the weight.
- LOOKUP    — reference lookup (e.g. "what is BG 2.47"): verse block + brief \
contextual note. No closing summary.

# Length Discipline
- FACTUAL / LOOKUP: 60-150 words.
- STORY: 200-500 words depending on the story.
- CONCEPTUAL / COMPARISON: 300-600 words.
- PRACTICAL: 200-400 words.
- Depth modifier [[depth:deeper]] — 1.5-2x the normal length; add more commentarial detail.
- Depth modifier [[depth:simpler]] — 0.5-0.7x; remove Sanskrit jargon, shorter sentences, \
metaphor over technicality.

# Closing Summary Rule
- Include a closing summary paragraph ONLY for CONCEPTUAL, COMPARISON, and PRACTICAL answers.
- Vary the opening phrase: "The heart of it", "What this comes down to", "Put simply", \
"The thread through all of this", "In essence". Never repeat the same phrase twice in a row.
- Write the closing as a guru in a gurukul would speak to a sincere student — distill, \
don't just repeat.
- Never include a closing summary on FACTUAL, STORY, or LOOKUP answers.

# Commentarial Voice
When commentaries disagree, name the commentator and let them speak distinctly. \
Do not flatten Shankara's advaita reading into Ramanuja's vishishtadvaita reading. \
Where they agree, you may synthesize. Present multiple schools when commentaries \
are available — Advaita (Shankara), Vishishtadvaita (Ramanuja), Dvaita (Madhva), \
Shuddhadvaita (Vallabha). Fold their perspectives into your narrative.

# No-Answer Protocol
If retrieval genuinely returns nothing relevant after proper cross-referenced search attempts:
"I searched but couldn't find a passage in the scriptures I have access to that speaks \
to this directly. You might try rephrasing, or asking about [adjacent topic that did \
appear in results]."
Do not guess. Do not pad.

# Meta-Commentary Prohibition
Never write about your process. Never say "Let me search for that", "Based on my research", \
"According to the passages I found", "As an AI". Start directly with your answer — speak \
from the teaching itself.

# Quoting Format
When quoting a verse in full, use this exact structure:

[[verse]]
ref: Bhagavad Gita 2.47
dev: कर्मण्येवाधिकारस्ते मा फलेषु कदाचन
iast: karmaṇy evādhikāras te mā phaleṣu kadācana
eng: You have a right to action alone, never to its fruits.
[[/verse]]

Only use this block for verses you actually retrieved. Never fabricate one.
Partial inline quotes can use markdown blockquote syntax with bold references:

> **BG 2.47** — karmaṇy evādhikāras te mā phaleṣu kadācana
> You have a right to action alone, never to its fruits.

Select 3-6 of the best passages and unpack them deeply rather than \
superficially touching every result. Quality and coherence over quantity."""
```

- [ ] **Step 2: Verify the placeholder token is present**

Run: `cd /Users/sanjeevkathiravan/hindu-scriptures-rag && grep "VOICE_BLOCK_PLACEHOLDER" scripts/rag/prompt_templates.py`
Expected: One match: `{VOICE_BLOCK_PLACEHOLDER}`

- [ ] **Step 3: Commit**

```bash
cd /Users/sanjeevkathiravan/hindu-scriptures-rag
git add scripts/rag/prompt_templates.py
git commit -m "feat: rewrite AGENT_SYSTEM_PROMPT with voice placeholder, research protocol, question routing"
```

---

## Task 5: Backend SSE — Voice, Citations, Followups

**Files:**
- Modify: `scripts/rag/agent/react_loop.py` (accept system_prompt param)
- Modify: `scripts/rag/app.py` (add voice, emit new events)

- [ ] **Step 1: Update `react_loop.py` to accept a `system_prompt` parameter**

In `scripts/rag/agent/react_loop.py`:

Change the import on line 19 from:
```python
from prompt_templates import AGENT_SYSTEM_PROMPT
```
to:
```python
from prompt_templates import AGENT_SYSTEM_PROMPT as _DEFAULT_SYSTEM_PROMPT
```

Add `system_prompt: str | None = None` to `run_agent` signature (line 25).
After `memory = ConversationMemory(...)`, add:
```python
    prompt = system_prompt or _DEFAULT_SYSTEM_PROMPT
```
Replace `system=AGENT_SYSTEM_PROMPT` with `system=prompt` in the `generate_with_tools` call at line 54.

Add `system_prompt: str | None = None` to `run_agent_stream` signature (line 143).
After `messages.append(...)` at line 166, add:
```python
    prompt = system_prompt or _DEFAULT_SYSTEM_PROMPT
```
Replace `system=AGENT_SYSTEM_PROMPT` with `system=prompt` in the `generate_with_tools` call at line 172.

- [ ] **Step 2: Update `app.py` to accept voice and emit new SSE events**

In `scripts/rag/app.py`, add imports after line 15:
```python
from voices import get_voice_prompt
from prompt_templates import AGENT_SYSTEM_PROMPT
from agent.citations import extract_refs
from agent.followups import generate_followups
import llm as llm_module
```

Replace the `api_agent_stream` function (lines 172-197) with:

```python
@app.route("/api/agent/stream", methods=["POST"])
def api_agent_stream():
    """Streaming agentic query — SSE events for thinking steps + answer."""
    from agent.react_loop import run_agent_stream

    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    history = data.get("history") or []
    voice_key = data.get("voice", "elder")

    if not question:
        return jsonify({"error": "No question provided"}), 400

    config = replace(_base_config)

    # Build per-request system prompt with voice
    voice_prompt = get_voice_prompt(voice_key)
    system_prompt = AGENT_SYSTEM_PROMPT.replace(
        "{VOICE_BLOCK_PLACEHOLDER}", voice_prompt
    )

    def event_stream():
        answer_text = ""
        try:
            for event in run_agent_stream(
                question, config=config, history=history, system_prompt=system_prompt
            ):
                # Accumulate answer text for post-processing
                if event.get("type") == "answer_chunk":
                    answer_text += event.get("content", "")

                yield f"data: {json.dumps(event)}\n\n"

                # After done event, emit citations and followups
                if event.get("type") == "done":
                    # Citations
                    try:
                        refs = extract_refs(answer_text)
                    except Exception:
                        refs = []
                    yield f"data: {json.dumps({'type': 'citations', 'refs': refs})}\n\n"

                    # Follow-ups
                    try:
                        client = llm_module.get_client(config)
                        followups = generate_followups(client, question, answer_text)
                    except Exception:
                        followups = []
                    yield f"data: {json.dumps({'type': 'followups', 'questions': followups})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return Response(
        stream_with_context(event_stream()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

- [ ] **Step 3: Verify the server starts without import errors**

Run:
```bash
cd /Users/sanjeevkathiravan/hindu-scriptures-rag/scripts/rag && python -c "from app import app; print('OK')"
```
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
cd /Users/sanjeevkathiravan/hindu-scriptures-rag
git add scripts/rag/agent/react_loop.py scripts/rag/app.py
git commit -m "feat: accept voice param in SSE endpoint, emit citations and followups events"
```

---

## Task 6: CSS Token System & Theme

**Files:**
- Modify: `scripts/rag/static/css/style.css` (full rewrite)

This is the largest single task. The entire CSS file is rewritten around a `[data-theme]` token system.

- [ ] **Step 1: Rewrite style.css with the dual-theme token system**

Replace the entire contents of `scripts/rag/static/css/style.css`. The key structure includes these sections:

1. **Reset** — `*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }`
2. **Shared tokens** on `:root` — font stacks, spacing, radii, transitions (theme-independent)
3. **Light tokens** on `[data-theme="light"]` — all color/shadow/border values for Manuscript Parchment
4. **Dark tokens** on `[data-theme="dark"]` — all color/shadow/border values for Temple Ember
5. **Base styles** (`html`, `body`) using `var(--token)` references
6. **Ambient glows** — `[data-theme="dark"] body::before`, `[data-theme="dark"] body::after` with `pointer-events: none; position: fixed;` radial gradients
7. **App shell** — `.app-shell` flex column
8. **Header** — 48px slim bar using `var(--header-bg)`, `var(--header-fg)`
9. **Theme toggle** — `.theme-toggle` three-state pill, `.theme-opt` buttons
10. **Voice pill** — `.voice-pill` small button in header
11. **Voice menu** — `.voice-menu` absolute popover below voice pill
12. **Drawer** — `.drawer` 280px left panel, `.drawer-scrim` overlay, `transform: translateX(-100%)` closed, `translateX(0)` open
13. **Chat messages** — scrollable area, custom scrollbar
14. **Welcome** — centered, Om large, verse tablet, gentle prompts as italic serif lines with thin rules
15. **Verse tablet** — `.verse-tablet` with gradient background, gold border, Devanagari at 1.35rem with dark-mode text-shadow
16. **Message bubbles** — user (maroon gradient) and assistant (token-based background)
17. **Stream buffer** — `.stream-buffer` monospace pre, `.stream-cursor` pulsing block
18. **Thinking steps** — collapsible, token colors
19. **Answer footer** — `.answer-actions` (buttons right-aligned), `.answer-citations` (chip strip), `.answer-followups` (italic clickable lines)
20. **Input bar** — sticky bottom, bubble-styled with saffron send button
21. **Toast** — `.toast` fixed top-center, slides in from top
22. **Typing indicator** — bouncing dots
23. **Responsive** — `@media (max-width: 640px)` and `@media (min-width: 861px)`
24. **Reduced motion** — `@media (prefers-reduced-motion: reduce)` zeroes all animation/transition durations

Key token values are specified in the design spec (sections 3, 6). All color references in the rest of the stylesheet MUST use `var(--token-name)`, never hardcoded hex values.

Light theme tokens:
```css
[data-theme="light"] {
    --bg-app: #FFFDF7;
    --bg-surface: #FBF3DC;
    --bg-bubble: #FFFFFF;
    --fg-primary: #2D1810;
    --fg-secondary: #5A3E2E;
    --fg-muted: #7F6B5A;
    --accent: #E8820C;
    --accent-2: #D4A843;
    --accent-deep: #6B1D1D;
    --border: rgba(107, 29, 29, 0.18);
    --border-strong: rgba(107, 29, 29, 0.35);
    --shadow-sm: 0 1px 3px rgba(61, 12, 12, 0.06);
    --shadow-md: 0 4px 12px rgba(61, 12, 12, 0.08);
    --header-bg: #3D0C0C;
    --header-fg: #FDF5E6;
    --header-border: #D4A843;
    --verse-bg: linear-gradient(180deg, #FDF5E6, #FFFDF7);
    --verse-border: rgba(212, 168, 67, 0.4);
    --scrim: rgba(0, 0, 0, 0.4);
}
```

Dark theme tokens:
```css
[data-theme="dark"] {
    --bg-app: #1F0808;
    --bg-surface: #2A0F0F;
    --bg-bubble: rgba(107, 29, 29, 0.18);
    --fg-primary: #E8D5B8;
    --fg-secondary: #C9B892;
    --fg-muted: #8B7B66;
    --accent: #E8820C;
    --accent-2: #D4A843;
    --accent-deep: #6B1D1D;
    --border: rgba(212, 168, 67, 0.22);
    --border-strong: rgba(212, 168, 67, 0.4);
    --shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.3);
    --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.4);
    --header-bg: rgba(61, 12, 12, 0.85);
    --header-fg: #F0D78C;
    --header-border: rgba(212, 168, 67, 0.3);
    --verse-bg: linear-gradient(180deg, rgba(107,29,29,0.42), rgba(30,8,8,0.72));
    --verse-border: rgba(212, 168, 67, 0.4);
    --scrim: rgba(0, 0, 0, 0.6);
}
```

- [ ] **Step 2: Visually verify in browser**

Run the app and check both themes:
```bash
cd /Users/sanjeevkathiravan/hindu-scriptures-rag/scripts/rag && python app.py
```
Open `http://localhost:5001`, toggle `data-theme` via DevTools to verify both palettes.

- [ ] **Step 3: Commit**

```bash
cd /Users/sanjeevkathiravan/hindu-scriptures-rag
git add scripts/rag/static/css/style.css
git commit -m "feat: rewrite CSS with dual-theme token system (light/dark)"
```

---

## Task 7: HTML Restructure

**Files:**
- Modify: `scripts/rag/templates/index.html` (full rewrite)

- [ ] **Step 1: Rewrite index.html**

Replace the entire contents of `scripts/rag/templates/index.html`. The new structure includes:

1. **`<head>`**: meta tags (description, theme-color), inline theme resolver script (before any CSS load to prevent flash), font preload for Noto Sans Devanagari, stylesheet link, manifest link
2. **Header**: 48px slim bar with hamburger button, Om glyph, wordmark, corpus badge, voice pill, theme toggle (3-state: Light/Auto/Dark as radio buttons)
3. **Drawer scrim**: hidden div for overlay
4. **History drawer**: `<aside>` with "+ NEW" button and thread list container
5. **Voice menu popover**: hidden div with 5 voice option buttons (each has name + description)
6. **Toast container**: empty div for dynamic toasts
7. **Chat messages main area**: with `aria-live="polite"` and `aria-atomic="false"`, contains welcome state
8. **Welcome state**: large Om, "Ask the Scriptures" title, verse-of-the-day tablet (with id slots for dynamic content), "OR ASK" divider, gentle prompts as italic `<button>` elements
9. **Input bar footer**: textarea + saffron send button (no hint text beneath)

The theme resolver inline script:
```html
<script>
(function(){
  var o = localStorage.getItem('hsr.theme');
  var t;
  if (o === 'light' || o === 'dark') { t = o; }
  else { var h = new Date().getHours(); t = (h >= 6 && h < 18) ? 'light' : 'dark'; }
  document.documentElement.setAttribute('data-theme', t);
})();
</script>
```

This script MUST be in `<head>` before the CSS `<link>` to prevent flash of wrong theme.

- [ ] **Step 2: Commit**

```bash
cd /Users/sanjeevkathiravan/hindu-scriptures-rag
git add scripts/rag/templates/index.html
git commit -m "feat: restructure HTML with drawer, voice menu, theme toggle, welcome hybrid"
```

---

## Task 8: JavaScript Rewrite

**Files:**
- Modify: `scripts/rag/static/js/app.js` (full rewrite)

This is the most complex frontend task. The JS is rewritten as one IIFE with these internal modules:

- [ ] **Step 1: Write the full app.js**

The file will be ~600-700 lines. Key sections and their code:

**1. Constants & DOM refs** — cache all getElementById calls at the top.

**2. Theme controller:**
```javascript
function resolveTheme() {
    var override = localStorage.getItem("hsr.theme");
    if (override === "light" || override === "dark") return override;
    var h = new Date().getHours();
    return (h >= 6 && h < 18) ? "light" : "dark";
}

function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    document.querySelectorAll(".theme-opt").forEach(function(btn) {
        var val = btn.dataset.themeVal;
        var isActive = (val === "auto" && !localStorage.getItem("hsr.theme"))
            || val === localStorage.getItem("hsr.theme");
        btn.setAttribute("aria-checked", isActive ? "true" : "false");
    });
}
```

Theme toggle click handler:
```javascript
document.querySelectorAll(".theme-opt").forEach(function(btn) {
    btn.addEventListener("click", function() {
        var val = btn.dataset.themeVal;
        if (val === "auto") {
            localStorage.removeItem("hsr.theme");
            applyTheme(resolveTheme());
        } else {
            localStorage.setItem("hsr.theme", val);
            applyTheme(val);
        }
    });
});
```

Mid-session toast timer — check every 60 seconds if the hour crossed the 6am/6pm boundary:
```javascript
setInterval(function() {
    if (localStorage.getItem("hsr.theme")) return; // user set explicit override
    var dismissed = localStorage.getItem("hsr.theme_prompt_dismissed_until");
    if (dismissed && new Date(dismissed) > new Date()) return;
    var current = document.documentElement.getAttribute("data-theme");
    var resolved = resolveTheme();
    if (current !== resolved) {
        var msg = resolved === "dark" ? "Evening. Switch to dark theme?" : "Morning. Switch to light theme?";
        showThemeToast(msg, resolved);
    }
}, 60000);
```

**3. Verse of the Day** — 30 curated entries:
```javascript
var VERSES_OF_DAY = [
    { dev: "\u0915\u0930\u094D\u092E\u0923\u094D\u092F\u0947\u0935\u093E\u0927\u093F\u0915\u093E\u0930\u0938\u094D\u0924\u0947 \u092E\u093E \u092B\u0932\u0947\u0937\u0941 \u0915\u0926\u093E\u091A\u0928", iast: "karma\u1E47y ev\u0101dhik\u0101ras te m\u0101 phale\u1E63u kad\u0101cana", eng: "You have a right to action alone, never to its fruits.", ref: "Bhagavad G\u012Bt\u0101 \u00B7 2.47" },
    // ... 29 more entries to be curated from the known corpus
];
var dayOfYear = Math.floor((Date.now() - new Date(new Date().getFullYear(),0,0)) / 86400000);
var todayVerse = VERSES_OF_DAY[dayOfYear % VERSES_OF_DAY.length];
```

Populate the welcome tablet:
```javascript
document.getElementById("vodDev").textContent = todayVerse.dev;
document.getElementById("vodIast").textContent = todayVerse.iast;
document.getElementById("vodEng").textContent = todayVerse.eng;
document.getElementById("vodRef").textContent = todayVerse.ref;
```

**4. Drawer controller** — open/close with scrim, focus trap:
```javascript
function openDrawer() {
    drawer.hidden = false;
    drawerScrim.hidden = false;
    document.body.style.overflow = "hidden";
    renderThreadList();
    trapFocus(drawer);
}
function closeDrawer() {
    drawer.hidden = true;
    drawerScrim.hidden = true;
    document.body.style.overflow = "";
    drawerToggle.focus();
}
```

**5. Voice menu** — popover toggle:
```javascript
voicePill.addEventListener("click", function() {
    voiceMenu.hidden = !voiceMenu.hidden;
});
document.querySelectorAll(".voice-option").forEach(function(btn) {
    btn.addEventListener("click", function() {
        var key = btn.dataset.voice;
        localStorage.setItem("hsr.voice", key);
        voicePillLabel.textContent = btn.querySelector("strong").textContent;
        voiceMenu.hidden = true;
    });
});
```

**6. Markdown renderer** — same logic as current but with `[[verse]]` block support. After the main parse, call `processVerseBlocks(contentEl)` which finds `[[verse]]...[[/verse]]` markers and replaces them with `.verse-tablet` figure elements using safe DOM construction (createElement, textContent assignments).

**7. Streaming engine** — the key performance fix:
- During streaming: append raw text to a `<pre class="stream-buffer">` using `textContent += chunk` (no HTML parsing)
- On `done`: hide buffer, parse full answer once, build DOM tree using a `<template>` element, append to content div, then call `processVerseBlocks()`

**8. Answer footer** — render after `citations` and `followups` events arrive:
- Action row: Copy, Share, Deeper, Simpler buttons
- Citations strip: SOURCES label + chip spans
- Follow-ups: CONTINUE label + clickable italic lines

Action handlers:
- Copy: `navigator.clipboard.writeText(answerText)`
- Share: `navigator.share()` with fallback to clipboard
- Deeper: prepend `[[depth:deeper]] ` to question and re-send
- Simpler: prepend `[[depth:simpler]] ` to question and re-send

**9. Thread persistence** (localStorage):
```javascript
function generateThreadId() { return crypto.randomUUID(); }
function loadThreads() { try { return JSON.parse(localStorage.getItem("hsr.threads") || "[]"); } catch(e) { return []; } }
function saveThreads(threads) { localStorage.setItem("hsr.threads", JSON.stringify(threads)); }
function loadMessages(id) { try { return JSON.parse(localStorage.getItem("hsr.thread." + id) || "[]"); } catch(e) { return []; } }
function saveMessages(id, msgs) {
    try { localStorage.setItem("hsr.thread." + id, JSON.stringify(msgs)); }
    catch(e) { pruneOldThreads(); try { localStorage.setItem("hsr.thread." + id, JSON.stringify(msgs)); } catch(e2) { showToast("Storage full."); } }
}
```

**10. Send message** — includes voice param:
```javascript
var payload = {
    question: text,
    history: conversationHistory,
    voice: localStorage.getItem("hsr.voice") || "elder",
};
```

**11. Keyboard shortcuts:**
```javascript
document.addEventListener("keydown", function(e) {
    if (e.key === "Escape") { closeDrawer(); voiceMenu.hidden = true; }
    if (e.key === "/" && document.activeElement !== chatInput && document.activeElement.tagName !== "TEXTAREA") {
        e.preventDefault(); chatInput.focus();
    }
});
```

**12. Service Worker registration:**
```javascript
if ("serviceWorker" in navigator) {
    window.addEventListener("load", function() {
        navigator.serviceWorker.register("/static/sw.js").catch(function() {});
    });
}
```

**13. Focus trap utility:**
```javascript
function trapFocus(container) {
    var focusable = container.querySelectorAll("button, [href], input, select, textarea, [tabindex]:not([tabindex=\"-1\"])");
    if (!focusable.length) return;
    var first = focusable[0];
    var last = focusable[focusable.length - 1];
    first.focus();
    container.addEventListener("keydown", function(e) {
        if (e.key !== "Tab") return;
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    });
}
```

**14. Scroll debouncing:**
```javascript
var _scrollRAF = 0;
function scheduleScroll() {
    if (_scrollRAF) return;
    _scrollRAF = requestAnimationFrame(function() {
        _scrollRAF = 0;
        var el = chatMessages;
        if (el.scrollHeight - el.scrollTop - el.clientHeight < 150) {
            el.scrollTop = el.scrollHeight;
        }
    });
}
```

- [ ] **Step 2: Verify in browser**

Run: `cd /Users/sanjeevkathiravan/hindu-scriptures-rag/scripts/rag && python app.py`
Open `http://localhost:5001` and verify:
- Welcome state shows Om + verse of the day + gentle prompts
- Theme toggle switches between light/dark/auto
- Drawer opens/closes, focus trap works
- Voice menu shows 5 options, selection persists
- Sending a message streams with append-only buffer
- Answer footer appears with actions, citations, followups
- Thread persists on reload

- [ ] **Step 3: Commit**

```bash
cd /Users/sanjeevkathiravan/hindu-scriptures-rag
git add scripts/rag/static/js/app.js
git commit -m "feat: rewrite JS with theme controller, drawer, voice menu, streaming fix, persistence"
```

---

## Task 9: PWA — Manifest & Service Worker

**Files:**
- Create: `scripts/rag/static/manifest.json`
- Create: `scripts/rag/static/sw.js`

- [ ] **Step 1: Create the PWA manifest**

Create `scripts/rag/static/manifest.json`:

```json
{
    "name": "Hindu Scriptures",
    "short_name": "Scriptures",
    "start_url": "/",
    "display": "standalone",
    "background_color": "#1F0808",
    "theme_color": "#3D0C0C",
    "icons": [
        {
            "src": "/static/icons/om-192.png",
            "sizes": "192x192",
            "type": "image/png",
            "purpose": "any maskable"
        },
        {
            "src": "/static/icons/om-512.png",
            "sizes": "512x512",
            "type": "image/png",
            "purpose": "any maskable"
        }
    ]
}
```

- [ ] **Step 2: Create the service worker**

Create `scripts/rag/static/sw.js`:

```javascript
var CACHE_KEY = "hsr-shell-v1";
var SHELL_URLS = [
    "/",
    "/static/css/style.css",
    "/static/js/app.js",
    "/static/manifest.json"
];

self.addEventListener("install", function(event) {
    event.waitUntil(
        caches.open(CACHE_KEY).then(function(cache) {
            return cache.addAll(SHELL_URLS);
        })
    );
    self.skipWaiting();
});

self.addEventListener("activate", function(event) {
    event.waitUntil(
        caches.keys().then(function(keys) {
            return Promise.all(
                keys.filter(function(k) { return k !== CACHE_KEY; })
                    .map(function(k) { return caches.delete(k); })
            );
        })
    );
    self.clients.claim();
});

self.addEventListener("fetch", function(event) {
    var url = new URL(event.request.url);

    // Never cache API calls
    if (url.pathname.startsWith("/api/")) {
        return;
    }

    // Cache-first for shell assets
    event.respondWith(
        caches.match(event.request).then(function(cached) {
            return cached || fetch(event.request);
        })
    );
});
```

- [ ] **Step 3: Create placeholder icon directory**

```bash
mkdir -p /Users/sanjeevkathiravan/hindu-scriptures-rag/scripts/rag/static/icons
```

Note: The Om icon PNGs (192x192 and 512x512) need to be created separately. For now, the directory exists so future tasks can place icons there.

- [ ] **Step 4: Commit**

```bash
cd /Users/sanjeevkathiravan/hindu-scriptures-rag
git add scripts/rag/static/manifest.json scripts/rag/static/sw.js scripts/rag/static/icons/
git commit -m "feat: add PWA manifest and shell-cache service worker"
```

---

## Task 10: Polish — Accessibility & Performance

**Files:**
- Modify: `scripts/rag/static/css/style.css` (add reduced-motion)
- Modify: `scripts/rag/static/js/app.js` (verify focus trap, keyboard nav)

- [ ] **Step 1: Verify reduced-motion is in CSS**

Ensure this block exists at the end of `style.css`:

```css
@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
        animation-duration: 0.01ms !important;
        transition-duration: 0.01ms !important;
    }
}
```

- [ ] **Step 2: Verify WCAG AA contrast**

Check these combinations with a contrast checker tool:
- Light: `#5A3E2E` on `#FFFDF7` = ~8.5:1 (passes AA)
- Light: `#7F6B5A` on `#FFFDF7` = ~4.7:1 (passes AA)
- Dark: `#E8D5B8` on `#1F0808` = ~10:1 (passes AA)
- Dark: `#C9B892` on `#1F0808` = ~8:1 (passes AA)

- [ ] **Step 3: Verify all aria attributes in HTML**

Check that these are present in `index.html`:
- `aria-label` on all icon buttons (hamburger, send)
- `role="radiogroup"` on theme toggle, `role="radio"` + `aria-checked` on each option
- `aria-live="polite"` + `aria-atomic="false"` on chat messages area
- `aria-label` on drawer aside

- [ ] **Step 4: Commit if changes were needed**

```bash
cd /Users/sanjeevkathiravan/hindu-scriptures-rag
git add scripts/rag/static/css/style.css scripts/rag/static/js/app.js scripts/rag/templates/index.html
git commit -m "feat: accessibility polish — reduced motion, focus trap, WCAG AA contrast"
```

---

## Task 11: Run All Tests & Final Verification

- [ ] **Step 1: Run all backend tests**

```bash
cd /Users/sanjeevkathiravan/hindu-scriptures-rag
python -m pytest tests/ -v
```

Expected: All tests in `test_voices.py`, `test_citations.py`, `test_followups.py` pass.

- [ ] **Step 2: Start the server and smoke test**

```bash
cd /Users/sanjeevkathiravan/hindu-scriptures-rag/scripts/rag
source ../../venv-rag/bin/activate
python app.py
```

Manual smoke test checklist:
1. First visit during day = light theme, no override
2. Toggle to Dark = persists on reload
3. Toggle to Auto = falls back to time-of-day
4. Voice pill shows "Warm Elder" = click = popover with 5 options
5. Select "Scholarly" = pill updates = `hsr.voice` in localStorage is "scholarly"
6. Verse of the Day appears in welcome state
7. Click a gentle prompt = sends, answer streams
8. Answer footer appears: Copy, Share, Deeper, Simpler buttons
9. Citations chips appear (if answer mentions verse refs)
10. Follow-up questions appear (if Haiku generates them)
11. Click "Deeper" = re-sends same question with depth modifier
12. Open drawer = thread appears = click "+ NEW" = new empty thread
13. Reload = current thread restored with messages

- [ ] **Step 3: Final commit if any fixes were needed**

```bash
cd /Users/sanjeevkathiravan/hindu-scriptures-rag
git add -A
git commit -m "fix: address smoke test issues"
```

---

## Self-Review

1. **Spec coverage**: All 19 spec sections have corresponding tasks. Theme (section 3) = Tasks 6-8. Layout/Drawer (section 4) = Tasks 7-8. Welcome (section 5) = Tasks 7-8. Typography (section 6) = Tasks 6, 8. Footer (section 7) = Task 8. Voice (section 8) = Tasks 1, 5, 7, 8. Persistence (section 9) = Task 8. Prompt (section 10) = Task 4. Backend (section 11) = Tasks 2, 3, 5. Performance (section 12) = Task 8. Accessibility (section 13) = Task 10. PWA (section 14) = Task 9. Testing (section 15) = Tasks 1-3, 11. Error handling (section 16) = Tasks 5, 8. Rollout (section 17) = Task 11.

2. **Placeholder scan**: No TBD/TODO. The Verse of the Day needs 30 entries curated (noted with instruction in Task 8).

3. **Type consistency**: `get_voice_prompt()` signature is consistent across voices.py, test_voices.py, and app.py. `extract_refs()` is consistent across citations.py and test_citations.py. `generate_followups()` is consistent across followups.py and test_followups.py. `run_agent_stream(system_prompt=)` parameter is consistent between react_loop.py and app.py.
