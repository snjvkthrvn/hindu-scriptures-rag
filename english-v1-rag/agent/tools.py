"""Tool definitions for the English-only RAG agent.

Adapted from scripts/rag/agent/tools.py with English corpus source aliases,
tool descriptions, and additional verse reference patterns (YS, MBh section).
"""

from dataclasses import replace
import re
import sys
from pathlib import Path

# Add shared RAG modules to path
_rag_dir = Path(__file__).resolve().parent.parent.parent / "scripts" / "rag"
if str(_rag_dir) not in sys.path:
    sys.path.insert(0, str(_rag_dir))

from api_security import wrap_tool_result
from config import RAGConfig
from english_config import get_english_config, get_full_corpus_config
from hybrid_query import hybrid_search
from search import format_context, search_by_verse_id, search_with_context_expansion

# Hard caps on tool inputs and result size; keep parity with scripts/rag/agent/tools.py.
_MAX_QUERY_LEN = 1000
_MAX_REF_LEN = 200
_MAX_NAME_LEN = 200
_TOOL_MAX_RESULT_CHARS = 60_000

_VALID_CATEGORIES = {"shruti", "smriti", "itihasa", ""}
_VALID_SCHOOLS = {
    "advaita",
    "vishishtadvaita",
    "dvaita",
    "shuddhadvaita",
    "kashmir_shaivism",
    "common",
    "",
}


def _str_arg(input_data: dict, key: str, max_len: int) -> str:
    v = input_data.get(key)
    if v is None:
        return ""
    if not isinstance(v, str):
        v = str(v)
    return v.strip()[:max_len]


def _int_arg(input_data: dict, key: str, default: int, lo: int, hi: int) -> int:
    v = input_data.get(key, default)
    try:
        n = int(v)
    except (ValueError, TypeError):
        return default
    return max(lo, min(n, hi))


def _truncate_for_model(text: str) -> str:
    if not text:
        return text
    if len(text) <= _TOOL_MAX_RESULT_CHARS:
        return text
    return text[:_TOOL_MAX_RESULT_CHARS] + "\n[...truncated...]"

# ── Source name aliases → canonical names (as in verses_english_only.json) ──

_SOURCE_ALIASES: dict[str, str] = {
    # Bhagavad Gita (standard translation)
    "gita": "Bhagavad Gita",
    "bhagavad gita": "Bhagavad Gita",
    "bhagavadgita": "Bhagavad Gita",
    "bg": "Bhagavad Gita",
    "srimad bhagavad gita": "Bhagavad Gita",
    # Bhagavad Gita (Arnold translation)
    "arnold gita": "Bhagavad Gita (Arnold)",
    "song celestial": "Bhagavad Gita (Arnold)",
    "edwin arnold gita": "Bhagavad Gita (Arnold)",
    "bg arnold": "Bhagavad Gita (Arnold)",
    # Mahabharata (Ganguli)
    "mahabharata": "Mahabharata",
    "mahabharat": "Mahabharata",
    "mbh": "Mahabharata",
    "ganguli mahabharata": "Mahabharata",
    # Ramayana
    "ramayana": "Ramayana",
    "ramayan": "Ramayana",
    "valmiki ramayana": "Ramayana",
    # Rigveda
    "rigveda": "Rig Veda",
    "rig veda": "Rig Veda",
    "rv": "Rig Veda",
    # Yoga Sutras
    "yoga sutras": "Yoga Sutras of Patanjali",
    "yoga sutra": "Yoga Sutras of Patanjali",
    "patanjali": "Yoga Sutras of Patanjali",
    "ys": "Yoga Sutras of Patanjali",
    # Upanishads (Mueller translations)
    "isha upanishad": "Isha Upanishad",
    "ishopanishad": "Isha Upanishad",
    "mundaka upanishad": "Mundaka Upanishad",
    "mundakopanishad": "Mundaka Upanishad",
    # Upanishads (Claude translations)
    "kena upanishad": "Kena Upanishad (Claude)",
    "kenopanishad": "Kena Upanishad (Claude)",
    "katha upanishad": "Katha Upanishad (Claude)",
    "kathopanishad": "Katha Upanishad (Claude)",
    "prashna upanishad": "Prashna Upanishad (Claude)",
    "prashnopanishad": "Prashna Upanishad (Claude)",
    "mandukya upanishad": "Mandukya Upanishad (Claude)",
    "mandukyopanishad": "Mandukya Upanishad (Claude)",
    "taittiriya upanishad": "Taittiriya Upanishad (Claude)",
    "taittiriyopanishad": "Taittiriya Upanishad (Claude)",
    "aitareya upanishad": "Aitareya Upanishad (Claude)",
    "aitareyopanishad": "Aitareya Upanishad (Claude)",
    "brihadaranyaka upanishad": "Brihadaranyaka Upanishad (Claude)",
    "brihadaranyakopanishad": "Brihadaranyaka Upanishad (Claude)",
    "brihad upanishad": "Brihadaranyaka Upanishad (Claude)",
    "svetasvatara upanishad": "Svetasvatara Upanishad (Claude)",
    "shvetashvatara upanishad": "Svetasvatara Upanishad (Claude)",
}


