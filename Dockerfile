# Multi-stage Dockerfile for CyberArk RAG MCP Server
# Optimized for Render.com free tier (500MB RAM)
# Uses all-MiniLM-L6-v2 (80MB) instead of bge-large (1.3GB)

FROM python:3.13-slim AS base

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the embedding model during build (cached in image)
# Using MiniLM for low memory footprint on free tier
ENV CYBERARK_RAG_MODEL=all-MiniLM-L6-v2
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Copy application code
COPY cyberark_rag/ cyberark_rag/
COPY sample_docs/ sample_docs/
COPY product_aliases.yaml query_expansions.yaml ./
COPY scripts/docker_entrypoint.sh ./entrypoint.sh

# Build the demo index from sample_docs at build time
# This avoids the startup cost on each container restart
RUN CYBERARK_RAG_DOCS=./sample_docs python -m cyberark_rag index || true

# --- Runtime stage ---
FROM python:3.13-slim

WORKDIR /app

# Copy installed packages from build stage
COPY --from=base /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=base /usr/local/bin /usr/local/bin

# Copy application and pre-built index
COPY --from=base /app /app

# Copy the cached embedding model
COPY --from=base /root/.cache/huggingface /root/.cache/huggingface

# Environment configuration
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    CYBERARK_RAG_MODEL=all-MiniLM-L6-v2 \
    MCP_TRANSPORT=streamable-http \
    PORT=8000

EXPOSE 8000

# Health check for Render
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT}/mcp')" || exit 1

ENTRYPOINT ["bash", "./entrypoint.sh"]
