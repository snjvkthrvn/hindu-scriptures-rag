# Hindu Scripture RAG Data Pipeline

A comprehensive Python framework for downloading, parsing, and formatting Hindu scripture texts into a unified JSON format optimized for Retrieval-Augmented Generation (RAG) systems.

## Features

- **Multi-source downloading**: GitHub repos, Project Gutenberg, sacred-texts.com
- **Format parsing**: JSON, CSV, plain text, HTML
- **Unicode handling**: Devanagari normalization, ITRANS conversion
- **Verse detection**: Automatic identification of verse boundaries
- **Schema unification**: Converts diverse formats to consistent structure
- **Metadata enrichment**: Automatic theme and life domain tagging
- **Deduplication**: Identifies and merges duplicate verses across sources
- **Quality validation**: Comprehensive verse validation and reporting

## Quick Start

### 1. Install Dependencies

```bash
cd ~/hindu-scriptures-rag
pip install -r requirements.txt
```

### 2. Run Full Pipeline

```bash
python scripts/main.py run --base-dir ~/hindu-scriptures-rag
```

This will:
1. Download from GitHub, Project Gutenberg, and sacred-texts.com
2. Parse all source files
3. Normalize to unified schema
4. Enrich with metadata
5. Deduplicate verses
6. Validate output

### 3. Check Output

```bash
# View final verses
ls -lh final/

# Validate verses
python -c "
import json
with open('final/verses.json') as f:
    verses = json.load(f)
print(f'Total verses: {len(verses)}')
"
```

## Web RAG chat UI

The chat servers depend on **`requirements-rag.txt`** (Flask, Qdrant, Cohere, Anthropic, etc.). The **data pipeline** uses **`requirements.txt`** — install both if you work on ingest and the UI.

| Entrypoint | Command | Default port |
|------------|---------|--------------|
| English edition | `python english-v1-rag/app.py` | 5002 |
| Full corpus (standalone) | `python scripts/rag/app.py` | 5001 |
| English + full corpus at `/main` | `python english-v1-rag/app.py` | 5002 |

`docker compose` runs the English app on **5002** (`docker-compose.yml`). Copy **`.env.example`** to `.env` and set API keys (and optional auth variables).

### Welcome screen — Option B (verse card + prompts)

**Status:** Spec agreed (brainstorming, 2026-04-10). Implementation tracked below.

**Goal:** Add a daily curated **verse card** and two **CTAs** (“Explain this verse simply”, “How does this apply today?”) that **only prime** the input. Keep the existing **six** starter chips unchanged (they still fill the question and send). Rotate verse by **local calendar day** using `dayOfYear % N` over a JSON list (`N` ≥ 30). If JSON fails to load, hide the verse block only.

**Data:** `scripts/rag/static/data/welcome-verses.json` — array of `{ "ref", "eng", "dev"?, "iast"? }`. Copy the file to `english-v1-rag/static/data/` and update both `templates/index.html`, `static/css/style.css`, and `static/js/app.js` (the English app mirrors `scripts/rag/static`).

**Out of scope for this increment:** Thread drawer, 3-state theme, streaming/answer-footer redesign (see `.claude/plans/2026-04-09-frontend-ux-redesign-design.md`).

**Implementation checklist**

- [x] Add `welcome-verses.json` with at least 30 corpus-safe entries (`scripts/rag/static/data/` and `english-v1-rag/static/data/`).
- [x] Mark up verse region + CTAs in `scripts/rag/templates/index.html` and `english-v1-rag/templates/index.html`.
- [x] Style `.welcome-verse` / CTAs in both `style.css` copies.
- [x] In `app.js` (both copies): fetch JSON, compute index, render text, bind CTAs to prime `chatInput` only; welcome hide logic unchanged.
- [ ] Manual test: same verse same day; CTAs prime; chips auto-send; dark theme readable.

## Directory Structure

```
~/hindu-scriptures-rag/
├── raw/                          # Downloaded source files
│   ├── dharmic-data/
│   ├── indian-scriptures/
│   ├── gutenberg/
│   ├── sacred-texts/
│   └── ...
├── processed/                    # Intermediate parsed files
│   ├── tier1-essential/
│   ├── tier2-critical/
│   ├── tier3-epics/
│   ├── tier4-philosophy/
│   └── tier5-puranas/
├── final/                        # RAG-ready outputs
│   ├── verses.json               # All unified verses
│   ├── verses_enriched.json      # With metadata enrichment
│   ├── verses_deduped.json       # After deduplication
│   ├── metadata.json             # Corpus statistics
│   └── embeddings/               # For future embedding storage
└── scripts/                      # Processing scripts
    ├── main.py                   # Master orchestration
    ├── downloaders/              # Download modules
    ├── parsers/                  # Parsing modules
    ├── formatters/               # Formatting modules
    └── utils/                    # Utility functions
```

## Verse JSON Schema

```json
{
  "id": "bg_2_47",
  "source": {
    "text": "Bhagavad Gita",
    "chapter": 2,
    "chapter_name": "Sankhya Yoga",
    "verse": 47,
    "section": null
  },
  "content": {
    "sanskrit": "कर्मण्येवाधिकारस्ते मा फलेषु कदाचन।",
    "transliteration": "karmaṇy evādhikāras te mā phaleṣu kadācana",
    "translation": "You have a right to perform your prescribed duties, but you are not entitled to the fruits of your actions.",
    "word_by_word": {}
  },
  "metadata": {
    "category": "smriti",
    "tradition": "vedanta",
    "themes": ["karma_yoga", "detachment", "duty"],
    "philosophical_schools": ["advaita", "dvaita", "vishishtadvaita"],
    "life_domains": ["work", "motivation"]
  },
  "commentaries": [
    {
      "author": "Shankaracharya",
      "school": "advaita",
      "text": "..."
    }
  ],
  "provenance": {
    "download_source": "dharmic-data",
    "original_url": "https://github.com/bhavykhatri/DharmicData",
    "license": "ODbL-1.0",
    "processed_date": "2024-02-04T12:34:56"
  }
}
```

