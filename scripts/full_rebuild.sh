#!/bin/bash
# Full rebuild: scrape all pages, clean and rebuild index
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== CyberArk RAG Full Rebuild ==="
echo ""
echo "WARNING: This will re-scrape ALL pages and rebuild the entire index."
echo "This may take several hours for the scraping phase."
echo ""

read -rp "Continue? (y/N) " confirm
if [[ "$confirm" != [yY] ]]; then
    echo "Aborted."
    exit 0
fi

# Step 1: Full scrape
echo ""
echo "[1/3] Running full scraper..."
python3 incremental_scraper.py --full
echo ""

# Step 2: Clean old index
echo "[2/3] Cleaning old index..."
rm -rf chroma_db/
rm -f chroma_db/bm25_index.pkl
echo "Old index removed."
echo ""

# Step 3: Rebuild index
echo "[3/3] Rebuilding index..."
python3 -m cyberark_rag index
echo ""

echo "=== Full rebuild complete ==="
