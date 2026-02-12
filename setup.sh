#!/bin/bash
# Setup script for Hindu Scripture RAG Pipeline

set -e  # Exit on error

echo "╔════════════════════════════════════════════════════════════╗"
echo "║     Hindu Scripture RAG Pipeline - Setup Script           ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Base directory
BASE_DIR="${HOME}/hindu-scriptures-rag"

echo -e "${YELLOW}[1/5]${NC} Checking prerequisites..."

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is not installed${NC}"
    echo "Please install Python 3.8 or higher"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo -e "${GREEN}✓${NC} Python ${PYTHON_VERSION} found"

# Check git
if ! command -v git &> /dev/null; then
    echo -e "${YELLOW}Warning: Git is not installed${NC}"
    echo "Git is required for downloading some sources"
    echo "Install it with: brew install git (macOS) or apt-get install git (Linux)"
else
    echo -e "${GREEN}✓${NC} Git found"
fi

# Check pip
if ! command -v pip3 &> /dev/null; then
    echo -e "${RED}Error: pip3 is not installed${NC}"
    exit 1
fi

echo -e "${GREEN}✓${NC} pip3 found"

echo ""
echo -e "${YELLOW}[2/5]${NC} Creating directory structure..."

# Create directories
mkdir -p "${BASE_DIR}"/{raw,processed,final,scripts}
mkdir -p "${BASE_DIR}"/raw/{dharmic-data,indian-scriptures,gretil,sacred-texts,sanskrit-documents,gutenberg,archive-org}
mkdir -p "${BASE_DIR}"/processed/{tier1-essential,tier2-critical,tier3-epics,tier4-philosophy,tier5-puranas}
mkdir -p "${BASE_DIR}"/final/embeddings
mkdir -p "${BASE_DIR}"/scripts/{downloaders,parsers,formatters,utils}

echo -e "${GREEN}✓${NC} Directory structure created at ${BASE_DIR}"

echo ""
echo -e "${YELLOW}[3/5]${NC} Installing Python dependencies..."

cd "${BASE_DIR}"

# Create virtual environment (optional but recommended)
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo -e "${GREEN}✓${NC} Virtual environment created"
fi

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    echo -e "${GREEN}✓${NC} Dependencies installed"
else
    echo -e "${YELLOW}Warning: requirements.txt not found${NC}"
fi

echo ""
echo -e "${YELLOW}[4/5]${NC} Making scripts executable..."

chmod +x scripts/*.py
chmod +x scripts/downloaders/*.py
chmod +x scripts/parsers/*.py
chmod +x scripts/formatters/*.py

echo -e "${GREEN}✓${NC} Scripts are now executable"

echo ""
echo -e "${YELLOW}[5/5]${NC} Running system check..."

# Test imports
python3 << EOF
import sys
try:
    import requests
    import bs4
    import pandas
    import tqdm
    print("✓ All required packages imported successfully")
except ImportError as e:
    print(f"✗ Import error: {e}")
    sys.exit(1)
EOF

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓${NC} System check passed"
else
    echo -e "${RED}✗${NC} System check failed"
    exit 1
fi

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                    SETUP COMPLETE!                         ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "Next steps:"
echo ""
echo "1. Activate the virtual environment:"
echo "   ${GREEN}source ~/hindu-scriptures-rag/venv/bin/activate${NC}"
echo ""
echo "2. Run the full pipeline:"
echo "   ${GREEN}cd ~/hindu-scriptures-rag${NC}"
echo "   ${GREEN}python scripts/main.py run${NC}"
echo ""
echo "3. Or run individual commands:"
echo "   ${GREEN}python scripts/main.py download${NC}  # Download sources"
echo "   ${GREEN}python scripts/main.py parse${NC}     # Parse downloaded files"
echo "   ${GREEN}python scripts/main.py format${NC}    # Format and enrich"
echo "   ${GREEN}python scripts/main.py validate${NC}  # Validate output"
echo ""
echo "4. Check the README for more options:"
echo "   ${GREEN}cat ~/hindu-scriptures-rag/README.md${NC}"
echo ""
echo "Happy processing! 🕉️"
