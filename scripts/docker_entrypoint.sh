#!/bin/bash
# Docker entrypoint for CyberArk RAG MCP Server
#
# Checks if the search index exists. If not, builds it from
# sample_docs/ (demo) or scraped_docs/ (full deployment).
# Then starts the MCP server with streamable-http transport.

set -e

DOCS_DIR="${CYBERARK_RAG_DOCS:-./scraped_docs}"
DB_DIR="${CYBERARK_RAG_DB:-./chroma_db}"
BM25_PATH="${DB_DIR}/bm25_index.pkl"

echo "=== CyberArk RAG MCP Server ==="
echo "Docs dir: ${DOCS_DIR}"
echo "DB dir: ${DB_DIR}"
echo "Embedding model: ${CYBERARK_RAG_MODEL:-all-MiniLM-L6-v2}"

# Check if index already exists
if [ -d "${DB_DIR}" ] && [ -f "${BM25_PATH}" ]; then
    echo "Index found. Skipping build."
else
    echo "No index found. Building from available docs..."

    # Use scraped_docs if it exists and has files, otherwise fall back to sample_docs
    if [ -d "${DOCS_DIR}" ] && [ "$(ls -A ${DOCS_DIR}/*.json 2>/dev/null | head -1)" ]; then
        echo "Using docs from ${DOCS_DIR}"
    elif [ -d "./sample_docs" ] && [ "$(ls -A ./sample_docs/*.json 2>/dev/null | head -1)" ]; then
        echo "No scraped_docs found. Using sample_docs for demo index."
        export CYBERARK_RAG_DOCS="./sample_docs"
    else
        echo "WARNING: No documents found. Server will start but search will not work."
        echo "Add JSON docs to scraped_docs/ or sample_docs/ and restart."
    fi

    # Build the index
    python -m cyberark_rag index || echo "WARNING: Index build failed. Server starting without index."
fi

echo "Starting MCP server (streamable-http) on port ${PORT:-8000}..."
exec python -m cyberark_rag.mcp_server --transport streamable-http
