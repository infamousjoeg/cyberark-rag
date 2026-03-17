# Dockerfile for CyberArk RAG MCP Server on Render.com
#
# Strategy:
#   - Pre-built BM25 index is committed in deploy/ (built locally)
#   - Docker just copies the index and starts the server
#   - No runtime scraping needed
#
# To update the index, run locally:
#   ./scripts/build_deploy_index.sh
#   git add deploy/ && git commit && git push
#
# Memory strategy: BM25-only mode avoids loading the embedding model
# (~300MB+) and ChromaDB, keeping RAM under the 512MB free-tier limit.
#
# Render free tier: 512MB RAM, 120-min build timeout, no persistent disk.

FROM python:3.13-slim AS builder

WORKDIR /app

# Install system deps (build-essential for native extensions)
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code + config files
COPY cyberark_rag/ cyberark_rag/
COPY product_aliases.yaml query_expansions.yaml ./

# Copy pre-built index
COPY deploy/ deploy/

# Copy entrypoint
COPY scripts/docker_entrypoint.sh ./entrypoint.sh

# --- Runtime stage (smaller image) ---
FROM python:3.13-slim

WORKDIR /app

# Copy installed packages
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy app code and pre-built index
COPY --from=builder /app /app

# Runtime configuration -- BM25-only mode keeps RAM under 512MB
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    CYBERARK_RAG_SEARCH_MODE=bm25 \
    MCP_TRANSPORT=streamable-http \
    PORT=8000

EXPOSE 8000

ENTRYPOINT ["bash", "./entrypoint.sh"]
