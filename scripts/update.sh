#!/bin/bash
# Incremental update: scrape changed pages and re-index
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== CyberArk RAG Incremental Update ==="
echo ""

# Step 1: Incremental scrape
echo "[1/2] Running incremental scraper..."
python3 incremental_scraper.py "$@"
echo ""

# Step 2: Re-index
echo "[2/2] Rebuilding index..."
python3 -m cyberark_rag index
echo ""

echo "=== Update complete ==="
