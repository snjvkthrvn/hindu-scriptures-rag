"""Tool definitions for Claude tool_use API and their execution logic.

Tools:
  1. search_scriptures — semantic search with optional filters
  2. search_commentaries — search by school or acharya
  3. get_verse — retrieve a specific verse by reference
  4. compare_schools — side-by-side school interpretations for a verse
"""

import re
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import RAGConfig
from search import format_context, search, search_by_verse_id, search_with_context_expansion

# ── Source name aliases → canonical names (as in verses_enriched.json) ────

_SOURCE_ALIASES: dict[str, str] = {
    # Bhagavad Gita
    "gita": "Bhagavad Gita",
    "bhagavad gita": "Bhagavad Gita",
    "bhagavadgita": "Bhagavad Gita",
    "bg": "Bhagavad Gita",
    "srimad bhagavad gita": "Bhagavad Gita",
    "shrimad bhagavad gita": "Bhagavad Gita",
    # Mahabharata
    "mahabharata": "Mahabharata (Critical Edition)",
    "mahabharat": "Mahabharata (Critical Edition)",
    "mahabharata ce": "Mahabharata (Critical Edition)",
    "mahabharata critical edition": "Mahabharata (Critical Edition)",
    "mbh": "Mahabharata (Critical Edition)",
    "mbhce": "Mahabharata (Critical Edition)",
    # Valmiki Ramayana
    "ramayana": "Valmiki Ramayana",
    "valmiki ramayana": "Valmiki Ramayana",
    "ramayan": "Valmiki Ramayana",
    "valmiki ramayan": "Valmiki Ramayana",
    # Ramcharitmanas
    "ramcharitmanas": "Ramcharitmanas",
    "ramcharitamanas": "Ramcharitmanas",
    "ram charit manas": "Ramcharitmanas",
    "tulsidas ramayana": "Ramcharitmanas",
    "tulsi ramayana": "Ramcharitmanas",
    "rcm": "Ramcharitmanas",
    # Rigveda
    "rigveda": "Rigveda",
    "rig veda": "Rigveda",
    "rv": "Rigveda",
    # Atharvaveda
    "atharvaveda": "Atharvaveda",
    "atharva veda": "Atharvaveda",
    "av": "Atharvaveda",
    # Yajurveda
    "yajurveda": "Yajurveda",
    "yajur veda": "Yajurveda",
    "yv": "Yajurveda",
    # Upanishads
    "isha upanishad": "Isha Upanishad",
    "ishopanishad": "Isha Upanishad",
    "isavasya upanishad": "Isha Upanishad",
    "kena upanishad": "Kena Upanishad",
    "kenopanishad": "Kena Upanishad",
    "katha upanishad": "Katha Upanishad",
    "kathopanishad": "Katha Upanishad",
    "prashna upanishad": "Prashna Upanishad",
    "prashnopanishad": "Prashna Upanishad",
    "mundaka upanishad": "Mundaka Upanishad",
    "mundakopanishad": "Mundaka Upanishad",
    "mandukya upanishad": "Mandukya Upanishad",
    "mandukyopanishad": "Mandukya Upanishad",
    "taittiriya upanishad": "Taittiriya Upanishad",
    "taittiriyopanishad": "Taittiriya Upanishad",
    "aitareya upanishad": "Aitareya Upanishad",
    "aitareyopanishad": "Aitareya Upanishad",
    "brihadaranyaka upanishad": "Brihadaranyaka Upanishad",
    "brihadaranyakopanishad": "Brihadaranyaka Upanishad",
    "brihad upanishad": "Brihadaranyaka Upanishad",
    "svetasvatara upanishad": "Svetasvatara Upanishad",
    "shvetashvatara upanishad": "Svetasvatara Upanishad",
    "svetashvatara upanishad": "Svetasvatara Upanishad",
}


def normalize_source_text(source_text: str) -> str:
    """Map common source name variants to the canonical name used in the index.

    Returns the canonical name if a match is found, otherwise returns the
    original string unchanged (Qdrant will just find no matches).
    """
    if not source_text:
        return source_text
    key = source_text.strip().lower()
    return _SOURCE_ALIASES.get(key, source_text)


# ── Claude tool_use schema definitions ────────────────────────────────────

