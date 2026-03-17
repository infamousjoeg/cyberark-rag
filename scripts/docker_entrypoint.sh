#!/bin/bash
# Docker entrypoint for CyberArk RAG MCP Server
#
# Strategy:
#   1. Start the MCP server immediately (with sample_docs if needed)
#   2. If no full index exists, scrape docs.cyberark.com in the background
#   3. When scrape + re-index finishes, new searches use the full index
#
# This ensures the server is always available, even while scraping.

set -e

DB_DIR="${CYBERARK_RAG_DB:-./chroma_db}"
BM25_PATH="${DB_DIR}/bm25_index.pkl"
SEARCH_MODE="${CYBERARK_RAG_SEARCH_MODE:-hybrid}"

echo "=== CyberArk RAG MCP Server ==="
echo "Search mode: ${SEARCH_MODE}"

# Check if we have a full index from a previous run or Docker build
HAS_FULL_INDEX=false

if [ "${SEARCH_MODE}" = "bm25" ]; then
    if [ -f "${BM25_PATH}" ]; then
        SCRAPED_COUNT=$(ls ./scraped_docs/*.json 2>/dev/null | wc -l || echo "0")
        echo "BM25 index found. Scraped docs: ${SCRAPED_COUNT}"
        if [ "${SCRAPED_COUNT}" -gt 8 ]; then
            HAS_FULL_INDEX=true
        fi
    fi
else
    echo "Embedding model: ${CYBERARK_RAG_MODEL:-all-MiniLM-L6-v2}"
    if [ -d "${DB_DIR}" ] && [ -f "${BM25_PATH}" ]; then
        SCRAPED_COUNT=$(ls ./scraped_docs/*.json 2>/dev/null | wc -l || echo "0")
        echo "Index found. Scraped docs: ${SCRAPED_COUNT}"
        if [ "${SCRAPED_COUNT}" -gt 8 ]; then
            HAS_FULL_INDEX=true
        fi
    fi
fi

# If no full index, bootstrap with sample_docs so server can start immediately
if [ "${HAS_FULL_INDEX}" = "false" ]; then
    echo "No full index found. Building initial index from sample_docs..."
    export CYBERARK_RAG_DOCS="./sample_docs"
    if [ "${SEARCH_MODE}" = "bm25" ]; then
        python -m cyberark_rag index --bm25-only || echo "WARNING: Initial index build failed."
    else
        python -m cyberark_rag index || echo "WARNING: Initial index build failed."
    fi
    # Reset DOCS_DIR for background scrape
    export CYBERARK_RAG_DOCS="./scraped_docs"
fi

# Start background scrape if we don't have a full index
if [ "${HAS_FULL_INDEX}" = "false" ]; then
    echo "Starting background scrape of docs.cyberark.com..."
    bash ./scripts/background_scrape.sh &
    SCRAPE_PID=$!
    echo "Background scrape started (PID: ${SCRAPE_PID})"
fi

echo "Starting MCP server (streamable-http) on port ${PORT:-8000}..."
exec python -m cyberark_rag.mcp_server --transport streamable-http
