# Frontend UX Redesign & Prompt Rewrite — Design Doc

**Date:** 2026-04-09
**Status:** Approved, ready for implementation planning
**Scope:** Substantial redesign of the web UI, streaming pipeline, persistence layer, and the agent system prompt for the Hindu Scriptures RAG app.

---

## 1. Goals & Non-Goals

### Goals

1. Replace the current "chatbot chrome" aesthetic with a **Sacred Interface + Reading Companion** mood — calm, literary, manuscript-inspired — without becoming decorative or precious.
2. Make the app **time-of-day aware**: light theme during the day, dark theme (Temple Ember) at night, with a user-overridable 3-state toggle.
3. Treat Sanskrit verses as **first-class typography**, not decoration. The "Inscribed Tablet" component gives every quoted verse ref + Devanagari + IAST + English.
4. Ship a **user-customizable voice system** (5 presets) so the same retrieval pipeline can speak in different registers — Warm Elder (default), Traditional Guru, Plainspoken Friend, Scholarly, Poetic.
5. **Rewrite the LLM system prompt** comprehensively across nine improvement directions — research protocol, Sanskrit discipline, question-type routing, length discipline, commentarial voice, etc.
6. Add **threaded conversation persistence** (localStorage), an overlay history drawer, per-answer copy/share/deeper/simpler actions, citations, and follow-up question suggestions.
7. Fix the known **streaming re-render performance bug** (O(n²) markdown re-parse on every SSE chunk).
8. Improve **accessibility** (WCAG AA contrast, keyboard nav, screen-reader support for streaming).
9. Add a minimal **PWA shell** (installable, offline shell cache — not offline answers).

### Non-Goals

- No framework migration. Stays vanilla HTML/CSS/JS served from Flask.
- No new backend model beyond what already ships (Claude + Cohere + Qdrant).
- No account system. All state is client-side.
- No multi-language UI (English only; scriptures remain multilingual).
- No real-time collaboration.
- No offline RAG. Only the app shell is cached.

---

## 2. High-Level Architecture

Three-file frontend stays three files. Backend grows two small Python modules and one new data file.

```
scripts/rag/
  templates/index.html          ← restructured; drawer, toast, voice menu, welcome
  static/css/style.css          ← rewritten around a token system with [data-theme]
  static/js/app.js              ← rewritten around a small controller/render loop
  static/manifest.json          ← NEW: PWA manifest
  static/sw.js                  ← NEW: shell-cache service worker
  static/icons/                 ← NEW: maskable Om icons (192, 512)
  voices.py                     ← NEW: 5 voice preset dict
  prompt_templates.py           ← rewritten AGENT_SYSTEM_PROMPT
  agent/citations.py            ← NEW: extract_refs() regex module
  agent/followups.py            ← NEW: Haiku-based follow-up generator
  app.py                        ← extended: voice param, two new SSE events
```

### Data flow for a single question

1. User types or clicks a prompt → JS calls `POST /api/agent/stream` with `{question, voice, thread_id}`.
2. Server builds system prompt by interpolating `VOICES[voice_key].prompt` into `AGENT_SYSTEM_PROMPT`.
3. Agent loop runs tool calls and streams `token` events via SSE.
4. Client appends tokens to an in-memory answer buffer and incrementally renders — no full re-parse per chunk.
5. On `done`, server runs `extract_refs(answer_text)` and emits a `citations` event.
6. Server then asks Haiku for 3 follow-up questions, emits a `followups` event, then closes.
7. Client persists the full message (question + answer + citations + followups + voice + timestamp) to `localStorage` under the current thread id.

---

## 3. Theme System

### Tokens

All color, spacing, and typography values live in CSS custom properties on `:root`, with `[data-theme="light"]` and `[data-theme="dark"]` overriding the color tokens only.

**Shared tokens** (same in both themes): spacing scale, font stacks, border radii, transition durations.

**Light theme (Manuscript Parchment):**

