#!/bin/bash
# Docker entrypoint for CyberArk RAG MCP Server
#
# The search index is built during Docker build (scrape + index).
# This entrypoint checks that the index exists and starts the server.
# If no index exists (build failed), it falls back to sample_docs.

set -e

DB_DIR="${CYBERARK_RAG_DB:-./chroma_db}"
BM25_PATH="${DB_DIR}/bm25_index.pkl"
SEARCH_MODE="${CYBERARK_RAG_SEARCH_MODE:-hybrid}"

echo "=== CyberArk RAG MCP Server ==="
echo "Search mode: ${SEARCH_MODE}"

if [ "${SEARCH_MODE}" = "bm25" ]; then
    # BM25-only mode: only need the BM25 index file
    if [ -f "${BM25_PATH}" ]; then
        SCRAPED_COUNT=$(ls ./scraped_docs/*.json 2>/dev/null | wc -l)
        echo "BM25 index found. Scraped docs: ${SCRAPED_COUNT}"
    else
        echo "No BM25 index found from build. Building from sample_docs..."
        export CYBERARK_RAG_DOCS="./sample_docs"
        python -m cyberark_rag index --bm25-only || echo "WARNING: Index build failed."
    fi
else
    echo "Embedding model: ${CYBERARK_RAG_MODEL:-all-MiniLM-L6-v2}"
    if [ -d "${DB_DIR}" ] && [ -f "${BM25_PATH}" ]; then
        SCRAPED_COUNT=$(ls ./scraped_docs/*.json 2>/dev/null | wc -l)
        echo "Index found. Scraped docs: ${SCRAPED_COUNT}"
    else
        echo "No index found from build. Building from sample_docs..."
        export CYBERARK_RAG_DOCS="./sample_docs"
        python -m cyberark_rag index || echo "WARNING: Index build failed."
    fi
fi

echo "Starting MCP server (streamable-http) on port ${PORT:-8000}..."
exec python -m cyberark_rag.mcp_server --transport streamable-http
