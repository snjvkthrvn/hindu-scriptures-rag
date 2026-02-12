# Hindu Scripture RAG Pipeline - Project Status

## ✅ Implementation Complete

This document provides a complete overview of the implemented Hindu Scripture RAG Data Pipeline.

---

## 📁 Project Structure

```
~/hindu-scriptures-rag/
├── README.md                    # Complete documentation
├── QUICKSTART.md               # 5-minute quick start guide
├── PROJECT_STATUS.md           # This file
├── LICENSE                     # MIT + source licenses
├── Makefile                    # Make commands for common tasks
├── setup.sh                    # Automated setup script
├── requirements.txt            # Python dependencies
├── .gitignore                  # Git ignore rules
│
├── raw/                        # Downloaded sources (created by pipeline)
│   ├── dharmic-data/           # GitHub: DharmicData repo
│   ├── indian-scriptures/      # GitHub: Upanishads CSV
│   ├── gutenberg/              # Project Gutenberg texts
│   ├── sacred-texts/           # Sacred-texts.com HTML
│   ├── gretil/                 # GRETIL Sanskrit corpus (future)
│   ├── sanskrit-documents/     # Sanskrit docs (future)
│   └── archive-org/            # Archive.org PDFs (future)
│
├── processed/                  # Parsed intermediate files
│   ├── tier1-essential/        # Gita, Upanishads
│   ├── tier2-critical/         # Yoga Sutras, Viveka Chudamani
│   ├── tier3-epics/            # Mahabharata, Ramayana
│   ├── tier4-philosophy/       # Brahma Sutras, etc.
│   └── tier5-puranas/          # Bhagavata, Vishnu, Shiva
│
├── final/                      # RAG-ready outputs
│   ├── verses.json             # Unified verse corpus
│   ├── verses_enriched.json    # With metadata enrichment
│   ├── verses_deduped.json     # Deduplicated version
│   ├── metadata.json           # Corpus statistics
│   └── embeddings/             # For future embeddings
│
├── examples/                   # Usage examples
│   └── query_verses.py         # Example query interface
│
└── scripts/                    # Processing pipeline
    ├── main.py                 # Master orchestration script
    ├── test_pipeline.py        # Test suite
    ├── validate_schema.py      # Schema validation
    │
    ├── downloaders/            # Download modules
    │   ├── __init__.py
    │   ├── download_github.py
    │   ├── download_gutenberg.py
    │   └── download_sacred_texts.py
    │
    ├── parsers/                # Parsing modules
    │   ├── __init__.py
    │   ├── parse_dharmic_json.py
    │   ├── parse_upanishad_csv.py
    │   └── parse_text_files.py
    │
    ├── formatters/             # Formatting modules
    │   ├── __init__.py
    │   ├── normalize_schema.py
    │   ├── add_metadata.py
    │   └── deduplicate.py
    │
    └── utils/                  # Utility modules
        ├── __init__.py
        ├── unicode_utils.py
        ├── verse_detector.py
        └── quality_checker.py
```

---

## 🎯 Implemented Features

### Core Pipeline

✅ **Phase 1: Downloading**
- GitHub repository cloning (DharmicData, Indian-Scriptures)
- Project Gutenberg downloads (4 key texts)
- Sacred-texts.com scraping (respectful rate limiting)
- Parallel downloading support
- Automatic retry and error handling
- Download verification

✅ **Phase 2: Parsing**
- JSON parser for DharmicData (Gita, Mahabharata, Ramayana)
- CSV parser for Upanishads (11 principal Upanishads)
- Plain text parser for Gutenberg/generic texts
- Automatic verse boundary detection
- Multi-format support (JSON, CSV, TXT, HTML)
- Unicode Devanagari normalization

✅ **Phase 3: Formatting & Normalization**
- Unified JSON schema conversion
- Required field validation
- Metadata enrichment (themes, life domains)
- Automatic theme tagging based on keywords
- Life domain mapping for practical applications
- Deduplication across sources
- Commentary extraction and association

✅ **Phase 4: Validation & Quality**
- Comprehensive schema validation
- Verse count verification
- Coverage analysis against expected counts
- Quality reporting
- Statistics generation
- Error detection and reporting

### Utility Modules

✅ **Unicode Handling**
- NFC normalization for Devanagari
- Character validation
- Diacritic removal
- ITRANS to Unicode conversion (with library support)
- Character counting and analysis

✅ **Verse Detection**
- Devanagari verse markers (॥१॥)
- Decimal verse markers (1.1, 1:1)
- Bracket markers ([1], (1))
- Automatic verse boundary detection
- Multi-format verse splitting

✅ **Quality Checking**
- Schema validation
- Sanskrit-translation alignment checking
- Missing field detection
- Corpus-wide validation
- Statistical analysis

### Tools & Scripts

✅ **Command-Line Interface**
- Main orchestration script with subcommands
- Individual downloader scripts
- Individual parser scripts
- Individual formatter scripts
- Validation script
- Test suite
- Example query interface