```
--bg-app: #FFFDF7
--bg-surface: #FBF3DC
--bg-bubble: #FFFFFF
--fg-primary: #2D1810
--fg-secondary: #5A3E2E        /* bumped from #7A5C4F for WCAG AA */
--fg-muted: #7F6B5A             /* bumped from #A08878 */
--accent: #E8820C               /* saffron */
--accent-2: #D4A843             /* temple gold */
--accent-deep: #6B1D1D          /* maroon */
--border: rgba(107, 29, 29, 0.18)
--border-strong: rgba(107, 29, 29, 0.35)
```

**Dark theme (Temple Ember):**

```
--bg-app: #1F0808
--bg-surface: #2A0F0F
--bg-bubble: rgba(107, 29, 29, 0.18)
--fg-primary: #E8D5B8
--fg-secondary: #C9B892
--fg-muted: #8B7B66
--accent: #E8820C
--accent-2: #D4A843
--accent-deep: #6B1D1D
--border: rgba(212, 168, 67, 0.22)
--border-strong: rgba(212, 168, 67, 0.4)
--glow-orange: rgba(232, 130, 12, 0.22)
--glow-gold: rgba(212, 168, 67, 0.12)
```

Devanagari text gets `text-shadow: 0 0 16px rgba(232, 130, 12, 0.35)` in dark mode only.

Ambient radial gradients are drawn via `body::before` / `body::after` with `pointer-events: none` and `position: fixed` — top-right orange glow, bottom-left gold glow. Only applied when `[data-theme="dark"]`.

### Resolution

Runs **before first paint** to avoid flash. An inline `<script>` at the top of `<head>`:

```javascript
(function(){
  var override = localStorage.getItem('hsr.theme');
  var theme;
  if (override === 'light' || override === 'dark') {
    theme = override;
  } else {
    var h = new Date().getHours();
    theme = (h >= 6 && h < 18) ? 'light' : 'dark';
  }
  document.documentElement.setAttribute('data-theme', theme);
})();
```

- 6am–6pm local → light
- 6pm–6am local → dark
- Explicit override in `localStorage.hsr.theme` wins

### Toggle

Three-state pill in the header: **Light · Auto · Dark**.

- Clicking Light or Dark writes `hsr.theme = 'light'|'dark'`.
- Clicking Auto removes `hsr.theme` (falls back to time-of-day).
- Toggle updates `[data-theme]` immediately with a 240ms crossfade on `background-color` and `color`.

### Mid-session prompt

If the user has the app open across the 6pm transition (or 6am), and has not set an explicit override, a gentle toast appears **once per transition**:

> "Evening. Switch to the dark theme? [Switch] [Not now]"

- "Switch" → sets theme, dismisses toast.
- "Not now" → sets `hsr.theme_prompt_dismissed_until` to the next transition time (~12 hours ahead).
- Toast auto-dismisses after 12 seconds if ignored.

Toast has `role="status"` and `aria-live="polite"`. Non-interruptive.

---

## 4. Layout — Overlay Drawer

Header is a slim bar (48px) containing, left to right:

- Hamburger button (opens drawer)
- Om glyph + "HINDU SCRIPTURES" wordmark + "सत्यमेव जयते" italic subtitle
- Flex spacer
- "118K verses · 9 texts" quiet pill (desktop only, hidden < 640px)
- Voice pill (shows current voice, opens voice menu)
- Theme toggle (Light · Auto · Dark)

**History drawer** slides in from the left over a scrim (`rgba(0,0,0,0.4)`). 280px wide on desktop, 85vw on mobile. Content is the **Minimalist Ribbon** style:

- Top: "+ NEW" link
- Then a vertical list of thread titles, each with a thin top rule separator
- Title: first user question, truncated to ~48 chars
- Underneath title: muted relative time ("2h ago", "yesterday")
- Current thread has a saffron left-border indicator
- No avatars, no icons, no preview text — just titles

**Closing**: click scrim, press Escape, or click hamburger again. Drawer uses focus trap while open. Body scroll locked.

**Main area** below the header:

- Empty state OR message list
- Sticky input bar at bottom (bubble-styled with saffron send button)

---

## 5. Welcome / Empty State — Hybrid

Combines Verse of the Day + Gentle Prompts.

