# Architecture Reference

This file gives you the ground truth about how the system works. Use it to write accurate documentation. Do not guess about behavior; if something is unclear, read the source file.

## System Components

### Scraper Layer

**incremental_scraper.py** (project root)
- Parses docs.cyberark.com/sitemap.xml (handles sitemap index recursion up to depth 3)
- Tracks state in scraper_state.json: {last_run, pages: {url: {lastmod, content_hash, scraped_at}}}
- Incremental mode: only fetches pages where sitemap lastmod > stored lastmod
- Full mode: re-scrapes all valid URLs
- Dry-run mode: prints what would change without fetching
- URL validation: must be docs.cyberark.com, skips .pdf/.zip/.png/.jpg/.gif/.svg/.css/.js
- Page extraction: finds main/article/content div, strips script/style/nav, normalizes whitespace
- Output: JSON files in scraped_docs/ matching format {url, title, content, scraped_at}
- User-Agent: CyberArkRAGBot/2.0
- Default delay: 0.5s between requests

**scraper.py** (project root, legacy)
- Original BFS crawler, preserved but not recommended
- 1.5s delay, no state tracking, no sitemap support
- Takes 8+ hours for full crawl

### Indexing Layer

**cyberark_rag/indexer.py**
- DocumentIndexer class
- Loads all *.json from scraped_docs/
- Extracts product_category from URL path (first meaningful segment after domain)
- Chunks text using paragraph-aware splitting with tiktoken tokenizer
- Default: 800 tokens per chunk, 100 token overlap
- After chunking, calls contextualize_chunks() to add metadata-derived prefixes
- Embeds contextualized text using sentence-transformers model
- Stores in ChromaDB (persistent, collection: cyberark_docs)
- Also builds BM25 index from same contextualized text
- Metadata per chunk: url, title, product_category, chunk_index, content_type, original_text, context_prefix

**cyberark_rag/contextual_chunker.py**
- build_chunk_context(): creates deterministic prefix from URL, title, product, nearest heading, version
- Prefix format: "From CyberArk {Product} documentation, page titled '{Title}', in the section about {Heading}, (version {X.Y}). "
- _extract_nearest_heading(): regex search backward for markdown headers or title-case lines
- _extract_version(): finds version from URL path segments (e.g., "14.2", "v12", "Latest")
- contextualize_chunks(): wraps all chunks, stores original_text in metadata, returns prefixed text for embedding
- Includes docstring documenting LLM-powered upgrade path with Anthropic's exact prompt

**cyberark_rag/bm25_index.py**
- BM25Index class implementing Okapi BM25 (k1=1.5, b=0.75)
- Tokenizer preserves hyphenated terms: regex r"\b[\w][\w\-]*[\w]\b|\b\w\b"
- Inverted index with term frequencies per document
- Product filtering at search time
- Persistence via pickle (save/load to bm25_index.pkl)

### Search Layer

**cyberark_rag/search.py**
- DocumentSearcher class (singleton pattern)
- Lazy-loads ChromaDB collection and BM25 index
- Search pipeline:
  1. Query expansion (query_expansion.py)
  2. Intent detection (query_intent.py)
  3. Vector search: encode query, ChromaDB cosine similarity, top_k * 3 results
  4. BM25 search: tokenize query, BM25 scoring, top_k * 3 results
  5. Reciprocal Rank Fusion (hybrid_search.py)
  6. Intent-based re-ranking
  7. Return top_k results with original_text (not prefixed text)

**cyberark_rag/hybrid_search.py**
- hybrid_search(): Reciprocal Rank Fusion
- Formula: score = sum(weight / (k + rank + 1)) per result list
- Default: vector_weight=0.7, bm25_weight=0.3, k=60
- Deduplicates by (url, chunk_index) tuple

**cyberark_rag/query_expansion.py**
- QueryExpander class (singleton)
- Loads 80+ expansion groups from query_expansions.yaml
- Matches query tokens against groups, adds up to 5 synonyms per match
- Expansion terms weighted 0.7x vs 1.0x for original query
- Includes typo correction (priviledge -> privilege, authentification -> authentication)

**cyberark_rag/query_intent.py**
- QueryIntentDetector class (singleton)
- 5 intent types: how-to, explanation, reference, troubleshooting, general
- Regex-based detection
- Returns boost multipliers per content_type for each intent

