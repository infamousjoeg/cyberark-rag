# Configuration Reference

Exhaustive list of every configurable parameter. Use this to write docs/configuration.md accurately.

## Environment Variables

| Variable | Type | Default | Description |
|---|---|---|---|
| `CYBERARK_RAG_DOCS` | path | `./scraped_docs` | Directory containing scraped JSON files |
| `CYBERARK_RAG_DB` | path | `./chroma_db` | ChromaDB persistent storage directory |
| `CYBERARK_RAG_MODEL` | string | `all-MiniLM-L6-v2` | sentence-transformers model name |
| `CYBERARK_RAG_CHUNK_SIZE` | int | `800` | Target tokens per chunk |
| `CYBERARK_RAG_CHUNK_OVERLAP` | int | `100` | Overlap tokens between adjacent chunks |
| `ANTHROPIC_API_KEY` | string | (none) | Optional: enables LLM-powered contextual retrieval |

## config.yaml (Terminal Assistant)

```yaml
# Ollama LLM for terminal command generation
ollama:
  endpoint: http://localhost:11434   # Ollama API endpoint
  model: llama3.1                     # Model name (must be pulled: ollama pull llama3.1)

# MCP server connection
mcp:
  python_path: python3                # Python interpreter (must have cyberark_rag installed)
  max_context_chunks: 3               # Number of search results sent to LLM as context

# Command execution behavior
execution:
  auto_execute: false                 # If true, runs generated commands without confirmation
  show_context: false                 # If true, displays retrieved doc chunks before command
```

## mcp_config.json (Claude Desktop)

macOS location: `~/Library/Application Support/Claude/claude_desktop_config.json`
Linux location: `~/.config/claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "cyberark-rag": {
      "command": "python3",
      "args": ["-m", "cyberark_rag.mcp_server"],
      "env": {
        "PYTHONPATH": "/path/to/cyberark-rag"
      },
      "disabled": false
    }
  }
}
```

For venv installs, use the venv python:
```json
{
  "mcpServers": {
    "cyberark-rag": {
      "command": "/path/to/cyberark-rag/.venv/bin/python3",
      "args": ["-m", "cyberark_rag.mcp_server"],
      "disabled": false
    }
  }
}
```

## product_aliases.yaml Structure

```yaml
canonical-product-name:
  display_name: "Human Readable Name"
  category: product          # product | deprecated | metadata | navigation
  description: "Short description"
  aliases:
    - alias-one
    - alias-two
    - AliasThree             # case-sensitive in YAML, resolved case-insensitively
```

22 canonical products. Adding a new one:
1. Add the block above
2. All aliases map to the canonical name during search
3. No re-index needed (alias resolution is at query time)

## query_expansions.yaml Structure

```yaml
groups:
  - terms:
      - spire
      - spiffe
      - svid
      - workload-identity
    category: machine-identity

  - terms:
      - kubernetes
      - k8s
      - openshift
      - eks
      - aks
      - gke
    category: platforms
```

80+ groups. When any term in a group matches a query token, the other terms in the group are added to the expanded query at 0.7x weight (up to 5 additions per match).

Adding a new expansion:
1. Add a new group with related terms
2. No re-index needed (expansion is at query time)

## Embedding Model Options

| Model | Dimensions | Download | Index Size* | Quality |
|---|---|---|---|---|
| `all-MiniLM-L6-v2` | 384 | ~80 MB | ~1.2 GB | Good |
| `BAAI/bge-base-en-v1.5` | 768 | ~420 MB | ~2.4 GB | Better |
| `BAAI/bge-large-en-v1.5` | 1024 | ~1.3 GB | ~3.8 GB | Best |

*Index size for ~19K docs with ~50K chunks.

Switching models requires:
1. Set `CYBERARK_RAG_MODEL=BAAI/bge-large-en-v1.5`
2. Delete `chroma_db/` and `bm25_index.pkl`
3. Run `python -m cyberark_rag index`

BGE models use a query instruction prefix for retrieval that sentence-transformers handles automatically.

## BM25 Parameters

Set in `cyberark_rag/bm25_index.py` constructor:

| Parameter | Default | Range | Effect |
|---|---|---|---|
| `k1` | 1.5 | 1.0-2.0 | Term frequency saturation. Higher = more credit for repeated terms. 1.5 works well for CyberArk's domain-specific terminology. |
| `b` | 0.75 | 0.0-1.0 | Document length normalization. 0 = no length penalty, 1 = full normalization. 0.75 is standard. Lower if short docs dominate results unfairly. |

## Hybrid Search Weights

Set in `cyberark_rag/hybrid_search.py`:

| Parameter | Default | Effect |
|---|---|---|
| `vector_weight` | 0.7 | Weight for semantic similarity results in RRF |
| `bm25_weight` | 0.3 | Weight for keyword match results in RRF |
| `k` | 60 | RRF constant. Higher = more equal ranking across positions. 60 is Microsoft Azure AI Search's default. |

Tuning guidance:
- If exact-match queries (error codes, parameter names) return poorly: increase bm25_weight to 0.4-0.5
- If conceptual queries ("how does authentication work") return poorly: increase vector_weight to 0.8
- These must sum to 1.0 (not enforced in code, but recommended)

## Scraper CLI Flags

| Flag | Default | Description |
|---|---|---|
| `--full` | false | Force re-scrape of all URLs regardless of state |
| `--dry-run` | false | Show what would be scraped without fetching |
| `--delay` | 0.5 | Seconds between HTTP requests |
| `--output-dir` | `scraped_docs` | Directory for output JSON files |

## MCP Tool Parameters

### cyberark_rag_search_docs
| Parameter | Type | Default | Constraints | Description |
|---|---|---|---|---|
| `query` | string | (required) | non-empty | Search query |
| `top_k` | int | 5 | 1-20 | Number of results |
| `product_filter` | string | null | valid product key | Filter by product |
| `use_hybrid_search` | bool | true | | Enable BM25 + vector fusion |

### cyberark_rag_get_command_example
| Parameter | Type | Default | Description |
|---|---|---|---|
| `product` | string | (required) | Product name (e.g., "Conjur", "PAM") |
| `task` | string | (required) | Task description (e.g., "authenticate", "rotate credentials") |

### cyberark_rag_list_products
No parameters.

### cyberark_rag_get_index_stats
No parameters. Returns: total_chunks, unique_products, indexed_at, embedding_model, bm25_available.

## Intent Boost Matrix

| Intent \ Content | procedural | conceptual | reference | code-example |
|---|---|---|---|---|
| how-to | 2.0x | 0.8x | 0.8x | 1.5x |
| explanation | 0.8x | 2.0x | 1.0x | 0.8x |
| reference | 0.8x | 0.8x | 2.0x | 1.5x |
| troubleshooting | 1.5x | 1.0x | 1.0x | 1.5x |
| general | 1.0x | 1.0x | 1.0x | 1.0x |

These multipliers are applied after Reciprocal Rank Fusion, before final top_k selection.