```
           ॐ   (large, glowing in dark; quiet in light)

        Ask the Scriptures

   ┌────────────────────────┐
   │   TODAY'S VERSE        │
   │                        │
   │   कर्मण्येवाधिकारस्ते    │
   │   मा फलेषु कदाचन         │
   │                        │
   │   ─────────✦─────────  │
   │                        │
   │   karmaṇy evādhikāras  │
   │   te mā phaleṣu        │
   │                        │
   │   You have a right to  │
   │   action alone…        │
   │                        │
   │   — BHAGAVAD GĪTĀ 2.47│
   └────────────────────────┘

            · OR ASK ·

   ─────────────────────────
   What does the Gita say about fear?
   ─────────────────────────
   Explain Brahman in the Upanishads
   ─────────────────────────
   Tell me the story of Nachiketa
   ─────────────────────────
   What is dharma?
   ─────────────────────────
```

- Verse of the Day cycles through **30 curated entries** (hand-picked from Gita, Upanishads, Rig Veda). Deterministic by day-of-year for stability.
- Clicking the verse tablet primes the input with "Tell me more about this verse" but does not auto-send.
- Clicking a gentle prompt **sets** it in the input and auto-sends.
- Prompts are italic serif separated by thin rules — not pill buttons. They read like margin notes.

---

## 6. Typography — Inscribed Tablet

Any quoted verse in an answer is rendered via a shared `.verse-tablet` component. The agent writer is instructed (in the system prompt) to emit a specific marker; the frontend parses it and replaces with the tablet component.

**Markup:**

```html
<figure class="verse-tablet">
  <div class="verse-ref">Bhagavad Gītā · 2.47</div>
  <div class="verse-dev">कर्मण्येवाधिकारस्ते मा फलेषु कदाचन</div>
  <div class="verse-rule"><span class="verse-diamond">✦</span></div>
  <div class="verse-iast">karmaṇy evādhikāras te mā phaleṣu kadācana</div>
  <div class="verse-eng">You have a right to action alone, never to its fruits.</div>
</figure>
```

- Gradient background (subtle maroon→black in dark, cream→parchment in light)
- Gold border at 40% opacity
- Devanagari: 1.35rem (up from current 0.95rem), line-height 1.5, gold glow in dark
- IAST: italic, secondary color
- English: Georgia serif, primary color
- Ref label: uppercased, letterspaced, gold
- Thin gradient rule with centered ✦ between Dev and IAST
- Max-width 560px, centered

Body copy typography:
- Primary: Georgia serif (inherited), 16px / 1.65 line-height
- Sanskrit inline: `Noto Sans Devanagari` font family
- UI chrome: system sans

---

## 7. Answer Footer — Stacked

Below every answer bubble:

**Row 1 — Action row** (four icon + label buttons, aligned right):
- Copy (copies rendered answer as plain text)
- Share (Web Share API if available, else copy URL)
- Deeper (re-asks the same question with a `[[depth:deeper]]` prefix)
- Simpler (re-asks with `[[depth:simpler]]` prefix)

**Row 2 — Citations strip**:
Label "SOURCES" + chip list of refs extracted server-side. Each chip shows ref + source (e.g. "BG 2.47"). Clicking a chip highlights the matching verse tablet in the answer (scroll + brief pulse).

**Row 3 — Follow-ups**:
Heading "CONTINUE", then up to 3 full-sentence follow-up questions stacked vertically. Each is its own clickable italic line (same style as welcome prompts). Clicking sets the input and auto-sends as a new user turn.

All three rows are outside the answer bubble, aligned to its left edge. Separated from the bubble by 12px, from each other by 16px.

---

## 8. Voice System

### 5 voice presets (ship all)

1. **Warm Elder ★ (default)** — Friend across the kitchen table. Direct but tender. Uses "you." Explains Sanskrit gently. Doesn't preach. Most approachable for newcomers.
2. **Traditional Guru** — Satsang discourse. Formal, honorifics, dense Sanskrit terminology in parentheses, reverent. Classical register.
3. **Plainspoken Friend** — Zero jargon. Modern language first, Sanskrit explained thoroughly. For beginners or people burned out on spiritual vocabulary.
4. **Scholarly** — Precise, citation-heavy, IAST throughout, multiple commentarial schools weighed (Śaṅkara, Rāmānuja, Madhva…). For researchers.
5. **Poetic** — Lyrical, metaphor-rich, meditative. Short sentences, imagery, quote-heavy. For contemplative reading.

