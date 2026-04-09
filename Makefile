.PHONY: help setup install install-rag test download parse format validate clean run ingest query web qdrant-up qdrant-down deploy deploy-down deploy-logs deploy-index

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
	@echo "  make qdrant-up   - Start Qdrant in Docker (set QDRANT_URL=http://localhost:6333)"
	@echo "  make qdrant-down - Stop Qdrant Docker"
	@echo "  make ingest      - Embed verses into ChromaDB"
	@echo "  make query       - Interactive scripture Q&A"
	@echo "  make web         - Launch web interface (Flask)"
	@echo ""
	@echo "Deployment (Docker Compose):"
	@echo "  make deploy        - Build and start all services (Qdrant + apps + Caddy)"
	@echo "  make deploy-down   - Stop all deployed services"
	@echo "  make deploy-logs   - Tail logs from all services"
	@echo "  make deploy-index  - Index English verses inside running container"
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

# Qdrant in Docker (recommended for 20k+ points)
qdrant-up:
	docker compose up -d qdrant
	@echo "Qdrant at http://localhost:6333. Set QDRANT_URL=http://localhost:6333 in .env and re-index."

qdrant-down:
	docker compose down

# English-only RAG (v1)
english-build:
	@$(PYTHON) english-v1-rag/build_english_verses.py

english-index:
	@$(PYTHON) english-v1-rag/index_english.py

english-index-resume:
	@$(PYTHON) english-v1-rag/index_english.py --resume

ingest:
	@cd $(SCRIPTS)/rag && $(PYTHON) ingest.py

query:
	@cd $(SCRIPTS)/rag && $(PYTHON) cli.py

web:
	@cd $(SCRIPTS)/rag && $(PYTHON) app.py

# Docker Compose deployment
deploy:
	docker compose up -d --build
	@echo ""
	@echo "Services started:"
	@echo "  English RAG  → http://localhost (via Caddy)"
	@echo "  Main RAG     → http://localhost/main (via Caddy)"
	@echo "  Qdrant       → http://localhost:6333"
	@echo ""
	@echo "Next: run 'make deploy-index' to index verses into Qdrant."

deploy-down:
	docker compose down

deploy-logs:
	docker compose logs -f

deploy-index:
	docker compose exec rag python index_english.py
	@echo "English verses indexed."