## Usage Examples

### Run Individual Commands

```bash
# Download only
python scripts/main.py download --base-dir ~/hindu-scriptures-rag

# Parse only
python scripts/main.py parse --base-dir ~/hindu-scriptures-rag

# Format and enrich
python scripts/main.py format --base-dir ~/hindu-scriptures-rag

# Validate
python scripts/main.py validate --base-dir ~/hindu-scriptures-rag
```

### Use Individual Modules

```python
from pathlib import Path
from scripts.parsers import DharmicDataParser
from scripts.formatters import MetadataEnricher

# Parse Gita from DharmicData
parser = DharmicDataParser(Path('raw/dharmic-data'))
count, verses = parser.parse_directory()

# Enrich verses
enriched = MetadataEnricher.enrich_all(verses)
```

### Download Specific Sources

```bash
# GitHub only
python scripts/downloaders/download_github.py --list
python scripts/downloaders/download_github.py

# Project Gutenberg only
python scripts/downloaders/download_gutenberg.py --list
python scripts/downloaders/download_gutenberg.py

# Sacred Texts only
python scripts/downloaders/download_sacred_texts.py --list
python scripts/downloaders/download_sacred_texts.py --delay 2.0
```

### Parse Specific Formats

```bash
# Parse CSV Upanishads
python scripts/parsers/parse_upanishad_csv.py ~/hindu-scriptures-rag/raw/indian-scriptures

# Parse text files
python scripts/parsers/parse_text_files.py input.txt --title "Text Title"

# Parse JSON files
python scripts/parsers/parse_dharmic_json.py ~/hindu-scriptures-rag/raw/dharmic-data
```

### Normalize and Enrich

```bash
# Normalize schema
python scripts/formatters/normalize_schema.py \
  --input-dir ~/hindu-scriptures-rag/processed \
  --output ~/hindu-scriptures-rag/final/verses.json

# Enrich metadata
python scripts/formatters/add_metadata.py \
  --input ~/hindu-scriptures-rag/final/verses.json

# Deduplicate
python scripts/formatters/deduplicate.py \
  --input ~/hindu-scriptures-rag/final/verses.json
```

## Text Coverage

### Tier 1: Essential (Must Have)
- Bhagavad Gita (700 verses)
- 11 Principal Upanishads
- Yoga Sutras

### Tier 2: Critical Context
- Viveka Chudamani
- Ashtavakra Gita
- Narada Bhakti Sutras

### Tier 3: Epic Wisdom
- Mahabharata (key chapters)
- Valmiki Ramayana
- Yoga Vasistha

### Tier 4: Philosophical Depth
- Brahma Sutras with Shankara Bhashya
- Panchadashi
- Tattva Bodha

### Tier 5: Puranic Wisdom
- Bhagavata Purana
- Vishnu Purana
- Shiva Purana

## Available Themes

Auto-detected themes include:
- karma_yoga, bhakti, jnana, detachment, dharma
- atman, brahman, meditation, yoga, liberation
- mind, death, rebirth, creation, god, nature, maya, vedas
- And more based on content analysis

## Available Life Domains

Verses are tagged with relevant life domains:
- work, relationships, purpose, motivation, anxiety, grief, anger, failure
- success, decision, ethics, leadership, aging, patience, forgiveness, gratitude
- mindfulness

## Validation

Check corpus validity:

```bash
python -c "
from scripts.utils import CorpusValidator
from pathlib import Path

validator = CorpusValidator()
stats = validator.validate_file(Path('final/verses.json'))
validator.print_report(stats)
"
```

## License

The processed data pipeline is provided as-is. Please respect the licenses of individual sources:
- DharmicData: ODbL-1.0
- Indian Scriptures: CC-BY-4.0
- Project Gutenberg: Public Domain
- Sacred Texts: CC-BY-3.0
- Sanskrit Documents: Various

## Next Steps

1. **Generate embeddings**: Use OpenAI text-embedding-3-large on final verses
2. **Vector database**: Ingest into Qdrant or Pinecone
3. **Hybrid search**: Build sparse (BM25) + dense (embedding) search index
4. **LLM integration**: Connect to LangGraph agent for RAG queries

## Troubleshooting

### ModuleNotFoundError
```bash
# Install dependencies
pip install -r requirements.txt

# Add scripts to Python path
export PYTHONPATH="${PYTHONPATH}:~/hindu-scriptures-rag/scripts"
```

### Git clone failures
- Check internet connection
- Verify git is installed: `git --version`
- Try manual clone: `git clone https://github.com/bhavykhatri/DharmicData.git raw/dharmic-data/`

### Unicode errors
- Ensure UTF-8 encoding: `export PYTHONLANG=en_US.UTF-8`
- Check file encoding: `file -i raw/**/*.txt`

### Memory issues with large files
- Process in smaller chunks
- Use streaming instead of loading entire files

## Performance

Typical performance on modern hardware:
- **Download**: 5-15 minutes (depends on connection)
- **Parse**: 1-5 minutes
- **Format & Normalize**: 2-10 minutes
- **Deduplicate**: 1-3 minutes
- **Validation**: < 1 minute

## Contributing

To add new sources:
1. Create new downloader in `scripts/downloaders/`
2. Create new parser in `scripts/parsers/`
3. Update `main.py` to include new source
4. Test parsing and validation

## Contact & Issues

For questions or issues:
1. Check the troubleshooting section
2. Review output logs for error messages
3. Verify source files are properly downloaded
4. Check Python version (3.8+)