### Backend (`scripts/rag/voices.py`)

```python
VOICES = {
    "elder":       {"name": "Warm Elder",       "is_default": True,  "prompt": "..."},
    "guru":        {"name": "Traditional Guru", "is_default": False, "prompt": "..."},
    "plainspoken": {"name": "Plainspoken Friend","is_default": False,"prompt": "..."},
    "scholarly":   {"name": "Scholarly",        "is_default": False, "prompt": "..."},
    "poetic":      {"name": "Poetic",           "is_default": False, "prompt": "..."},
}
DEFAULT_VOICE = "elder"

def get_voice_prompt(voice_key: str | None) -> str:
    return VOICES.get(voice_key or DEFAULT_VOICE, VOICES[DEFAULT_VOICE])["prompt"]
```

Each voice's `prompt` is a ~8-12 line block describing identity, tone, sentence rhythm, honorific usage, and Sanskrit handling. This block replaces `{VOICE_BLOCK_PLACEHOLDER}` in `AGENT_SYSTEM_PROMPT`.

### Mechanical decisions

- **Placement**: Voice pill in the **header** (between verse-count pill and theme toggle). Shows "Voice: Warm Elder". Click opens a small popover menu listing all 5 voices with sample first-sentence previews. Selecting one updates `hsr.voice` and closes the menu.
- **Scope**: **Global** — one `hsr.voice` setting applies to all threads. Simpler mental model for v1. Per-thread override is explicit v2 work.
- **Customization**: **Presets only**. No free-form text box in v1. The 5 presets cover the full range of reasonable voices and there's no prompt-injection risk.

---

## 9. Conversation Persistence

All state is client-side, in `localStorage`.

### Schema

```
hsr.theme                         = 'light' | 'dark' | (absent means auto)
hsr.theme_prompt_dismissed_until  = ISO8601 timestamp (when to show next toast)
hsr.voice                         = 'elder' | 'guru' | 'plainspoken' | 'scholarly' | 'poetic'
hsr.current_thread                = <thread_uuid>
hsr.threads                       = JSON array of { id, title, updated_at }
hsr.thread.<id>                   = JSON array of messages
```

### Message shape

```json
{
  "role": "user" | "assistant",
  "text": "…",
  "citations": ["BG 2.47", "Katha Up 1.2.20"],
  "followups": ["…", "…", "…"],
  "voice": "elder",
  "ts": "2026-04-09T15:30:00Z"
}
```

### Thread lifecycle

- **New thread** created on first user message of a session, or when "+ NEW" clicked in drawer.
- **Thread id** is a UUID v4 generated client-side.
- **Title** is derived from the first user question (first 48 chars, trailing ellipsis if longer). Regenerated once after the first assistant response if the user edits the message — otherwise stable.
- **updated_at** refreshed on every new message in the thread.
- **Drawer list** sorted by `updated_at` descending.
- **Delete**: long-press (mobile) or right-click (desktop) a drawer entry → confirm → remove from `hsr.threads` and delete `hsr.thread.<id>`.

### Quota handling

localStorage is ~5MB per origin. At 2KB avg per message, that's ~2500 messages — plenty for a casual user but bounded.

- Before writing, check `JSON.stringify(messages).length`. If > 4MB total across all threads, show a toast: "Storage nearly full. Oldest threads will be pruned." Prune oldest threads until under 3MB.
- If a write still fails with `QuotaExceededError`, prune aggressively and retry once.

---

## 10. LLM System Prompt Rewrite

`AGENT_SYSTEM_PROMPT` in `prompt_templates.py` is comprehensively rewritten. The new structure has these sections, in order:

```
# Identity & Voice
{VOICE_BLOCK_PLACEHOLDER}

# Absolute Rules (never break these)
- Never invent verses, refs, translations, or commentaries.
- Never claim a passage says something it does not say.
- If retrieval returns nothing relevant, say so plainly. Do not fabricate a scriptural basis.
- Never start with "Great question" or meta-commentary about the question itself.
- Never end with "I hope this helps" or similar filler.
- Quote Sanskrit exactly as retrieved. If unsure, don't quote.
- If the user asks about non-Hindu scripture or a topic outside the corpus, say so once and stop.

# Research Protocol
Before writing the answer, you must:
1. Run search_scriptures with the user's question (or a rephrased version).
2. For questions that touch multiple texts or concepts, cross-reference:
   search at least TWO distinct angles and compare results.
3. When a passage has multiple commentaries available, read at least the
   primary commentarial voices (Śaṅkara, Rāmānuja, Madhva where relevant)
   before synthesizing.
4. If the first search is thin, rephrase and search again — up to 3 attempts.
5. Only begin writing the answer once you have retrieved enough grounding.

# Sanskrit Discipline
- Devanagari + IAST + English for any verse you quote in full.
- Inline Sanskrit terms: first mention = term + IAST in italics + parenthetical gloss.
  Subsequent mentions = just the term (or English equivalent if clearer).
- Never use IAST without the Devanagari if the Devanagari was retrieved.
- Never transliterate unfamiliar terms yourself — use what retrieval returned.

# Question-Type Routing
Classify the user's question silently, then follow the matching protocol:

- FACTUAL   → short, direct, one or two retrieved passages. No "In essence" section.
- STORY     → narrative retelling grounded in specific retrieved passages,
              keeping names and sequence faithful to the source.
- CONCEPTUAL→ structured exposition: definition → key passages → commentarial
              perspectives → practical significance.
- COMPARISON→ parallel structure: position A (sources), position B (sources),
              where they agree, where they differ.
- PRACTICAL → grounded advice that stays rooted in scripture. Don't invent
              modern self-help language; let the verses carry the weight.
- LOOKUP    → reference lookup (e.g. "what is BG 2.47"): verse tablet + brief
              contextual note. No "In essence" section.

# Length Discipline
- FACTUAL / LOOKUP: 60-150 words.
- STORY: 200-500 words depending on the story.
- CONCEPTUAL / COMPARISON: 300-600 words.
- PRACTICAL: 200-400 words.
- Depth modifier [[depth:deeper]] → 1.5x-2x the normal length; add more
  commentarial detail.
- Depth modifier [[depth:simpler]] → 0.5x-0.7x; remove Sanskrit jargon,
  shorter sentences, metaphor over technicality.

# "In Essence" Rule
- Include an "In essence" closing ONLY for CONCEPTUAL, COMPARISON, and
  PRACTICAL answers.
- Never use the literal phrase "In essence" twice in a row across answers —
  vary: "The heart of it", "What this comes down to", "Put simply",
  "The thread through all of this", etc.
- Never include "In essence" on FACTUAL, STORY, or LOOKUP answers.

# Commentarial Voice
When commentaries disagree, name the commentator and let them speak
distinctly. Don't flatten Śaṅkara's advaita reading into Rāmānuja's
viśiṣṭādvaita reading. Where they agree, you can synthesize.

# No-Answer Protocol
If retrieval genuinely returns nothing relevant after proper cross-referenced
search attempts, say so directly:
"I searched but couldn't find a passage in the scriptures I have access to
that speaks to this directly. You might try rephrasing, or asking about
[adjacent topic that did appear in results]."
Do not guess. Do not pad.

# Meta-Commentary Prohibition
Never write about your process. Never say "Let me search for that", "Based
on my research", "According to the passages I found", "As an AI". Speak as
the voice specified above would speak — directly, from the teaching itself.

# Quoting Format
When quoting a verse in full, use this exact structure (the frontend renders
it as an Inscribed Tablet):

  [[verse]]
  ref: Bhagavad Gītā 2.47
  dev: कर्मण्येवाधिकारस्ते मा फलेषु कदाचन
  iast: karmaṇy evādhikāras te mā phaleṣu kadācana
  eng: You have a right to action alone, never to its fruits.
  [[/verse]]

Only use this block for verses you actually retrieved. Never fabricate one.
Partial inline quotes can remain inline.
```