✅ **Automation**
- Automated setup script (setup.sh)
- Makefile with common commands
- Test suite for verification
- Quick start guide

---

## 📊 Supported Texts

### Tier 1: Essential (Fully Implemented)
- ✅ Bhagavad Gita (via DharmicData)
- ✅ 11 Principal Upanishads (via Indian-Scriptures CSV)
  - Isha, Kena, Katha, Prashna, Mundaka
  - Mandukya, Taittiriya, Aitareya
  - Chandogya, Brihadaranyaka, Svetasvatara

### Tier 2: Critical (Ready for Integration)
- ✅ Yoga Sutras (via Gutenberg)
- 🔄 Viveka Chudamani (via Sacred-Texts)
- 🔄 Ashtavakra Gita (parser ready)
- 🔄 Uddhava Gita (parser ready)

### Tier 3: Epics (Partially Implemented)
- ✅ Mahabharata chapters (via DharmicData)
- ✅ Ramayana (via DharmicData)
- 🔄 Yoga Vasistha (via Sacred-Texts)

### Tier 4-5: Philosophy & Puranas (Future)
- 🔄 Brahma Sutras with commentaries
- 🔄 Panchadashi
- 🔄 Tattva Bodha
- 🔄 Bhagavata Purana
- 🔄 Vishnu Purana
- 🔄 Shiva Purana

Legend:
- ✅ Fully implemented and tested
- 🔄 Parser ready, awaiting source download
- ⏳ Planned for future implementation

---

## 🔧 Technical Specifications

### JSON Schema

```json
{
  "id": "unique_verse_id",
  "source": {
    "text": "Source name",
    "chapter": 1,
    "chapter_name": "Chapter name",
    "verse": 1,
    "section": "Optional section"
  },
  "content": {
    "sanskrit": "Devanagari text",
    "transliteration": "IAST transliteration",
    "translation": "English translation",
    "word_by_word": {}
  },
  "metadata": {
    "category": "shruti|smriti|itihasa|purana|darshana|prakarana",
    "tradition": "vedanta|yoga|bhakti|etc",
    "themes": ["theme1", "theme2"],
    "philosophical_schools": ["advaita", "dvaita"],
    "life_domains": ["work", "relationships"]
  },
  "commentaries": [
    {
      "author": "Commentator name",
      "school": "Philosophical school",
      "text": "Commentary text"
    }
  ],
  "provenance": {
    "download_source": "source_identifier",
    "original_url": "https://...",
    "license": "License type",
    "processed_date": "ISO 8601 timestamp"
  }
}
```

### Categories

- **shruti**: Vedas, Upanishads (revealed scripture)
- **smriti**: Gita, Dharma Sutras (remembered scripture)
- **itihasa**: Mahabharata, Ramayana (epic narratives)
- **purana**: Bhagavata, Vishnu, Shiva Puranas
- **darshana**: Yoga Sutras, Brahma Sutras (philosophical systems)
- **prakarana**: Viveka Chudamani, Panchadashi (treatises)

### Themes (Auto-detected)

karma_yoga, bhakti, jnana, detachment, dharma, atman, brahman,
meditation, yoga, liberation, mind, death, rebirth, creation,
god, nature, maya, vedas

### Life Domains (Practical Applications)

work, relationships, purpose, motivation, anxiety, grief, anger,
failure, success, decision, ethics, leadership, aging, patience,
forgiveness, gratitude, mindfulness

---

## 🧪 Testing

### Test Coverage

✅ **Unit Tests**
- Unicode normalization
- Verse detection
- Schema validation
- Verse normalization
- Metadata enrichment

✅ **Integration Tests**
- Full pipeline execution
- Parser integration
- Formatter integration

✅ **Validation Tests**
- Schema compliance
- Required field presence
- Data integrity
- Coverage analysis

### Running Tests

```bash
# Run full test suite
python scripts/test_pipeline.py

# Run specific test
python scripts/test_pipeline.py --test validation

# Validate output
python scripts/validate_schema.py final/verses.json
```

---

## 📈 Performance Benchmarks

### Expected Processing Times

| Phase | Time | Notes |
|-------|------|-------|
| Download | 10-20 min | Depends on connection speed |
| Parse | 2-5 min | For Tier 1 texts |
| Format | 2-5 min | Normalization + enrichment |
| Deduplicate | 1-3 min | Depends on corpus size |
| Validate | <1 min | Quick validation |
| **Total** | **15-35 min** | For complete Tier 1 pipeline |

### Resource Requirements

- **Disk space**: 2-5 GB (varies by tier coverage)
- **Memory**: 1-2 GB peak during processing
- **Network**: Broadband recommended for downloads
- **CPU**: Any modern processor (single-threaded)

---

## 🚀 Usage Examples

### Basic Commands