TOOL_DEFINITIONS = [
    {
        "name": "search_scriptures",
        "description": (
            "Search Hindu scripture verses using semantic + keyword hybrid search. "
            "Returns relevant verses with Sanskrit, transliteration, and translation. "
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
                    "description": "Filter by scripture name (e.g., 'Bhagavad Gita', 'Valmiki Ramayana', 'Rigveda'). Leave empty to search all.",
                },
                "category": {
                    "type": "string",
                    "enum": ["shruti", "smriti", "itihasa", ""],
                    "description": "Filter by category. shruti=Vedas/Upanishads, smriti=Gita/Ramcharitmanas, itihasa=epics.",
                },
                "tradition": {
                    "type": "string",
                    "description": "Filter by tradition (vedic, vedanta, bhakti, common). Leave empty for all.",
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
            "Covers commentaries across multiple texts (Bhagavad Gita, Upanishads, etc.)."
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
                        "'RV 1.1.1' (Rigveda), 'AV 1.1.1' (Atharvaveda), 'YV 1.1' (Yajurveda), "
                        "'VR 1.1.1' (Valmiki Ramayana), "
                        "'MBhCE 1.1.1' (Mahabharata Critical Edition), "
                        "'RCM 1.1' (Ramcharitmanas), "
                        "'Katha Up 1.2.12', 'Isha Up 1', 'Mundaka Up 1.2.3', "
                        "'Brihad Up 1.2.3', 'Svetasvatara Up 1.1', etc. for Upanishads."
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
                        "'RV 1.1.1' (Rigveda), 'VR 1.1.1' (Valmiki Ramayana), "
                        "'MBhCE 1.1.1' (Mahabharata Critical Edition)."
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
            "'What happened when Yajnavalkya debated Gargi?', "
            "'Describe the dialogue between Uddalaka and Shvetaketu')."
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
                        "Filter by scripture name (e.g., 'Katha Upanishad', "
                        "'Brihadaranyaka Upanishad', 'Bhagavad Gita'). "
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

    Supports all texts in the corpus:
      BG 2.47, RV 1.1.1, AV 1.1.1, YV 1.1, VR 1.1.1, MBhCE 1.1.1,
      RCM 1.1, Isha Up 1, Kena Up 1.1, Katha Up 1.2.12, etc.
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

    # AV 1.1.1 → av_1_1_1 (Atharvaveda)
    m = re.match(r"AV\s+(\d+)\.(\d+)\.(\d+)", ref, re.IGNORECASE)
    if m:
        return f"av_{m.group(1)}_{m.group(2)}_{m.group(3)}"

    # YV 1.1 → yv_1_1 (Yajurveda)
    m = re.match(r"YV\s+(\d+)\.(\d+)", ref, re.IGNORECASE)
    if m:
        return f"yv_{m.group(1)}_{m.group(2)}"

    # VR 1.1.1 → vr_1_1_1 (Valmiki Ramayana)
    m = re.match(r"VR\s+(\d+)\.(\d+)\.(\d+)", ref, re.IGNORECASE)
    if m:
        return f"vr_{m.group(1)}_{m.group(2)}_{m.group(3)}"

    # MBhCE 1.1.1 or MBh 1.1.1 → mbhce_1_1_1 (Mahabharata Critical Edition)
    m = re.match(r"MBh(?:CE)?\s+(\d+)\.(\d+)\.(\d+)", ref, re.IGNORECASE)
    if m:
        return f"mbhce_{m.group(1)}_{m.group(2)}_{m.group(3)}"

    # RCM 1.1 → rcm_1_1 (Ramcharitmanas)
    m = re.match(r"RCM\s+(\d+)\.(\d+)", ref, re.IGNORECASE)
    if m:
        return f"rcm_{m.group(1)}_{m.group(2)}"

    # --- Upanishads ---
    # Generic pattern: "XYZ Upanishad 1.2.3" or "XYZ Up 1.2.3" or "XYZ Up. 1.2"
    # Isha Upanishad (single numbering: verse N)
    m = re.match(r"Isha\s+(?:Up(?:anishad)?\.?\s+)?(\d+)", ref, re.IGNORECASE)
    if m:
        return f"isha_{m.group(1)}"

    # Kena Upanishad (section.verse)
    m = re.match(r"Kena\s+(?:Up(?:anishad)?\.?\s+)?(\d+)\.(\d+)", ref, re.IGNORECASE)
    if m:
        return f"kena_{m.group(1)}_{m.group(2)}"

    # Katha Upanishad (valli.section.verse or section.verse)
    m = re.match(r"Katha\s+(?:Up(?:anishad)?\.?\s+)?(\d+)\.(\d+)\.(\d+)", ref, re.IGNORECASE)
    if m:
        return f"katha_{m.group(1)}_{m.group(2)}_{m.group(3)}"
    m = re.match(r"Katha\s+(?:Up(?:anishad)?\.?\s+)?(\d+)\.(\d+)", ref, re.IGNORECASE)
    if m:
        return f"katha_{m.group(1)}_{m.group(2)}"

    # Prashna Upanishad (prashna.verse)
    m = re.match(r"Prashna\s+(?:Up(?:anishad)?\.?\s+)?(\d+)\.(\d+)", ref, re.IGNORECASE)
    if m:
        return f"prashna_{m.group(1)}_{m.group(2)}"

    # Mundaka Upanishad (mundaka.section.verse)
    m = re.match(r"Mundaka\s+(?:Up(?:anishad)?\.?\s+)?(\d+)\.(\d+)\.(\d+)", ref, re.IGNORECASE)
    if m:
        return f"mundaka_{m.group(1)}_{m.group(2)}_{m.group(3)}"
    m = re.match(r"Mundaka\s+(?:Up(?:anishad)?\.?\s+)?(\d+)\.(\d+)", ref, re.IGNORECASE)
    if m:
        return f"mundaka_{m.group(1)}_{m.group(2)}"

    # Mandukya Upanishad (verse)
    m = re.match(r"Mandukya\s+(?:Up(?:anishad)?\.?\s+)?(\d+)", ref, re.IGNORECASE)
    if m:
        return f"mandukya_{m.group(1)}"

    # Taittiriya Upanishad (valli.anuvaka)
    m = re.match(r"Taittiriya\s+(?:Up(?:anishad)?\.?\s+)?(\d+)\.(\d+)", ref, re.IGNORECASE)
    if m:
        return f"taittiriya_{m.group(1)}_{m.group(2)}"

    # Aitareya Upanishad (section.verse)
    m = re.match(r"Aitareya\s+(?:Up(?:anishad)?\.?\s+)?(\d+)\.(\d+)", ref, re.IGNORECASE)
    if m:
        return f"aitareya_{m.group(1)}_{m.group(2)}"

    # Brihadaranyaka Upanishad (adhyaya.brahmana.verse)
    m = re.match(
        r"Bri?had(?:aranyaka)?\s+(?:Up(?:anishad)?\.?\s+)?(\d+)\.(\d+)\.(\d+)", ref, re.IGNORECASE
    )
    if m:
        return f"brihad_{m.group(1)}_{m.group(2)}_{m.group(3)}"
    m = re.match(
        r"Bri?had(?:aranyaka)?\s+(?:Up(?:anishad)?\.?\s+)?(\d+)\.(\d+)", ref, re.IGNORECASE
    )
    if m:
        return f"brihad_{m.group(1)}_{m.group(2)}"

    # Svetasvatara Upanishad (chapter.verse)
    m = re.match(r"Sveta?s?vatara\s+(?:Up(?:anishad)?\.?\s+)?(\d+)\.(\d+)", ref, re.IGNORECASE)
    if m:
        return f"svetasvatara_{m.group(1)}_{m.group(2)}"

    # Fallback: replace dots and spaces with underscores, lowercase
    return ref.lower().replace(" ", "_").replace(".", "_")


# ── Tool execution ────────────────────────────────────────────────────────


def execute_tool(name: str, input_data: dict, config: RAGConfig) -> str:
    """Execute a tool and return the result as a string for Claude."""
    if name == "search_scriptures":
        return _exec_search_scriptures(input_data, config)
    elif name == "search_commentaries":
        return _exec_search_commentaries(input_data, config)
    elif name == "get_verse":
        return _exec_get_verse(input_data, config)
    elif name == "compare_schools":
        return _exec_compare_schools(input_data, config)
    elif name == "search_story":
        return _exec_search_story(input_data, config)
    else:
        return f"Unknown tool: {name}"


def _exec_search_scriptures(input_data: dict, config: RAGConfig) -> str:
    query = input_data.get("query", "")
    if not query:
        return "Error: query is required"

    filters = {}
    if input_data.get("source_text"):
        filters["source_text"] = normalize_source_text(input_data["source_text"])
    if input_data.get("category"):
        filters["category"] = input_data["category"]
    if input_data.get("tradition"):
        filters["tradition"] = input_data["tradition"]

    # Allow caller to filter by chunk_type, but default to searching everything
    if input_data.get("chunk_type"):
        filters["chunk_type"] = input_data["chunk_type"]

    top_k = min(input_data.get("top_k", 8), 20)
    results = search(query, config=config, filters=filters, top_k=top_k)

    if not results:
        return "No verses found matching your query."

    return format_context(results)


def _exec_search_commentaries(input_data: dict, config: RAGConfig) -> str:
    query = input_data.get("query", "")
    if not query:
        return "Error: query is required"

    filters = {"chunk_type": "commentary"}
    if input_data.get("school"):
        filters["school"] = input_data["school"]
    if input_data.get("author"):
        filters["author"] = input_data["author"]

    top_k = min(input_data.get("top_k", 10), 20)
    results = search(query, config=config, filters=filters, top_k=top_k)

    if not results:
        return "No commentaries found matching your query."

    return format_context(results)


def _exec_get_verse(input_data: dict, config: RAGConfig) -> str:
    ref = input_data.get("verse_ref", "")
    if not ref:
        return "Error: verse_ref is required"

    verse_id = normalize_verse_ref(ref)
    results = search_by_verse_id(verse_id, config=config)

    if not results:
        return f"Verse '{ref}' (id: {verse_id}) not found."

    return format_context(results)


def _exec_compare_schools(input_data: dict, config: RAGConfig) -> str:
    ref = input_data.get("verse_ref", "")
    if not ref:
        return "Error: verse_ref is required"

    verse_id = normalize_verse_ref(ref)
    results = search_by_verse_id(verse_id, config=config)

    if not results:
        return f"Verse '{ref}' (id: {verse_id}) not found."

    # Separate verse from commentaries
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
        if verse_result.get("sanskrit"):
            parts.append(f"Sanskrit: {verse_result['sanskrit']}")
        if verse_result.get("transliteration"):
            parts.append(f"Transliteration: {verse_result['transliteration']}")
        if verse_result.get("translation"):
            parts.append(f"Translation: {verse_result['translation']}")

    if commentaries:
        # Group by school
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
    query = input_data.get("query", "")
    if not query:
        return "Error: query is required"

    filters = {}
    if input_data.get("source_text"):
        filters["source_text"] = normalize_source_text(input_data["source_text"])

    context_window = min(input_data.get("context_window", 10), 30)

    results = search_with_context_expansion(
        query,
        config=config,
        filters=filters,
        top_k=5,  # fewer seeds, wider expansion
        context_window=context_window,
    )

    if not results:
        return "No story passages found matching your query."

    # Format with section headers to show contiguous blocks
    parts = []
    prev_source = None
    prev_chapter = None
    for _i, r in enumerate(results, 1):
        source = r.get("source_text", "")
        chapter = r.get("chapter")

        # Insert a section header when source or chapter changes
        if source != prev_source or chapter != prev_chapter:
            header = f"\n=== {source}"
            if r.get("chapter_name"):
                header += f" — {r['chapter_name']}"
            if chapter:
                header += f" (Chapter {chapter})"
            header += " ==="
            parts.append(header)
            prev_source = source
            prev_chapter = chapter

        # Format the verse
        verse_num = r.get("verse_num", "")
        lines = [f"Verse {verse_num}:"]
        if r.get("sanskrit"):
            lines.append(f"  Sanskrit: {r['sanskrit']}")
        if r.get("transliteration"):
            lines.append(f"  Transliteration: {r['transliteration']}")
        if r.get("translation"):
            lines.append(f"  Translation: {r['translation']}")
        parts.append("\n".join(lines))

    return "\n\n".join(parts)