**Depth modifier injection**: When the user clicks "Deeper" or "Simpler", the frontend prepends `[[depth:deeper]] ` or `[[depth:simpler]] ` to the same question and resends. Backend passes it through transparently. The system prompt's Length Discipline section handles it.

**Voice block injection**: On each request, server replaces `{VOICE_BLOCK_PLACEHOLDER}` with `get_voice_prompt(voice_key)` before sending to Claude.

---

## 11. Backend Changes

### `app.py`

- `POST /api/agent/stream` accepts `voice` in request JSON (default `"elder"`).
- Builds system prompt per-request: `AGENT_SYSTEM_PROMPT.replace("{VOICE_BLOCK_PLACEHOLDER}", get_voice_prompt(voice))`.
- After the final `token` events and before `done`, emit two new SSE events:

  ```
  event: citations
  data: {"refs": ["BG 2.47", "Katha Up 1.2.20"]}

  event: followups
  data: {"questions": ["...", "...", "..."]}
  ```

- On any error in citation extraction or follow-up generation, emit an empty list — never block the answer.

### `agent/citations.py` (new)

```python
import re

REF_PATTERNS = [
    r'\b(BG)\s+(\d+\.\d+)\b',
    r'\b(RV|AV|YV|SV)\s+(\d+\.\d+(?:\.\d+)?)\b',
    r'\b(MBh|Ram)\s+(\d+\.\d+(?:\.\d+)?)\b',
    (r'\b(Isha|Kena|Katha|Prashna|Mundaka|Mandukya|Taittiriya|Aitareya|'
     r'Brihadaranyaka|Svetasvatara|Chandogya)\s+Up\.?\s+(\d+(?:\.\d+){0,2})\b'),
]

def extract_refs(text: str) -> list[str]:
    seen = []
    for pat in REF_PATTERNS:
        for m in re.finditer(pat, text):
            ref = f"{m.group(1)} {m.group(2)}"
            if ref not in seen:
                seen.append(ref)
    return seen
```

Dedup preserves order of first appearance. Returns empty list on no matches.

### `agent/followups.py` (new)

Uses Claude Haiku 4.5 for cheap generation.

```python
import json
from anthropic import Anthropic

FOLLOWUP_PROMPT = """Given this Q&A about Hindu scripture, suggest 3 natural
follow-up questions the reader might want to ask next. Return JSON only:
{"questions": ["...", "...", "..."]}

Question: {q}

Answer: {a}"""

def generate_followups(client: Anthropic, question: str, answer: str) -> list[str]:
    try:
        truncated = answer[:3000]
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            messages=[{
                "role": "user",
                "content": FOLLOWUP_PROMPT.format(q=question, a=truncated),
            }],
        )
        text = resp.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0]
        data = json.loads(text)
        qs = data.get("questions", [])
        return [q for q in qs if isinstance(q, str)][:3]
    except Exception:
        return []
```

Fails silently. Never blocks the main answer stream.

---

## 12. Performance Fixes

### Streaming render

**Problem**: Current code at `app.js:178` replaces the full HTML of the content element with `renderMarkdown(answerText)` on every SSE chunk. For an answer with N chunks, this is O(N²) markdown parses and full DOM wipes.

**Fix**: Two-pass rendering.

1. **During streaming**: append raw text to a hidden `<pre class="stream-buffer">` inside the bubble. Use `textContent` append only — no markdown parsing. Show a pulsing cursor after the buffer.
2. **On `done`**: hide the buffer, parse the full answer markdown **once**, replace buffer with the rendered tree. Then apply Inscribed Tablet post-processing (find `[[verse]]…[[/verse]]` blocks, replace with `<figure class="verse-tablet">`).

This avoids the O(N²) cost entirely and makes the stream feel smoother.

### Scroll

Debounce the "scroll to bottom" behavior to at most once per 100ms using `requestAnimationFrame`. Only scroll if the user is already within 150px of the bottom (respect manual scroll-up).

### Font loading

Add `<link rel="preload">` for Noto Sans Devanagari and Georgia fallback. Use `font-display: swap` to avoid FOIT.

---

## 13. Accessibility

