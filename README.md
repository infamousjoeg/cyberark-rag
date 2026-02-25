# CyberArk Documentation RAG

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![MCP Compatible](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io)

Semantic search over CyberArk's complete product documentation, powered by hybrid vector + BM25 retrieval and served via MCP for Claude Desktop and Claude Code.

## Features

- **Hybrid search** combining vector embeddings and BM25 keyword matching with Reciprocal Rank Fusion
- **Contextual chunk enrichment** using [Anthropic's Contextual Retrieval](https://www.anthropic.com/news/contextual-retrieval) technique (35% fewer retrieval failures)
- **Incremental documentation updates** via sitemap parsing (minutes, not hours)
- **4 MCP tools** for seamless Claude Desktop and Claude Code integration
- **Query expansion** with 80+ CyberArk-specific term groups (SPIFFE/SPIRE, K8s/OpenShift, etc.)
- **Intent-aware re-ranking** that boosts results matching query intent (how-to, reference, troubleshooting, explanation)
- **22+ CyberArk products** covered: Privilege Cloud, Conjur Cloud/Enterprise, Secrets Manager, Secrets Hub, EPM, Identity, DPA, Secure Workload Access, and more

## Quick Start

```bash
# 1. Clone and set up
git clone https://github.com/infamousjoeg/cyberark-rag.git
cd cyberark-rag
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Scrape documentation (preview first)
python incremental_scraper.py --dry-run
python incremental_scraper.py --full          # first run: 2-4 hours

# 3. Build the search index
python -m cyberark_rag index

# 4. Test a search
python -m cyberark_rag search "configure conjur kubernetes authenticator"

# 5. Connect to Claude Code
claude mcp add cyberark-rag -- python3 -m cyberark_rag.mcp_server
```

See [Getting Started](docs/getting-started.md) for the full walkthrough.

## Architecture

```
docs.cyberark.com/sitemap.xml
    | incremental_scraper.py (sitemap-driven, 2-10 min updates)
scraped_docs/ (~19,378 JSON files, same format)
    | indexer.py (contextual chunking -> embed -> ChromaDB + BM25)
chroma_db/ + bm25_index.pkl
    | search.py (hybrid vector+BM25 -> rank fusion -> intent re-ranking)
mcp_server.py (FastMCP, 4 tools, Pydantic schemas, stdio)
    |
Claude Desktop / Claude Code
```

See [Architecture](docs/architecture.md) for the full system design.

## MCP Tools

| Tool | Description | Key Parameters |
|---|---|---|
| `search_cyberark_docs` | Hybrid semantic + keyword search | `query`, `top_k`, `product_filter`, `use_hybrid_search` |
| `get_command_example` | Find CLI/API/config examples | `product`, `task` |
| `list_products` | List available product categories | (none) |
| `get_index_stats` | Index health and statistics | (none) |

See [MCP Integration](docs/mcp-integration.md) for setup instructions.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `CYBERARK_RAG_DOCS` | `./scraped_docs` | Scraped docs directory |
| `CYBERARK_RAG_DB` | `./chroma_db` | ChromaDB storage |
| `CYBERARK_RAG_MODEL` | `BAAI/bge-large-en-v1.5` | Sentence-transformer model |
| `CYBERARK_RAG_CHUNK_SIZE` | `800` | Tokens per chunk |
| `CYBERARK_RAG_CHUNK_OVERLAP` | `100` | Overlap between chunks |

See [Configuration](docs/configuration.md) for all options.

## Documentation

- [Getting Started](docs/getting-started.md) -- Zero-to-working in 10 minutes
- [Architecture](docs/architecture.md) -- System design, data flow, module map
- [Configuration](docs/configuration.md) -- Every env var, YAML key, CLI flag
- [Scraper Guide](docs/scraper-guide.md) -- Incremental vs full scrape, automation
- [Indexing Guide](docs/indexing-guide.md) -- Contextual chunking, BM25, embedding models
- [MCP Integration](docs/mcp-integration.md) -- Claude Desktop + Claude Code setup
- [Search Pipeline](docs/search-pipeline.md) -- Query expansion, hybrid search, re-ranking
- [Troubleshooting](docs/troubleshooting.md) -- Common errors, diagnostics, FAQ
- [Contributing](docs/contributing.md) -- Dev setup, testing, PR workflow
- [Changelog](docs/changelog.md) -- Version history

## Contributing

See [Contributing](docs/contributing.md) for development setup, testing, and PR guidelines.

## License

MIT
