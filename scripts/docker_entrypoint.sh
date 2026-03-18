#!/bin/bash
# Docker entrypoint for CyberArk RAG MCP Server
#
# Uses the pre-built BM25 index from deploy/ -- no runtime scraping needed.
# Server starts instantly with real data.

set -e

DB_DIR="${CYBERARK_RAG_DB:-./chroma_db}"

echo "=== CyberArk RAG MCP Server ==="
echo "Search mode: ${CYBERARK_RAG_SEARCH_MODE:-bm25}"

# Copy pre-built index to expected location
mkdir -p "${DB_DIR}"
cp -n ./deploy/bm25_index.pkl "${DB_DIR}/bm25_index.pkl" 2>/dev/null || true
cp -n ./deploy/products_cache.json "${DB_DIR}/products_cache.json" 2>/dev/null || true

echo "BM25 index ready at ${DB_DIR}/bm25_index.pkl"
echo "Starting MCP server (streamable-http) on port ${PORT:-8000}..."
exec python -m cyberark_rag.mcp_server --transport streamable-http