def normalize_source_text(source_text: str) -> str:
    """Map common source name variants to the canonical name used in the index."""
    if not source_text:
        return source_text
    key = source_text.strip().lower()
    return _SOURCE_ALIASES.get(key, source_text)


# ── Claude tool_use schema definitions ────────────────────────────────────

TOOL_DEFINITIONS = [
    {
        "name": "search_scriptures",
        "description": (
            "Search English translations of Hindu scripture verses using semantic + keyword "
            "hybrid search. Returns relevant verses with English translations. "
            "Use this for general questions about concepts, teachings, or themes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language search query (e.g., 'concept of duty and righteous action')",
                },
                "source_text": {
                    "type": "string",
                    "description": (
                        "Filter by scripture name (e.g., 'Bhagavad Gita', 'Ramayana', "
                        "'Rigveda', 'Mahabharata', 'Yoga Sutras of Patanjali'). Leave empty to search all."
                    ),
                },
                "category": {
                    "type": "string",
                    "enum": ["shruti", "smriti", "itihasa", ""],
                    "description": "Filter by category. shruti=Vedas/Upanishads, smriti=Gita/Yoga Sutras, itihasa=epics.",
                },
                "tradition": {
                    "type": "string",
                    "description": "Filter by tradition (vedic, vedanta, bhakti, yoga, common). Leave empty for all.",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of results (default 8, max 20).",
                    "default": 8,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_commentaries",
        "description": (
            "Search commentaries on scripture verses by philosophical school or specific acharya. "
            "Returns commentary text with author attribution and school. "
            "Covers Bhagavad Gita commentaries from multiple traditions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query related to the commentary topic.",
                },
                "school": {
                    "type": "string",
                    "enum": [
                        "advaita",
                        "vishishtadvaita",
                        "dvaita",
                        "shuddhadvaita",
                        "kashmir_shaivism",
                        "common",
                        "",
                    ],
                    "description": "Filter by philosophical school.",
                },
                "author": {
                    "type": "string",
                    "description": "Filter by commentator name (e.g., 'Sri Shankaracharya', 'Sri Ramanuja').",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of results (default 10). Use higher values to see more philosophical schools.",
                    "default": 10,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_verse",
        "description": (
            "Retrieve a specific verse by its reference ID. "
            "Also returns all available commentaries for that verse. "
            "Use format like 'bg_2_47' for Bhagavad Gita 2.47, 'rv_1_1_1' for Rigveda 1.1.1, etc."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "verse_ref": {
                    "type": "string",
                    "description": (
                        "Verse reference. Supported formats: "
                        "'BG 2.47' (Bhagavad Gita), "
                        "'RV 1.1.1' (Rigveda), "
                        "'YS 1.2' (Yoga Sutras), "
                        "'MBh 42' or 'MBh Section 42' (Mahabharata section), "
                        "'Katha Up 1.2', 'Isha Up 1', 'Mundaka Up 1.2.3', "
                        "'Brihad Up 1.2.3', etc. for Upanishads."
                    ),
                },
            },
            "required": ["verse_ref"],
        },
    },
    {
        "name": "compare_schools",
        "description": (
            "For a given verse, return the verse text plus side-by-side interpretations "
            "from different philosophical schools (Advaita, Vishishtadvaita, Dvaita, etc.). "
            "Works for any verse that has commentaries indexed."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "verse_ref": {
                    "type": "string",
                    "description": (
                        "Verse reference. Examples: 'BG 2.47' (Bhagavad Gita), "
                        "'RV 1.1.1' (Rigveda)."
                    ),
                },
            },
            "required": ["verse_ref"],
        },
    },
    {
        "name": "search_story",
        "description": (
            "Search for a story, narrative, dialogue, or extended passage that spans "
            "multiple verses. Returns a contiguous block of verses around the best "
            "matches so the full narrative is preserved in reading order. "
            "Use this instead of search_scriptures when the user asks for a story, "
            "parable, or dialogue (e.g. 'Tell me the story of Nachiketa', "
            "'Describe the dialogue between Krishna and Arjuna on the battlefield')."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The story, narrative, or dialogue to search for.",
                },
                "source_text": {
                    "type": "string",
                    "description": (
                        "Filter by scripture name (e.g., 'Katha Upanishad (Claude)', "
                        "'Mahabharata', 'Bhagavad Gita'). "
                        "Leave empty to search all scriptures."
                    ),
                },
                "context_window": {
                    "type": "integer",
                    "description": (
                        "How many verses before and after each hit to include "
                        "(default 10, max 30). Increase for longer stories."
                    ),
                    "default": 10,
                },
            },
            "required": ["query"],
        },
    },
]


