#!/bin/bash
# Build the pre-built BM25 index for deployment.
#
# Run this locally on your Mac to scrape docs, build the index,
# and copy artifacts to deploy/. Then commit and push to trigger
# a Render rebuild with real data baked in.
#
# Usage:
#   bash scripts/build_deploy_index.sh
#   bash scripts/build_deploy_index.sh --incremental   # skip --full flag

set -e

EXCLUDE="pam-self-hosted,secrets-manager-sh,conjur-open-source,mis-self-hosted,mis-saas"
FULL_FLAG="--full"

if [ "$1" = "--incremental" ]; then
    FULL_FLAG=""
    echo "=== Incremental mode (only new/changed pages) ==="
fi

echo "=== Step 1: Scraping docs.cyberark.com (SaaS products only) ==="
echo "Excluding: ${EXCLUDE}"
python incremental_scraper.py ${FULL_FLAG} \
  --exclude-products "${EXCLUDE}" \
  --output-dir ./scraped_docs

SCRAPED_COUNT=$(ls ./scraped_docs/*.json 2>/dev/null | wc -l | tr -d ' ')
echo "Scraped docs: ${SCRAPED_COUNT}"

echo "=== Step 2: Building BM25 index ==="
python -m cyberark_rag index --bm25-only

echo "=== Step 3: Copying artifacts to deploy/ ==="
mkdir -p deploy
cp chroma_db/bm25_index.pkl deploy/
cp chroma_db/products_cache.json deploy/

echo ""
echo "=== Done ==="
ls -lh deploy/
echo ""

# Check if Git LFS is needed
BM25_SIZE=$(stat -f%z deploy/bm25_index.pkl 2>/dev/null || stat -c%s deploy/bm25_index.pkl 2>/dev/null)
if [ "${BM25_SIZE}" -gt 104857600 ]; then
    echo "WARNING: bm25_index.pkl is > 100MB. Set up Git LFS:"
    echo "  git lfs install"
    echo "  git lfs track 'deploy/bm25_index.pkl'"
    echo "  git add .gitattributes"
else
    echo "bm25_index.pkl is under 100MB -- no Git LFS needed."
fi

echo ""
echo "Commit deploy/ and push to trigger Render rebuild."
