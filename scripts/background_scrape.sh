#!/bin/bash
# Background scrape and re-index for runtime use.
#
# Called by docker_entrypoint.sh after the MCP server starts.
# Scrapes docs.cyberark.com, builds BM25 index, then signals
# the server to reload.
#
# This runs in the background so the server is available immediately
# with sample_docs while the full scrape completes.

set -e

SCRAPE_DELAY="${SCRAPE_DELAY:-0.5}"
EXCLUDE_PRODUCTS="${EXCLUDE_PRODUCTS:-pam-self-hosted,secrets-manager-sh,conjur-open-source,mis-self-hosted,mis-saas}"
MAX_PAGES="${MAX_PAGES:-10000}"
OUTPUT_DIR="${CYBERARK_RAG_DOCS:-./scraped_docs}"

echo "[background_scrape] Starting scrape (delay=${SCRAPE_DELAY}s, max_pages=${MAX_PAGES})..."

# Scrape docs
python incremental_scraper.py \
    --full \
    --delay "${SCRAPE_DELAY}" \
    --exclude-products "${EXCLUDE_PRODUCTS}" \
    --max-pages "${MAX_PAGES}" \
    --output-dir "${OUTPUT_DIR}" \
    2>&1

SCRAPED_COUNT=$(ls "${OUTPUT_DIR}"/*.json 2>/dev/null | wc -l)
echo "[background_scrape] Scrape complete: ${SCRAPED_COUNT} pages"

if [ "${SCRAPED_COUNT}" -le 8 ]; then
    echo "[background_scrape] Too few pages scraped (${SCRAPED_COUNT}), skipping re-index"
    exit 0
fi

# Rebuild BM25 index
echo "[background_scrape] Rebuilding BM25 index..."
CYBERARK_RAG_DOCS="${OUTPUT_DIR}" python -m cyberark_rag index --bm25-only 2>&1

echo "[background_scrape] Re-index complete. New searches will use the updated index."
