# Dockerfile for CyberArk RAG MCP Server on Render.com
#
# Build: scrapes SaaS product docs from docs.cyberark.com, builds BM25 index.
# Runtime: serves MCP over streamable-http using BM25-only search.
#
# Memory strategy: BM25-only mode avoids loading the embedding model (~300MB+)
# and ChromaDB at runtime, keeping RAM well under the 512MB free-tier limit.
# BM25 keyword search still provides good results for CyberArk terminology.
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

# Copy application code + config files needed for scraping and indexing
COPY cyberark_rag/ cyberark_rag/
COPY incremental_scraper.py .
COPY product_aliases.yaml query_expansions.yaml ./
COPY sample_docs/ sample_docs/
COPY scripts/docker_entrypoint.sh ./entrypoint.sh

# --- Scrape docs.cyberark.com during build (SaaS products only) ---
# Excluding self-hosted products cuts ~19K pages down to ~5-8K,
# which fits comfortably in Render's 120-min build timeout.
ARG SCRAPE_DELAY=0.2
ARG EXCLUDE_PRODUCTS=pam-self-hosted,secrets-manager-sh,conjur-open-source,mis-self-hosted,mis-saas

RUN echo "=== Scraping docs.cyberark.com (SaaS only, delay ${SCRAPE_DELAY}s) ===" && \
    python incremental_scraper.py \
        --full \
        --delay "${SCRAPE_DELAY}" \
        --exclude-products "${EXCLUDE_PRODUCTS}" \
        --output-dir ./scraped_docs \
    && echo "=== Scrape complete: $(ls ./scraped_docs/*.json 2>/dev/null | wc -l) pages ===" \
    || echo "=== Scrape had errors, continuing with whatever was collected ==="

# --- Build BM25-only search index (no embedding model = saves ~300MB RAM) ---
RUN echo "=== Building BM25 search index ===" && \
    CYBERARK_RAG_DOCS=./scraped_docs python -m cyberark_rag index --bm25-only \
    && echo "=== Index build complete ===" \
    || echo "=== Index build failed, will fall back to sample_docs at runtime ==="

# --- Runtime stage (smaller image) ---
FROM python:3.13-slim

WORKDIR /app

# Copy installed packages
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy app code, scraped docs, and pre-built BM25 index
COPY --from=builder /app /app

# Runtime configuration -- BM25-only mode keeps RAM under 512MB
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    CYBERARK_RAG_SEARCH_MODE=bm25 \
    MCP_TRANSPORT=streamable-http \
    PORT=8000

EXPOSE 8000

ENTRYPOINT ["bash", "./entrypoint.sh"]
