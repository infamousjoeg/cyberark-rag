# CyberArk RAG Improvement Tasks

Track progress by marking items `[x]` as completed. Commit after each phase.

## Phase 1: Foundation
- [x] Create `cyberark_rag/config.py` with Settings class
- [x] Create `cyberark_rag/logging_config.py` with stderr-only logging
- [x] Update `indexer.py` to use config.py
- [x] Update `search.py` to use config.py
- [x] Update `mcp_server.py` to use config.py
- [x] Update `product_aliases.py` to use config.py
- [x] Update `query_expansion.py` to use config.py
- [x] Update `terminal.py` to use config.py
- [x] Fix `config.yaml` hardcoded python path
- [x] Fix `mcp_config.json` hardcoded paths
- [x] Fix `bin/cyai` shebang
- [x] Verify: `grep -rn "/Users/joe" .` returns nothing
- [ ] Commit: "refactor: centralize config, remove hardcoded paths"

## Phase 2: Incremental Scraper
- [x] Create `incremental_scraper.py` with sitemap parsing
- [x] Implement state tracking in `scraper_state.json`
- [x] Implement incremental/full/dry-run modes
- [x] Create `tests/test_incremental_scraper.py`
- [x] Verify: `--dry-run` discovers URLs
- [ ] Commit: "feat: add sitemap-driven incremental scraper"

## Phase 3: Contextual Retrieval
- [x] Create `cyberark_rag/contextual_chunker.py`
- [x] Modify `indexer.py` to call `contextualize_chunks()` after chunking
- [x] Store `original_text` in metadata, embed prefixed version
- [x] Include LLM-upgrade docstring block
- [x] Create `tests/test_contextual_chunker.py`
- [x] Verify: indexed chunks have context prefixes
- [ ] Commit: "feat: add contextual retrieval chunk enrichment"

## Phase 4: BM25 Hybrid Search
- [x] Create `cyberark_rag/bm25_index.py` with Okapi BM25
- [x] Create `cyberark_rag/hybrid_search.py` with RRF
- [x] Modify `indexer.py` to build BM25 index after ChromaDB
- [x] Modify `search.py` for hybrid search pipeline
- [x] Create `tests/test_bm25.py`
- [x] Create `tests/test_hybrid_search.py`
- [x] Verify: "PVWA error 401" returns exact-match results
- [ ] Commit: "feat: add BM25 hybrid search with rank fusion"

## Phase 5: MCP Server Modernization
- [x] Rewrite `mcp_server.py` with FastMCP + Pydantic
- [x] Implement all four `cyberark_rag_*` tools with annotations
- [x] Update `mcp_config.json`
- [x] Create `tests/test_mcp_server.py`
- [x] Verify: all four tools appear with correct schemas
- [ ] Commit: "feat: migrate MCP server to FastMCP with Pydantic"

## Phase 6: Testing & Documentation
- [x] Create `tests/conftest.py` with session-scoped fixtures
- [x] Create `tests/test_search.py` (replaces test_mcp.py)
- [x] Add pytest config to `pyproject.toml`
- [x] Update `requirements.txt` with new dependencies
- [x] Create `scripts/update.sh`
- [x] Create `scripts/full_rebuild.sh`
- [x] Update `README.md`
- [x] Verify: `pytest -v` all green
- [ ] Commit: "test: migrate to pytest, add automation scripts"

## Optional Phases
- [ ] Phase 7: Switch embedding model to `BAAI/bge-large-en-v1.5`
- [ ] Phase 8: Add LLM-powered contextual retrieval with Claude Haiku