# ── Verse reference normalization ─────────────────────────────────────────


def normalize_verse_ref(ref: str) -> str:
    """Convert human-friendly refs like 'BG 2.47' to internal IDs like 'bg_2_47'.

    Supports all texts in the English corpus.
    """
    ref = ref.strip()

    # Already in internal format (e.g., bg_2_47)
    if re.match(r"^[a-z]+_\d+", ref):
        return ref

    # BG 2.47 → bg_2_47 (Bhagavad Gita)
    m = re.match(r"BG\s+(\d+)\.(\d+)", ref, re.IGNORECASE)
    if m:
        return f"bg_{m.group(1)}_{m.group(2)}"

    # RV 1.1.1 → rv_1_1_1 (Rigveda)
    m = re.match(r"RV\s+(\d+)\.(\d+)\.(\d+)", ref, re.IGNORECASE)
    if m:
        return f"rv_{m.group(1)}_{m.group(2)}_{m.group(3)}"

    # YS 1.2 → ys_1_2 (Yoga Sutras)
    m = re.match(r"YS\s+(\d+)\.(\d+)", ref, re.IGNORECASE)
    if m:
        return f"ys_{m.group(1)}_{m.group(2)}"

    # MBh Section N or MBh N → mbh_sN (Mahabharata section)
    m = re.match(r"MBh\s+(?:Section\s+)?(\d+)(?:\.(\d+))?", ref, re.IGNORECASE)
    if m:
        section = m.group(1)
        verse = m.group(2)
        if verse:
            return f"mbh_s{section}_v{verse}"
        return f"mbh_s{section}_v1"

    # --- Upanishads ---
    # Isha Upanishad (single numbering: verse N)
    m = re.match(r"Isha\s+(?:Up(?:anishad)?\.?\s+)?(\d+)", ref, re.IGNORECASE)
    if m:
        return f"up_isha_upanishad_{m.group(1)}"

    # Kena Upanishad (section.verse)
    m = re.match(r"Kena\s+(?:Up(?:anishad)?\.?\s+)?(\d+)\.(\d+)", ref, re.IGNORECASE)
    if m:
        return f"up_claude_kena_upanishad_{m.group(1)}"

    # Katha Upanishad (valli.section.verse or section.verse)
    m = re.match(r"Katha\s+(?:Up(?:anishad)?\.?\s+)?(\d+)\.(\d+)\.(\d+)", ref, re.IGNORECASE)
    if m:
        return f"up_claude_katha_upanishad_{m.group(1)}"
    m = re.match(r"Katha\s+(?:Up(?:anishad)?\.?\s+)?(\d+)\.(\d+)", ref, re.IGNORECASE)
    if m:
        return f"up_claude_katha_upanishad_{m.group(1)}"
    m = re.match(r"Katha\s+(?:Up(?:anishad)?\.?\s+)?(\d+)", ref, re.IGNORECASE)
    if m:
        return f"up_claude_katha_upanishad_{m.group(1)}"

    # Prashna Upanishad (prashna.verse)
    m = re.match(r"Prashna\s+(?:Up(?:anishad)?\.?\s+)?(\d+)\.(\d+)", ref, re.IGNORECASE)
    if m:
        return f"up_claude_prashna_upanishad_{m.group(1)}"

    # Mundaka Upanishad (mundaka.section.verse)
    m = re.match(r"Mundaka\s+(?:Up(?:anishad)?\.?\s+)?(\d+)\.(\d+)\.(\d+)", ref, re.IGNORECASE)
    if m:
        return f"up_mundaka_upanishad_{m.group(1)}"
    m = re.match(r"Mundaka\s+(?:Up(?:anishad)?\.?\s+)?(\d+)\.(\d+)", ref, re.IGNORECASE)
    if m:
        return f"up_mundaka_upanishad_{m.group(1)}"

    # Mandukya Upanishad (verse)
    m = re.match(r"Mandukya\s+(?:Up(?:anishad)?\.?\s+)?(\d+)", ref, re.IGNORECASE)
    if m:
        return f"up_claude_mandukya_upanishad_{m.group(1)}"

    # Taittiriya Upanishad (valli.anuvaka)
    m = re.match(r"Taittiriya\s+(?:Up(?:anishad)?\.?\s+)?(\d+)\.(\d+)", ref, re.IGNORECASE)
    if m:
        return f"up_claude_taittiriya_upanishad_{m.group(1)}"

    # Aitareya Upanishad (section.verse)
    m = re.match(r"Aitareya\s+(?:Up(?:anishad)?\.?\s+)?(\d+)\.(\d+)", ref, re.IGNORECASE)
    if m:
        return f"up_claude_aitareya_upanishad_{m.group(1)}"

    # Brihadaranyaka Upanishad (adhyaya.brahmana.verse)
    m = re.match(
        r"Bri?had(?:aranyaka)?\s+(?:Up(?:anishad)?\.?\s+)?(\d+)\.(\d+)\.(\d+)", ref, re.IGNORECASE
    )
    if m:
        return f"up_claude_brihadaranyaka_upanishad_{m.group(1)}"
    m = re.match(
        r"Bri?had(?:aranyaka)?\s+(?:Up(?:anishad)?\.?\s+)?(\d+)\.(\d+)", ref, re.IGNORECASE
    )
    if m:
        return f"up_claude_brihadaranyaka_upanishad_{m.group(1)}"

    # Svetasvatara Upanishad (chapter.verse)
    m = re.match(r"Sveta?s?vatara\s+(?:Up(?:anishad)?\.?\s+)?(\d+)\.(\d+)", ref, re.IGNORECASE)
    if m:
        return f"up_claude_svetasvatara_upanishad_{m.group(1)}"

    # Fallback: replace dots and spaces with underscores, lowercase
    return ref.lower().replace(" ", "_").replace(".", "_")


