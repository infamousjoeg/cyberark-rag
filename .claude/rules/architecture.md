# Architecture

## Current Pipeline

```
docs.cyberark.com
    | scraper.py (BFS crawler, 8+ hours, no change detection)
scraped_docs/ (~19,378 JSON files)
    | indexer.py (paragraph chunking -> embed -> ChromaDB)
chroma_db/
    | search.py (vector-only search + intent re-ranking)
mcp_server.py (low-level MCP Server class, 3 tools, stdio)
    |
Claude Desktop integration
```

## Target Pipeline

```
docs.cyberark.com/sitemap.xml
    | incremental_scraper.py (sitemap-driven, 2-10 min updates)
scraped_docs/ (~19,378 JSON files, same format)
    | indexer.py (contextual chunking -> embed -> ChromaDB + BM25)
chroma_db/ + bm25_index.pkl
    | search.py (hybrid vector+BM25 -> rank fusion -> intent re-ranking)
mcp_server.py (FastMCP, 4 tools, Pydantic schemas, stdio)
    |
Claude Desktop / Claude Code integration
```

## Critical Files

- `cyberark_rag/config.py` -- NEW: central configuration (all paths, env vars)
- `cyberark_rag/logging_config.py` -- NEW: stderr-only logging setup
- `cyberark_rag/contextual_chunker.py` -- NEW: Anthropic contextual retrieval
- `cyberark_rag/bm25_index.py` -- NEW: BM25 keyword index + tokenizer
- `cyberark_rag/hybrid_search.py` -- NEW: reciprocal rank fusion
- `cyberark_rag/indexer.py` -- MODIFY: add contextual chunks + BM25 build
- `cyberark_rag/search.py` -- MODIFY: hybrid search pipeline
- `cyberark_rag/mcp_server.py` -- REWRITE: FastMCP + Pydantic
- `incremental_scraper.py` -- NEW: sitemap-driven scraper (project root)

## Dependencies (add to requirements.txt)

```
mcp[cli]>=1.0.0
pydantic>=2.0.0
lxml>=5.1.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
```

## Research References

- Anthropic Contextual Retrieval: https://www.anthropic.com/news/contextual-retrieval
  - 49% fewer retrieval failures with BM25 + embeddings
  - 67% fewer failures adding reranking
  - Contextual chunk prefixes: 35% improvement alone
- MCP Spec (2025-06-18): tool annotations (readOnlyHint, destructiveHint, idempotentHint, openWorldHint)
- FastMCP: automatic schema generation from Pydantic models, replaces low-level Server class