- Light theme contrast bumps: `--fg-secondary` from `#7A5C4F` → `#5A3E2E`, `--fg-muted` from `#A08878` → `#7F6B5A`. All text now meets WCAG AA at 4.5:1 against backgrounds.
- Keyboard navigation: Tab order is header (hamburger → theme toggle → voice pill) → welcome prompts or messages → input → send.
- `Esc` closes the drawer and voice menu.
- `/` focuses the input (when not already focused).
- Drawer uses focus trap while open.
- Streaming answer container has `aria-live="polite"` + `aria-atomic="false"`. Screen readers hear updates without constant interruption.
- All icon buttons have `aria-label`.
- Theme toggle is a `<div role="radiogroup">` with three `<button role="radio">`.
- Prefers-reduced-motion: disable the toast slide-in, verse tablet glow animation, ambient radial gradient pulse.

---

## 14. PWA

### Manifest (`static/manifest.json`)

```json
{
  "name": "Hindu Scriptures",
  "short_name": "Scriptures",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#1F0808",
  "theme_color": "#3D0C0C",
  "icons": [
    { "src": "/static/icons/om-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable" },
    { "src": "/static/icons/om-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable" }
  ]
}
```

### Service worker (`static/sw.js`)

**Strategy**:
- `cache-first` for shell: `/`, `style.css`, `app.js`, `manifest.json`, fonts, icons
- `network-only` for `/api/*` — never cache API responses

Cache version key: `hsr-shell-v1`. Bump on each release to invalidate.

On activation, delete caches that don't match the current version.

Registered from `app.js` after `load` event. Registration failure is logged but non-fatal.

---

## 15. Testing Strategy

### Backend (pytest)

- `tests/test_citations.py` — 10+ cases for `extract_refs`:
  - Simple: "See BG 2.47." → `["BG 2.47"]`
  - Multiple: "BG 2.47 and Katha Up 1.2.20" → both in order
  - Dedup: "BG 2.47 ... BG 2.47" → one entry
  - Negative: "BG2.47" (no space) → no match
  - Mixed texts: Rig Veda, Mahabharata, Upanishad all in one string
- `tests/test_voices.py` — default returns elder, unknown key falls back to elder, all 5 keys return non-empty strings, prompt contains voice-specific marker.
- `tests/test_followups.py` — mock Anthropic client, assert JSON parsing, assert fallback to `[]` on bad JSON, assert truncation to 3000 chars applied.

### Frontend

- Manual smoke tests documented in a `TESTING.md`:
  - First visit during day → light theme, no override
  - First visit at night → dark theme, no override
  - Set explicit dark at noon → persists on reload
  - Cross 6pm → toast appears once
  - Dismiss toast → dismissed until next transition
  - Send message → streams, citations appear, follow-ups appear
  - Click follow-up → new user turn, same thread
  - Click "Deeper" → longer answer, same question
  - Create new thread → old thread stays in drawer, new thread selected
  - Switch voice mid-thread → next answer uses new voice
  - Reload → threads restored, current thread selected

### Accessibility

Run axe-core manually on the home page and on a sample thread. All violations must be fixed or explicitly waived with rationale.

---

## 16. Error Handling

- **Network failure on stream**: Show inline error bubble "Connection lost. [Retry]". Retry re-sends the same question in the same thread.
- **Citation extraction crash**: Log server-side, emit empty `citations` event. Don't block.
- **Follow-up generation crash**: Log server-side, emit empty `followups` event. Don't block.
- **Voice not found**: Server falls back to `elder`, logs warning.
- **localStorage write failure**: Toast "Couldn't save this thread — storage full. Older threads are being pruned." Attempt prune + retry.
- **Service worker registration failure**: Silent. App works without PWA.
- **Font loading failure**: CSS fallback chain (`Georgia, 'Times New Roman', serif`) handles it.

---

## 17. Rollout

Single feature branch. Incremental commits aligned to the implementation phases below. No feature flag — this is a redesign, not a trial. The old three files are rewritten in place.

Pre-merge checklist:
- All backend tests pass (80%+ coverage for new modules).
- Manual smoke test checklist complete.
- Lighthouse score ≥ 90 on mobile (Performance, Accessibility, Best Practices, SEO, PWA).
- axe-core clean.
- No console errors on first load.