# ── Tool execution ────────────────────────────────────────────────────────


_TOOL_DISPATCH = {
    "search_scriptures": "_exec_search_scriptures",
    "search_commentaries": "_exec_search_commentaries",
    "get_verse": "_exec_get_verse",
    "compare_schools": "_exec_compare_schools",
    "search_story": "_exec_search_story",
}


def execute_tool(name: str, input_data: dict, config: RAGConfig) -> str:
    """Execute a tool and return the result wrapped as untrusted data for Claude."""
    if not isinstance(input_data, dict):
        return wrap_tool_result(name, "Error: invalid tool input")
    fn_name = _TOOL_DISPATCH.get(name)
    if fn_name is None:
        return wrap_tool_result("invalid", f"Unknown tool: {name!r}")
    raw = globals()[fn_name](input_data, config)
    return wrap_tool_result(name, _truncate_for_model(raw))


def _exec_search_scriptures(input_data: dict, config: RAGConfig) -> str:
    query = _str_arg(input_data, "query", _MAX_QUERY_LEN)
    if not query:
        return "Error: query is required"

    filters = {}
    source_text = _str_arg(input_data, "source_text", _MAX_NAME_LEN)
    if source_text:
        filters["source_text"] = normalize_source_text(source_text)
    category = _str_arg(input_data, "category", 32)
    if category:
        if category not in _VALID_CATEGORIES:
            return f"Error: invalid category {category!r}"
        filters["category"] = category
    tradition = _str_arg(input_data, "tradition", 64)
    if tradition:
        filters["tradition"] = tradition
    chunk_type = _str_arg(input_data, "chunk_type", 32)
    if chunk_type:
        filters["chunk_type"] = chunk_type

    top_k = _int_arg(input_data, "top_k", 8, 1, 20)
    english_config = replace(config or get_english_config(), top_k=top_k)
    full_config = get_full_corpus_config(config, top_k=top_k)
    results, _retrieval_mode = hybrid_search(
        query,
        english_config=english_config,
        full_config=full_config,
        filter_dict=filters or None,
    )

    if not results:
        return "No verses found matching your query."

    return format_context(results)


