# CyberArk RAG MCP Server

Python 3.13 project on macOS (M1 Max). Retrieval-Augmented Generation system that scrapes docs.cyberark.com, indexes into ChromaDB, and serves search via MCP for Claude Desktop/Code integration.

See @.claude/rules/architecture.md for system design.
See @.claude/rules/implementation-phases.md for the full improvement roadmap.
See @cyberark-rag-tasks.md for the current task checklist.

## Commands

```bash
# Scraping
python incremental_scraper.py              # incremental update (sitemap-driven)
python incremental_scraper.py --full       # full re-scrape
python incremental_scraper.py --dry-run    # preview what would change

# Indexing
python -m cyberark_rag index               # rebuild index from scraped_docs/

# Search (test)
python -m cyberark_rag search "configure conjur kubernetes"
python -m cyberark_rag search --stats      # index health check

# MCP Server
python -m cyberark_rag.mcp_server          # stdio transport for Claude Desktop

# Testing
pytest -v                                  # run all tests
pytest tests/test_bm25.py -v              # run specific test module
```

## Code Style

- Python: type hints on all functions, docstrings on all public methods, f-strings over .format()
- No hardcoded absolute paths. Use `cyberark_rag/config.py` Settings class with env var overrides
- All logging to stderr, never stdout (stdout is MCP JSON-RPC)
- No em-dashes in any text, comments, or documentation
- Prefer `pathlib.Path` over `os.path`
- Imports: stdlib, blank line, third-party, blank line, local

## Key Conventions

- Existing `scraped_docs/` JSON format is sacred: `{url, title, content, scraped_at}` -- do not change
- ChromaDB collection name: `cyberark_docs` -- do not change
- MCP tool names: prefix with `cyberark_rag_` to prevent collisions
- Embedding dimension changes require full re-index
- BM25 tokenizer must preserve hyphens in compound terms (e.g., "privilege-cloud", "AAM-DAP")
- CyberArk brand colors: Navy #0f1f3c, Cobalt #0047ab, Ice #a3e5f5, Chartreuse #d4f000, Sand #e8e4de

## Workflow Rules

- Commit after each completed phase with a descriptive message
- Run `pytest -v` after every code change before moving to next phase
- Run `grep -rn "/Users/" .` after Phase 1 and confirm zero results
- After modifying search.py or indexer.py, test with: `python -m cyberark_rag search "PVWA error 401"`
- After modifying mcp_server.py, verify tools list with: `python -m cyberark_rag.mcp_server` (check JSON-RPC output)

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `CYBERARK_RAG_DOCS` | `./scraped_docs` | Scraped docs directory |
| `CYBERARK_RAG_DB` | `./chroma_db` | ChromaDB storage |
| `CYBERARK_RAG_MODEL` | `all-MiniLM-L6-v2` | Sentence-transformer model |
| `CYBERARK_RAG_CHUNK_SIZE` | `500` | Tokens per chunk |
| `CYBERARK_RAG_CHUNK_OVERLAP` | `100` | Overlap between chunks |
