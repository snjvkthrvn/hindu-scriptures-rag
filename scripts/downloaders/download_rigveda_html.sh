#!/bin/bash
#
# Download Rigveda HTML pages from sacred-texts.com.
# Uses wget or curl (whichever is available).
# Run from a machine where sacred-texts.com is accessible
# (some data center IPs may get 403 from Cloudflare).
#
# Usage: ./download_rigveda_html.sh [output_dir]
# Default output: raw/sacred-texts/rigveda_html/
#

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
OUT_DIR="${1:-$PROJECT_ROOT/raw/sacred-texts/rigveda_html}"
BASE_URL="https://www.sacred-texts.com/hin/rigveda"

if command -v wget &>/dev/null; then
    GET="wget -q -O"
elif command -v curl &>/dev/null; then
    GET="curl -sL -o"
else
    echo "Error: need wget or curl"
    exit 1
fi

mkdir -p "$OUT_DIR"
cd "$OUT_DIR"

echo "Downloading Rigveda to $OUT_DIR"
echo "Base URL: $BASE_URL"
echo ""

# Download book indexes and extract hymn URLs, then download each hymn
for book in $(seq 1 10); do
    idx="rvi$(printf "%02d" $book).htm"
    echo "=== Book $book ==="
    
    if ! $GET "$idx" "$BASE_URL/$idx" 2>/dev/null || [ ! -s "$idx" ]; then
        echo "  Failed to fetch book index $idx"
        continue
    fi
    
    # Extract hymn filenames (rv01001.htm, etc.)
    hymns=$(grep -oE 'rv[0-9]{5}\.htm' "$idx" | sort -u)
    count=0
    for hymn in $hymns; do
        if [ ! -f "$hymn" ]; then
            $GET "$hymn" "$BASE_URL/$hymn" && count=$((count+1))
            sleep 0.5  # Be respectful
        fi
    done
    echo "  Downloaded $count new hymns"
done

echo ""
echo "Done. Run the Python scraper with:"
echo "  python scripts/downloaders/download_rigveda.py --from-html-dir $OUT_DIR -o raw/sacred-texts/rigveda.json"
echo ""