def _exec_search_commentaries(input_data: dict, config: RAGConfig) -> str:
    query = _str_arg(input_data, "query", _MAX_QUERY_LEN)
    if not query:
        return "Error: query is required"

    filters = {"chunk_type": "commentary"}
    school = _str_arg(input_data, "school", 64)
    if school:
        if school not in _VALID_SCHOOLS:
            return f"Error: invalid school {school!r}"
        filters["school"] = school
    author = _str_arg(input_data, "author", _MAX_NAME_LEN)
    if author:
        filters["author"] = author

    top_k = _int_arg(input_data, "top_k", 10, 1, 20)
    english_config = replace(config or get_english_config(), top_k=top_k)
    full_config = get_full_corpus_config(config, top_k=top_k)
    results, _retrieval_mode = hybrid_search(
        query,
        english_config=english_config,
        full_config=full_config,
        filter_dict=filters or None,
    )

    if not results:
        return "No commentaries found matching your query."

    return format_context(results)


def _exec_get_verse(input_data: dict, config: RAGConfig) -> str:
    ref = _str_arg(input_data, "verse_ref", _MAX_REF_LEN)
    if not ref:
        return "Error: verse_ref is required"

    verse_id = normalize_verse_ref(ref)
    results = search_by_verse_id(verse_id, config=config)

    if not results:
        return f"Verse '{ref}' (id: {verse_id}) not found."

    return format_context(results)


def _exec_compare_schools(input_data: dict, config: RAGConfig) -> str:
    ref = _str_arg(input_data, "verse_ref", _MAX_REF_LEN)
    if not ref:
        return "Error: verse_ref is required"

    verse_id = normalize_verse_ref(ref)
    results = search_by_verse_id(verse_id, config=config)

    if not results:
        return f"Verse '{ref}' (id: {verse_id}) not found."

    verse_result = None
    commentaries = []
    for r in results:
        if r["chunk_type"] == "verse":
            verse_result = r
        else:
            commentaries.append(r)

    parts = []

    if verse_result:
        parts.append(
            f"=== Verse: {verse_result['source_text']} {verse_result['chapter']}.{verse_result['verse_num']} ==="
        )
        if verse_result.get("translation"):
            parts.append(f"Translation: {verse_result['translation']}")

    if commentaries:
        by_school: dict[str, list] = {}
        for c in commentaries:
            school = c.get("school") or c.get("tradition", "common")
            by_school.setdefault(school, []).append(c)

        parts.append("\n=== Commentaries by School ===")
        for school, comms in sorted(by_school.items()):
            parts.append(f"\n--- {school.replace('_', ' ').title()} ---")
            for c in comms:
                author = c.get("author", "Unknown")
                text = c.get("commentary_text", "")[:500]
                parts.append(f"{author}: {text}")
    else:
        parts.append("\nNo commentaries found for this verse.")

    return "\n".join(parts)


def _exec_search_story(input_data: dict, config: RAGConfig) -> str:
    """Execute story search with context expansion around hits."""
    query = _str_arg(input_data, "query", _MAX_QUERY_LEN)
    if not query:
        return "Error: query is required"

    filters = {}
    source_text = _str_arg(input_data, "source_text", _MAX_NAME_LEN)
    if source_text:
        filters["source_text"] = normalize_source_text(source_text)

    context_window = _int_arg(input_data, "context_window", 10, 1, 30)

    results = search_with_context_expansion(
        query,
        config=config,
        filters=filters,
        top_k=5,
        context_window=context_window,
    )

    if not results:
        return "No story passages found matching your query."

    parts = []
    prev_source = None
    prev_chapter = None
    for _i, r in enumerate(results, 1):
        source = r.get("source_text", "")
        chapter = r.get("chapter")

        if source != prev_source or chapter != prev_chapter:
            header = f"\n=== {source}"
            if r.get("chapter_name"):
                header += f" - {r['chapter_name']}"
            if chapter:
                header += f" (Chapter {chapter})"
            header += " ==="
            parts.append(header)
            prev_source = source
            prev_chapter = chapter

        verse_num = r.get("verse_num", "")
        lines = [f"Verse {verse_num}:"]
        if r.get("translation"):
            lines.append(f"  Translation: {r['translation']}")
        parts.append("\n".join(lines))

    return "\n\n".join(parts)
