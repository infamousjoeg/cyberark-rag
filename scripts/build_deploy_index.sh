#!/bin/bash
# Build a BM25 index locally and stage it for deployment.
#
# Run this on your Mac whenever you want to refresh the deployed index:
#   ./scripts/build_deploy_index.sh
#   git add deploy/ && git commit -m "data: update BM25 index" && git push
#
# Excludes: pam-self-hosted, secrets-manager-sh, conjur-open-source, mis-self-hosted, mis-saas

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

EXCLUDE="pam-self-hosted,secrets-manager-sh,conjur-open-source,mis-self-hosted,mis-saas"
DOCS_DIR="${CYBERARK_RAG_DOCS:-./scraped_docs}"
DEPLOY_DIR="./deploy"

echo "=== CyberArk RAG Deploy Index Builder ==="
echo "Docs dir: ${DOCS_DIR}"
echo "Excluding: ${EXCLUDE}"
echo ""

# Step 1: Scrape (incremental by default, use --full for first run)
SCRAPE_FLAGS="${*:---full}"
echo "Step 1: Scraping docs.cyberark.com (${SCRAPE_FLAGS})..."
python incremental_scraper.py \
    ${SCRAPE_FLAGS} \
    --exclude-products "${EXCLUDE}" \
    --output-dir "${DOCS_DIR}"

SCRAPED_COUNT=$(ls "${DOCS_DIR}"/*.json 2>/dev/null | wc -l | tr -d ' ')
echo "Scraped docs: ${SCRAPED_COUNT}"

if [ "${SCRAPED_COUNT}" -lt 10 ]; then
    echo "ERROR: Too few docs scraped (${SCRAPED_COUNT}). Aborting."
    exit 1
fi

# Step 2: Build BM25 index
echo ""
echo "Step 2: Building BM25 index..."
python -m cyberark_rag index --bm25-only

# Step 3: Copy to deploy/
echo ""
echo "Step 3: Copying index to deploy/..."
mkdir -p "${DEPLOY_DIR}"

DB_DIR="${CYBERARK_RAG_DB:-./chroma_db}"
BM25_PATH="${DB_DIR}/bm25_index.pkl"

if [ ! -f "${BM25_PATH}" ]; then
    # Fallback: check project root
    BM25_PATH="./bm25_index.pkl"
fi

if [ -f "${BM25_PATH}" ]; then
    cp "${BM25_PATH}" "${DEPLOY_DIR}/bm25_index.pkl"
    SIZE=$(du -sh "${DEPLOY_DIR}/bm25_index.pkl" | cut -f1)
    echo "Index copied to deploy/bm25_index.pkl (${SIZE})"
else
    echo "ERROR: BM25 index not found at ${BM25_PATH}"
    exit 1
fi

echo ""
echo "=== Done! ==="
echo "Next steps:"
echo "  git add deploy/"
echo "  git commit -m 'data: update BM25 index'"
echo "  git push"
