.PHONY: help setup install install-rag test download parse format validate clean run ingest query web

PYTHON := python3
BASE_DIR := ~/hindu-scriptures-rag
SCRIPTS := $(BASE_DIR)/scripts

help:
	@echo "Hindu Scripture RAG Pipeline - Available Commands"
	@echo ""
	@echo "Setup & Installation:"
	@echo "  make setup      - Run initial setup script"
	@echo "  make install    - Install Python dependencies"
	@echo "  make test       - Run test suite"
	@echo ""
	@echo "Pipeline Commands:"
	@echo "  make run        - Run complete pipeline"
	@echo "  make download   - Download all sources"
	@echo "  make parse      - Parse downloaded files"
	@echo "  make format     - Format and normalize verses"
	@echo "  make validate   - Validate output files"
	@echo ""
	@echo "RAG System:"
	@echo "  make install-rag - Install RAG dependencies"
	@echo "  make ingest      - Embed verses into ChromaDB"
	@echo "  make query       - Interactive scripture Q&A"
	@echo "  make web         - Launch web interface (Flask)"
	@echo ""
	@echo "Utilities:"
	@echo "  make clean      - Clean intermediate files"
	@echo "  make stats      - Show corpus statistics"
	@echo "  make check      - Run quick health check"
	@echo ""

setup:
	@bash setup.sh

install:
	@$(PYTHON) -m pip install -r requirements.txt

test:
	@$(PYTHON) $(SCRIPTS)/test_pipeline.py --test all

run:
	@$(PYTHON) $(SCRIPTS)/main.py run --base-dir $(BASE_DIR)

download:
	@$(PYTHON) $(SCRIPTS)/main.py download --base-dir $(BASE_DIR)

parse:
	@$(PYTHON) $(SCRIPTS)/main.py parse --base-dir $(BASE_DIR)

format:
	@$(PYTHON) $(SCRIPTS)/main.py format --base-dir $(BASE_DIR)

validate:
	@$(PYTHON) $(SCRIPTS)/validate_schema.py $(BASE_DIR)/final/verses.json

stats:
	@$(PYTHON) -c "import json; f=open('$(BASE_DIR)/final/metadata.json'); data=json.load(f); print(f\"Total verses: {data['total_verses']}\"); print(f\"Sources: {len(data['by_source'])}\"); print(f\"Categories: {len(data['by_category'])}\"); f.close()"

check:
	@echo "Checking directory structure..."
	@test -d $(BASE_DIR)/raw && echo "✓ raw/ exists" || echo "✗ raw/ missing"
	@test -d $(BASE_DIR)/processed && echo "✓ processed/ exists" || echo "✗ processed/ missing"
	@test -d $(BASE_DIR)/final && echo "✓ final/ exists" || echo "✗ final/ missing"
	@test -d $(BASE_DIR)/scripts && echo "✓ scripts/ exists" || echo "✗ scripts/ missing"
	@echo "Checking Python dependencies..."
	@$(PYTHON) -c "import requests; import bs4; import pandas; import tqdm; print('✓ All required packages installed')" || echo "✗ Missing dependencies - run 'make install'"

clean:
	@echo "Cleaning intermediate files..."
	@rm -rf $(BASE_DIR)/processed/*
	@rm -rf $(BASE_DIR)/raw/dharmic-data/.git
	@rm -rf $(BASE_DIR)/raw/indian-scriptures/.git
	@find $(BASE_DIR) -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find $(BASE_DIR) -type f -name "*.pyc" -delete
	@echo "✓ Cleaned"

# Download individual sources
download-github:
	@$(PYTHON) $(SCRIPTS)/downloaders/download_github.py --base-dir $(BASE_DIR)/raw

download-gutenberg:
	@$(PYTHON) $(SCRIPTS)/downloaders/download_gutenberg.py --base-dir $(BASE_DIR)/raw/gutenberg

download-sacred:
	@$(PYTHON) $(SCRIPTS)/downloaders/download_sacred_texts.py --base-dir $(BASE_DIR)/raw/sacred-texts

# Parse individual sources
parse-gita:
	@$(PYTHON) $(SCRIPTS)/parsers/parse_dharmic_json.py $(BASE_DIR)/raw/dharmic-data

parse-upanishads:
	@$(PYTHON) $(SCRIPTS)/parsers/parse_upanishad_csv.py $(BASE_DIR)/raw/indian-scriptures

# Format individual steps
normalize:
	@$(PYTHON) $(SCRIPTS)/formatters/normalize_schema.py --input-dir $(BASE_DIR)/processed --output $(BASE_DIR)/final/verses.json

enrich:
	@$(PYTHON) $(SCRIPTS)/formatters/add_metadata.py --input $(BASE_DIR)/final/verses.json

deduplicate:
	@$(PYTHON) $(SCRIPTS)/formatters/deduplicate.py --input $(BASE_DIR)/final/verses.json

# RAG system
install-rag:
	@$(PYTHON) -m pip install -r requirements-rag.txt

ingest:
	@cd $(SCRIPTS)/rag && $(PYTHON) ingest.py

query:
	@cd $(SCRIPTS)/rag && $(PYTHON) cli.py

web:
	@cd $(SCRIPTS)/rag && $(PYTHON) app.py