---

## 18. Implementation Order

16 phases, roughly linear. Each phase should leave the app working.

1. **Backend: voice module** — Create `voices.py`, tests, verify 5 voices load.
2. **Backend: citation extractor** — Create `agent/citations.py`, tests.
3. **Backend: follow-up generator** — Create `agent/followups.py`, tests with mocked Anthropic.
4. **Backend: prompt rewrite** — Rewrite `AGENT_SYSTEM_PROMPT`, add voice placeholder interpolation, manual test via CLI.
5. **Backend: SSE events** — Extend `/api/agent/stream` to accept voice, emit citations + followups events, manual test with curl.
6. **Frontend: token system** — Rewrite CSS custom properties, add `[data-theme]` overrides, reload to verify no regressions.
7. **Frontend: theme resolver** — Inline head script, 3-state toggle in header, mid-session toast.
8. **Frontend: header restructure** — Slim bar, drawer toggle, verse-count pill, voice pill placeholder.
9. **Frontend: Inscribed Tablet** — `.verse-tablet` component CSS, `[[verse]]` parser in JS, test with a hardcoded answer.
10. **Frontend: streaming fix** — Append-only buffer during stream, single parse on done, verse tablet post-processing.
11. **Frontend: welcome hybrid** — Big Om, verse tablet, gentle prompts, 30 curated verse rotation.
12. **Frontend: drawer** — Overlay + scrim + Minimalist Ribbon list, focus trap, thread persistence.
13. **Frontend: answer footer** — Action row (copy/share/deeper/simpler), citations strip, follow-ups stack.
14. **Frontend: voice menu** — Popover with 5 voices, localStorage, pass `voice` on each request.
15. **Frontend: PWA** — manifest, service worker, icons, registration.
16. **Polish: accessibility + performance** — axe pass, Lighthouse, keyboard nav, reduced-motion, font preload.

---

## 19. Open Questions

None at design-doc time. All decisions resolved during brainstorming. If new questions arise during implementation, flag them in the implementation plan rather than editing this doc.

---

## Appendix A — Decision Log

| Decision | Options Considered | Chosen | Reasoning |
|---|---|---|---|
| Direction | Sacred Interface / Reading Companion / both | **Both** | User wanted full manuscript mood + reading-first structure |
| Scope | Light polish / Meaningful redesign / Full rewrite | **Meaningful redesign (B)** | Keep 3-file structure, substantial rewrite within them |
| Layout | Overlay drawer / Persistent sidebar / Top tabs | **Overlay drawer (A)** | Keeps chat area uncluttered, mobile-first |
| Verse treatment | Inline / Inscribed Tablet / Marginalia | **Inscribed Tablet (B)** | First-class Sanskrit typography |
| Dark palette | Temple Ember / Moonlit Ashram / Deep Indigo | **Temple Ember (A)** | Warmest, most manuscript-like |
| Answer footer | Stacked / Inline / Parchment Sidecar | **Stacked (A)** | Clearest hierarchy, full-sentence follow-ups outside bubble |
| History drawer | Grouped / Rich Cards / Minimalist Ribbon | **Minimalist Ribbon (C)** | Consistent with less-chrome principle |
| Welcome state | Verse of Day / Gentle Prompts / Pure Opening | **Hybrid (A+B)** | Verse greets, prompts invite |
| Theme resolver | prefers-color-scheme / time-of-day / manual only | **Time-of-day + override** | Night feels different from day for scripture reading |
| Theme toggle | 2-state / 3-state / per-thread | **3-state (Light · Auto · Dark)** | Respects user override while keeping Auto as default |
| Prompt rewrite scope | Small tweaks / 9 directions | **All 9 directions** | User wanted it "a lot better" |
| Voice system | Single voice / 3 presets / 5 presets / presets + free-form | **5 presets, no free-form** | Full range without prompt-injection risk |
| Voice control UI | Header / Drawer / Both | **Header** | Visible, one-tap, discoverable |
| Voice scope | Global / Per-thread | **Global** | Simpler mental model for v1 |
