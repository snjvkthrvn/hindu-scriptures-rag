# Quick Start Guide

Get up and running with the Hindu Scripture RAG Pipeline in 5 minutes.

## Prerequisites

- Python 3.8 or higher
- Git (for downloading some sources)
- 2-5 GB free disk space
- Internet connection

## Installation

### Option 1: Automated Setup (Recommended)

```bash
cd ~/hindu-scriptures-rag
./setup.sh
```

This will:
- Create directory structure
- Install Python dependencies
- Set up virtual environment
- Run system checks

### Option 2: Manual Setup

```bash
# Create directories
mkdir -p ~/hindu-scriptures-rag
cd ~/hindu-scriptures-rag

# Install dependencies
pip install -r requirements.txt

# Make scripts executable
chmod +x scripts/*.py
chmod +x scripts/downloaders/*.py
chmod +x scripts/parsers/*.py
chmod +x scripts/formatters/*.py
```

## Quick Test

Run the test suite to verify everything works:

```bash
python scripts/test_pipeline.py
```

You should see:
```
✓ Unicode normalization works
✓ Verse detection works
✓ Verse validation works
✓ Schema normalization works
✓ Metadata enrichment works
✓ Full pipeline works
✓ All tests passed!
```

## Running the Pipeline

### Full Pipeline (Recommended for First Run)

```bash
python scripts/main.py run
```

This will:
1. Download sources from GitHub, Project Gutenberg, and sacred-texts.com (~10-20 minutes)
2. Parse all files (~5 minutes)
3. Normalize and format (~5 minutes)
4. Enrich metadata (~2 minutes)
5. Deduplicate verses (~2 minutes)
6. Validate output (~1 minute)

Total time: **25-35 minutes**

### Step-by-Step Pipeline

If you want more control:

```bash
# Step 1: Download sources
python scripts/main.py download

# Step 2: Parse files
python scripts/main.py parse

# Step 3: Format and normalize
python scripts/main.py format

# Step 4: Validate
python scripts/main.py validate
```

## Using Make Commands (Optional)

If you prefer make:

```bash
# See all commands
make help

# Run pipeline
make run

# Individual steps
make download
make parse
make format
make validate

# Utilities
make test
make check
make stats
```

## Checking Output

After running the pipeline:

```bash
# List generated files
ls -lh final/

# Check verse count
python -c "
import json
with open('final/verses.json') as f:
    verses = json.load(f)
print(f'Total verses: {len(verses)}')
"

# View sample verse
python -c "
import json
with open('final/verses.json') as f:
    verses = json.load(f)
print(json.dumps(verses[0], indent=2, ensure_ascii=False))
"

# Validate schema
python scripts/validate_schema.py final/verses.json
```

## Expected Output Files

After a successful run:

```
final/
├── verses.json              # All normalized verses
├── verses_enriched.json     # With metadata enrichment
├── verses_deduped.json      # After deduplication
└── metadata.json            # Corpus statistics
```

## Troubleshooting

### Import Errors

```bash
# Activate virtual environment
source venv/bin/activate

# Or install globally
pip install -r requirements.txt
```

### Download Failures

```bash
# Check internet connection
ping github.com

# Retry individual downloads
python scripts/downloaders/download_github.py
python scripts/downloaders/download_gutenberg.py
python scripts/downloaders/download_sacred_texts.py
```

### Empty Output

```bash
# Check if sources were downloaded
ls -la raw/

# Check if parsing worked
ls -la processed/

# Re-run specific steps
python scripts/main.py parse
```

### Permission Errors

```bash
# Make scripts executable
chmod +x scripts/*.py
chmod +x scripts/*/*.py

# Or run with python explicitly
python scripts/main.py run
```

## What's Next?

1. **Explore the data**:
   ```bash
   # View statistics
   cat final/metadata.json | python -m json.tool

   # Search for specific texts
   grep -i "bhagavad gita" final/verses.json | head
   ```

2. **Generate embeddings**:
   - Use OpenAI's text-embedding-3-large
   - Or sentence-transformers for local embeddings
   - Save to `final/embeddings/`

3. **Set up vector database**:
   - Qdrant (recommended for local)
   - Pinecone (cloud option)
   - Weaviate (hybrid search)

4. **Build RAG system**:
   - Use LangChain or LlamaIndex
   - Connect to Claude/GPT-4
   - Implement hybrid search (BM25 + vector)

## Resources

- **Full Documentation**: `README.md`
- **Plan Details**: Original plan document
- **Test Suite**: `scripts/test_pipeline.py`
- **Validation**: `scripts/validate_schema.py`

## Getting Help

If you encounter issues:

1. Check the troubleshooting section above
2. Review error messages in console output
3. Verify prerequisites are installed
4. Check file permissions
5. Review the README for detailed documentation

## Performance Tips

- **Faster downloads**: Use `--parallel` flag (when implemented)
- **Memory usage**: Process one tier at a time for large datasets
- **Storage**: Clean intermediate files with `make clean`
- **Speed**: Use SSD for better I/O performance

## Example Commands

```bash
# Quick health check
make check

# Run tests only
make test

# Download and parse Bhagavad Gita only
make download-github
make parse-gita

# Validate specific file
python scripts/validate_schema.py final/verses_deduped.json

# Clean and start fresh
make clean
make run
```

---

**Happy processing! 🕉️**

For detailed documentation, see `README.md`
