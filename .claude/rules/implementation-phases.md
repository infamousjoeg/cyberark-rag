# Implementation Phases

Execute in order. Each phase must produce working, testable code before moving on. Commit after each phase.

## Phase 1: Foundation -- Config & Path Cleanup (Est: 1-2h)

**Why**: Hardcoded paths to `/Users/joe.garcia/...` break portability. Central config prevents drift.

Create `cyberark_rag/config.py`:
- `Settings` class with `PROJECT_ROOT`, `DOCS_DIR`, `DB_DIR`, `BM25_PATH`, `STATE_FILE`, `EMBEDDING_MODEL`, `COLLECTION_NAME`, `CHUNK_SIZE`, `CHUNK_OVERLAP`
- All paths derived from env vars with sensible defaults relative to `PROJECT_ROOT = Path(__file__).parent.parent`

Create `cyberark_rag/logging_config.py`:
- `setup_logging(name, level)` -> Logger with stderr-only StreamHandler
- Format: `%(asctime)s [%(levelname)s] %(name)s: %(message)s`

Update all modules to import from config.py:
- `indexer.py`, `search.py`, `mcp_server.py`, `product_aliases.py`, `query_expansion.py`, `terminal.py`
- `config.yaml`: replace hardcoded python path with `python3`
- `mcp_config.json`: use relative PYTHONPATH
- `bin/cyai`: shebang -> `#!/usr/bin/env python3`

**Validation**: `grep -rn "/Users/joe" .` returns zero results. All existing tests pass.


## Phase 2: Incremental Scraper (Est: 2-3h)

**Why**: BFS crawler takes 8+ hours. Sitemap-driven updates take 2-10 minutes.

Create `incremental_scraper.py` at project root. Full spec in `.claude/rules/scraper.md`.

Create `tests/test_incremental_scraper.py` with: sitemap parsing, URL validation, state round-trip, needs_update logic.

**Validation**: `python incremental_scraper.py --dry-run` discovers URLs. `pytest tests/test_incremental_scraper.py -v` passes.


## Phase 3: Contextual Retrieval (Est: 2-3h)

**Why**: Anthropic research shows 35% fewer retrieval failures with metadata-derived context prefixes. Chunks like "Revenue grew 3%" become "From CyberArk Privilege Cloud documentation, page titled 'Billing Overview'. Revenue grew 3%."

Create `cyberark_rag/contextual_chunker.py`. Full spec in `.claude/rules/search-indexing.md`.

Modify `cyberark_rag/indexer.py`:
- After `self.chunk_text(content, metadata)`, call `contextualize_chunks(chunks, full_content=content)`
- Store `original_text` in metadata, embed the prefixed version

Create `tests/test_contextual_chunker.py`.

**Validation**: Index 10 docs, query ChromaDB, verify chunks have context prefixes and metadata contains original_text.


## Phase 4: BM25 Hybrid Search (Est: 4-6h)

**Why**: Vector-only search misses exact matches for CyberArk-specific terms. Adding BM25 with Reciprocal Rank Fusion reduces retrieval failures by 49% (Anthropic research).

Create `cyberark_rag/bm25_index.py` and `cyberark_rag/hybrid_search.py`. Full spec in `.claude/rules/search-indexing.md`.

Modify `cyberark_rag/indexer.py`: after ChromaDB indexing, build and save BM25 index.

Modify `cyberark_rag/search.py`:
- Load BM25 index at init (lazy)
- New `hybrid_search` method: vector (top_k*3) + BM25 (top_k*3) -> fuse -> take top_k
- `search()` gains `use_hybrid: bool = True` parameter
- Intent re-ranking still applies after fusion
- Return `original_text` in results for display

Create `tests/test_bm25.py` and `tests/test_hybrid_search.py`.

**Validation**: `python -m cyberark_rag search "PVWA error 401"` returns relevant exact-match results. pytest passes.


## Phase 5: MCP Server Modernization (Est: 3-4h)

**Why**: Low-level Server class requires manual schema definition and protocol handling. FastMCP auto-generates schemas from Pydantic models and handles all protocol negotiation.

Rewrite `cyberark_rag/mcp_server.py`. Full spec in `.claude/rules/mcp-server.md`.

Update `mcp_config.json` for new entry point.

Create `tests/test_mcp_server.py`.

**Validation**: Start server, verify all four tools appear with correct schemas. pytest passes.


## Phase 6: Testing & Docs (Est: 2-3h)

Migrate any remaining custom tests to pytest. Create `tests/conftest.py` with session-scoped fixtures.

Create `scripts/update.sh` (incremental scrape + re-index) and `scripts/full_rebuild.sh` (full scrape + clean rebuild).

Update `README.md` with architecture diagram, install instructions, quick start, env var table, tool reference.

**Validation**: `pytest -v` passes all tests. Scripts run without error. README is accurate.


## Phase 7: Embedding Model Upgrade (Optional, Est: 1h + re-index time)

**Why**: `all-MiniLM-L6-v2` (384 dims) is in the lower tier for retrieval accuracy. `BAAI/bge-large-en-v1.5` (1024 dims) is significantly better.

This is a drop-in replacement via the `CYBERARK_RAG_MODEL` env var. Requires full re-index since embedding dimensions change. Index size grows ~3x but runs fine on M1 Max.

Alternative middle ground: `BAAI/bge-base-en-v1.5` (768 dims).


## Phase 8: LLM-Powered Contextual Retrieval (Optional, Est: 4-6h)

**Why**: Upgrade from metadata-derived prefixes (35% improvement) to Claude Haiku-generated context (49-67% improvement). Requires Anthropic API key.

Add `ANTHROPIC_API_KEY` env var support. Use prompt caching for cost efficiency (~$1.02/M tokens). Add async batch processing in indexer.

This is the highest-impact single improvement but has an external dependency (API key + cost).
