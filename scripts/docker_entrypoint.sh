#!/bin/bash
# Docker entrypoint for CyberArk RAG MCP Server
#
# Uses a pre-built BM25 index from deploy/ directory.
# No runtime scraping -- index is built locally and committed.

set -e

DB_DIR="${CYBERARK_RAG_DB:-./chroma_db}"

echo "=== CyberArk RAG MCP Server ==="
echo "Search mode: ${CYBERARK_RAG_SEARCH_MODE:-bm25}"

# Copy pre-built index to expected location
if [ -f "./deploy/bm25_index.pkl" ]; then
    mkdir -p "${DB_DIR}"
    cp ./deploy/bm25_index.pkl "${DB_DIR}/bm25_index.pkl"
    echo "Pre-built BM25 index loaded from deploy/"
else
    echo "WARNING: No pre-built index found in deploy/"
    echo "Run ./scripts/build_deploy_index.sh locally, commit, and redeploy."
fi

echo "Starting MCP server (streamable-http) on port ${PORT:-8000}..."
exec python -m cyberark_rag.mcp_server --transport streamable-http