**cyberark_rag/content_classifier.py**
- classify_content_primary(): classifies chunk text into procedural, conceptual, reference, code-example
- Uses regex patterns (step indicators, code blocks, table markers, conceptual language)
- URL signals influence classification (e.g., /reference/ -> reference, /tutorial/ -> procedural)

**cyberark_rag/product_aliases.py**
- ProductAliasResolver class (singleton)
- Loads product_aliases.yaml: 22+ canonical products with 60+ aliases
- Maps raw URL-derived categories to canonical names with display names
- Categories: product, deprecated, metadata, navigation

### MCP Server Layer

**cyberark_rag/mcp_server.py**
- FastMCP("cyberark_rag_mcp") server
- stdio transport (JSON-RPC over stdin/stdout)
- All logging to stderr (stdout is protocol)
- 4 tools:
  - cyberark_rag_search_docs: hybrid search with query, top_k, product_filter, use_hybrid_search params
  - cyberark_rag_get_command_example: searches for CLI/API/config examples by product + task
  - cyberark_rag_list_products: returns all product categories with filter keys
  - cyberark_rag_get_index_stats: total chunks, products, last build time, BM25 status
- All tools: readOnlyHint=True, destructiveHint=False, idempotentHint=True
- Pydantic input models for search and command_example tools
- Lazy-loads DocumentSearcher on first tool call

### Terminal Layer

**cyberark_rag/terminal.py**
- Natural language terminal assistant
- Sends user query to MCP server (subprocess), gets documentation context
- Sends context + query to Ollama LLM
- LLM generates shell command
- User confirms before execution

**bin/cyai**
- CLI entry point for terminal assistant
- Shebang: #!/usr/bin/env python3
- Flags: --auto, --show-context, --config

### Configuration Layer

**cyberark_rag/config.py**
- Settings class with PROJECT_ROOT, DOCS_DIR, DB_DIR, BM25_PATH, STATE_FILE
- EMBEDDING_MODEL, COLLECTION_NAME, CHUNK_SIZE, CHUNK_OVERLAP
- All paths from env vars with defaults relative to PROJECT_ROOT

**cyberark_rag/logging_config.py**
- setup_logging(): returns Logger with stderr-only StreamHandler
- Format: %(asctime)s [%(levelname)s] %(name)s: %(message)s

## File Tree

```
cyberark-rag/
├── README.md
├── requirements.txt
├── pyproject.toml
├── incremental_scraper.py          # Sitemap-driven scraper
├── scraper.py                      # Legacy BFS scraper
├── scraper_state.json              # Scraper state (auto-generated)
├── config.yaml                     # Terminal assistant config
├── mcp_config.json                 # Claude Desktop MCP config
├── product_aliases.yaml            # Product name mappings
├── query_expansions.yaml           # Search term expansions
├── scripts/
│   ├── update.sh                   # Incremental scrape + re-index
│   └── full_rebuild.sh             # Full scrape + clean rebuild
├── bin/
│   └── cyai                        # Terminal assistant CLI
├── shell/
│   └── zshrc_integration.sh        # Shell completions
├── cyberark_rag/
│   ├── __init__.py
│   ├── __main__.py                 # CLI router
│   ├── config.py                   # Settings
│   ├── logging_config.py           # Stderr logging
│   ├── indexer.py                  # Chunking + embedding + ChromaDB
│   ├── contextual_chunker.py       # Anthropic contextual prefixes
│   ├── bm25_index.py               # BM25 keyword index
│   ├── hybrid_search.py            # Reciprocal Rank Fusion
│   ├── search.py                   # Search pipeline orchestrator
│   ├── query_expansion.py          # Term expansion
│   ├── query_intent.py             # Intent detection
│   ├── content_classifier.py       # Content type classification
│   ├── product_aliases.py          # Product alias resolution
│   ├── mcp_server.py               # FastMCP server
│   └── terminal.py                 # Ollama terminal assistant
├── tests/                          # pytest suite
├── scraped_docs/                   # ~19,378 JSON files (not in git)
├── chroma_db/                      # ChromaDB storage (not in git)
└── bm25_index.pkl                  # BM25 index (not in git)
```
