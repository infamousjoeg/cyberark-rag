# Dockerfile for CyberArk RAG MCP Server on Render.com
#
# Build scrapes docs.cyberark.com and builds the search index.
# Runtime serves the MCP server over streamable-http for Claude Web.
#
# Render free tier: 500MB RAM, 120-min build timeout, no persistent disk.
# At --delay 0.2 + HTTP latency, ~2000 pages fits in ~70 min of build time.
# Adjust MAX_SCRAPE_PAGES to scrape more (uses more build minutes).

FROM python:3.13-slim AS builder

WORKDIR /app

# Install system deps (build-essential for native extensions)
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download embedding model during build
ENV CYBERARK_RAG_MODEL=all-MiniLM-L6-v2
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Copy application code + config files needed for scraping and indexing
COPY cyberark_rag/ cyberark_rag/
COPY incremental_scraper.py .
COPY product_aliases.yaml query_expansions.yaml ./
COPY sample_docs/ sample_docs/
COPY scripts/docker_entrypoint.sh ./entrypoint.sh

# --- Scrape docs.cyberark.com during build ---
# MAX_SCRAPE_PAGES controls how many pages to scrape (0 = unlimited).
# 2000 pages covers the most important docs and fits in ~70 min.
# Set to 0 for a full scrape (~19K pages, requires ~8h build or paid tier).
ARG MAX_SCRAPE_PAGES=2000
ARG SCRAPE_DELAY=0.2

RUN echo "=== Scraping docs.cyberark.com (max ${MAX_SCRAPE_PAGES} pages, delay ${SCRAPE_DELAY}s) ===" && \
    python incremental_scraper.py \
        --full \
        --delay "${SCRAPE_DELAY}" \
        --max-pages "${MAX_SCRAPE_PAGES}" \
        --output-dir ./scraped_docs \
    && echo "=== Scrape complete: $(ls ./scraped_docs/*.json 2>/dev/null | wc -l) pages ===" \
    || echo "=== Scrape had errors, continuing with whatever was collected ==="

# --- Build the search index ---
RUN echo "=== Building search index ===" && \
    CYBERARK_RAG_DOCS=./scraped_docs python -m cyberark_rag index \
    && echo "=== Index build complete ===" \
    || echo "=== Index build failed, will fall back to sample_docs at runtime ==="

# --- Runtime stage (smaller image) ---
FROM python:3.13-slim

WORKDIR /app

# Copy installed packages
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy app code, scraped docs, and pre-built index
COPY --from=builder /app /app

# Copy cached embedding model
COPY --from=builder /root/.cache/huggingface /root/.cache/huggingface

# Runtime configuration
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    CYBERARK_RAG_MODEL=all-MiniLM-L6-v2 \
    MCP_TRANSPORT=streamable-http \
    PORT=8000

EXPOSE 8000

ENTRYPOINT ["bash", "./entrypoint.sh"]