```bash
# Setup
./setup.sh

# Run full pipeline
python scripts/main.py run

# Individual steps
python scripts/main.py download
python scripts/main.py parse
python scripts/main.py format
python scripts/main.py validate
```

### Using Make

```bash
make setup      # Initial setup
make test       # Run tests
make run        # Full pipeline
make validate   # Validate output
make stats      # Show statistics
```

### Querying Data

```bash
# Run examples
python examples/query_verses.py --examples

# Search for text
python examples/query_verses.py --search "karma"

# Get by theme
python examples/query_verses.py --theme "detachment"

# Get by life domain
python examples/query_verses.py --domain "work"

# Show statistics
python examples/query_verses.py --stats
```

---

## 🎓 Next Steps for RAG Integration

### 1. Generate Embeddings

```python
# Using OpenAI
import openai
import json

with open('final/verses.json') as f:
    verses = json.load(f)

for verse in verses:
    text = verse['content']['translation']
    embedding = openai.Embedding.create(
        input=text,
        model="text-embedding-3-large"
    )
    verse['embedding'] = embedding['data'][0]['embedding']

# Save with embeddings
with open('final/verses_with_embeddings.json', 'w') as f:
    json.dump(verses, f)
```

### 2. Set Up Vector Database

```python
# Using Qdrant
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

client = QdrantClient(path="./qdrant_storage")

client.create_collection(
    collection_name="hindu_scriptures",
    vectors_config=VectorParams(
        size=3072,  # text-embedding-3-large dimension
        distance=Distance.COSINE
    )
)

# Index verses
client.upsert(
    collection_name="hindu_scriptures",
    points=[
        {
            "id": i,
            "vector": verse['embedding'],
            "payload": verse
        }
        for i, verse in enumerate(verses)
    ]
)
```

### 3. Implement RAG Query

```python
# Query function
def query_scriptures(question: str, top_k: int = 5):
    # Get embedding for question
    q_embedding = openai.Embedding.create(
        input=question,
        model="text-embedding-3-large"
    )['data'][0]['embedding']

    # Search vector DB
    results = client.search(
        collection_name="hindu_scriptures",
        query_vector=q_embedding,
        limit=top_k
    )

    # Format context
    context = "\n\n".join([
        f"{r.payload['source']['text']} {r.payload['source']['chapter']}:{r.payload['source']['verse']}\n"
        f"{r.payload['content']['translation']}"
        for r in results
    ])

    # Query LLM with context
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a wise teacher of Hindu philosophy."},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"}
        ]
    )

    return response['choices'][0]['message']['content']
```

---

## 📝 Known Limitations & Future Work

### Current Limitations

1. **Coverage**: Tier 1 fully implemented, Tiers 2-5 partially ready
2. **Commentaries**: Basic structure in place, content extraction needs work
3. **Word-by-word**: Schema ready, auto-extraction not implemented
4. **Languages**: English translations only (no other modern languages)
5. **OCR**: PDF parsing basic, scanned PDFs need better OCR

### Planned Enhancements

1. **Additional Sources**
   - Complete GRETIL integration
   - Sanskrit Documents corpus
   - Archive.org PDF processing
   - Vedabase API integration

2. **Enhanced Parsing**
   - Better commentary extraction
   - Word-by-word etymology parsing
   - Multiple translation versions
   - Cross-reference detection

3. **Metadata Improvements**
   - ML-based theme classification
   - Sentiment analysis
   - Concept extraction
   - Verse similarity clustering

4. **Performance**
   - Parallel processing
   - Streaming for large files
   - Incremental updates
   - Caching layer

5. **Integration**
   - REST API
   - GraphQL interface
   - Embedding generation
   - Vector DB connectors

---

## 🤝 Contributing

To extend this pipeline:

1. **Add new sources**: Create downloader in `scripts/downloaders/`
2. **Add new formats**: Create parser in `scripts/parsers/`
3. **Enhance metadata**: Extend `scripts/formatters/add_metadata.py`
4. **Add tests**: Update `scripts/test_pipeline.py`
5. **Update docs**: Keep README and this file in sync

---

## 📜 License & Attribution

- **Pipeline code**: MIT License
- **Processed data**: Inherits source licenses
  - DharmicData: ODbL-1.0
  - Indian Scriptures: CC-BY-4.0
  - Project Gutenberg: Public Domain
  - Sacred-Texts: Various (mostly PD/CC-BY)

Always respect source licenses and provide proper attribution.

---

## ✨ Acknowledgments

This pipeline processes texts from:
- **DharmicData** by Bhavy Khatri
- **Indian Scriptures** by Harshit Gupta
- **Project Gutenberg** volunteers
- **Sacred-Texts.com** by John Bruno Hare
- Original translators and scholars

The Hindu scriptures themselves are ancient wisdom, freely available to all.

---

**Last Updated**: 2024-02-05
**Status**: ✅ Core Implementation Complete
**Version**: 1.0.0

