# Configuration

Every configurable parameter in the system, organized by component.

## Environment Variables

| Variable | Type | Default | Description |
|---|---|---|---|
| `CYBERARK_RAG_DOCS` | path | `./scraped_docs` | Directory containing scraped JSON files |
| `CYBERARK_RAG_DB` | path | `./chroma_db` | ChromaDB persistent storage directory |
| `CYBERARK_RAG_MODEL` | string | `BAAI/bge-large-en-v1.5` | sentence-transformers model name |
| `CYBERARK_RAG_CHUNK_SIZE` | int | `800` | Target tokens per chunk |
| `CYBERARK_RAG_CHUNK_OVERLAP` | int | `100` | Overlap tokens between adjacent chunks |
| `ANTHROPIC_API_KEY` | string | (none) | Optional: enables LLM-powered contextual retrieval |

Override any variable by exporting it before running commands:

```bash
export CYBERARK_RAG_MODEL="all-MiniLM-L6-v2"
python -m cyberark_rag index
```

All settings are managed by the `Settings` class in `cyberark_rag/config.py`. Paths default to locations relative to the project root.

## config.yaml

Configuration for the terminal assistant (`cyai`). Located at the project root.

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

### Key Settings

| Key | Default | Description |
|---|---|---|
| `ollama.endpoint` | `http://localhost:11434` | Where Ollama is running |
| `ollama.model` | `llama3.1` | Ollama model for command generation. Options: `llama3.1`, `llama3.2`, `codellama`, `mistral` |
| `mcp.python_path` | `python3` | Python interpreter with cyberark_rag installed |
| `mcp.max_context_chunks` | `3` | More chunks = better context, slower generation. Range: 1-10 |
| `execution.auto_execute` | `false` | Skip confirmation prompt. Use only in trusted environments |
| `execution.show_context` | `false` | Display documentation context before the generated command |

## mcp_config.json

MCP server configuration for Claude Desktop. Copy the relevant section into your Claude Desktop config file.

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Linux**: `~/.config/claude/claude_desktop_config.json`

### Using a virtual environment (recommended)

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

### Using system Python with PYTHONPATH

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

Replace `/path/to/cyberark-rag` with the actual path to your project directory.

## product_aliases.yaml

Maps raw URL-derived product categories to canonical names. Loaded by `ProductAliasResolver` at query time (no re-index needed when modified).

### Structure

```yaml
canonical-product-name:
  display_name: "Human Readable Name"
  category: product          # product | deprecated | metadata | navigation
  description: "Short description"
  aliases:
    - alias-one
    - alias-two
    - AliasThree             # resolved case-insensitively
```

### Categories

| Category | Meaning |
|---|---|
| `product` | Active CyberArk product (shown in search filters) |
| `deprecated` | Retired product name (still resolved for old docs) |
| `metadata` | Non-product page category (release notes, etc.) |
| `navigation` | Site navigation artifact (skip during search) |

### Adding a New Product

1. Add a new block to `product_aliases.yaml`:

```yaml
new-product:
  display_name: "New Product Name"
  category: product
  description: "What this product does"
  aliases:
    - np
    - new-prod
    - NewProduct
```

2. No re-index needed. Alias resolution happens at query time.

## query_expansions.yaml

Maps related terms so queries automatically include synonyms. Loaded by `QueryExpander` at query time.

### Structure

```yaml
primary_term:
  - alias1
  - alias2
  # All terms in a group are treated as related
```

When any term in a group matches a query token, the other terms are added to the expanded query at 0.7x weight (vs 1.0x for the original query). A maximum of 5 expansion terms are added per match.

### Examples

```yaml
spire:
  - spiffe
  - svid
  - workload-identity

kubernetes:
  - k8s
  - openshift
  - eks
  - aks
  - gke
```

### Adding a New Expansion Group

Add a new primary term with its aliases. No re-index needed; expansion happens at query time.

## Embedding Model Selection

| Model | Dimensions | Download | Index Size* | Quality |
|---|---|---|---|---|
| `all-MiniLM-L6-v2` | 384 | ~80 MB | ~1.2 GB | Good |
| `BAAI/bge-base-en-v1.5` | 768 | ~420 MB | ~2.4 GB | Better |
| `BAAI/bge-large-en-v1.5` | 1024 | ~1.3 GB | ~3.8 GB | Best |

*Index size for ~19K docs with ~50K chunks.

Switching models requires a full re-index because embedding dimensions change:

```bash
export CYBERARK_RAG_MODEL="BAAI/bge-large-en-v1.5"
rm -rf chroma_db/ bm25_index.pkl
python -m cyberark_rag index
```

BGE models use a query instruction prefix for retrieval that sentence-transformers handles automatically.

## BM25 Parameters

Set in `cyberark_rag/bm25_index.py` constructor. These are compile-time constants; changing them requires rebuilding the BM25 index.

| Parameter | Default | Range | Description |
|---|---|---|---|
| `k1` | 1.5 | 1.0-2.0 | Term frequency saturation. Higher values give more credit for repeated terms. 1.5 works well for CyberArk's domain-specific terminology. |
| `b` | 0.75 | 0.0-1.0 | Document length normalization. 0 = no length penalty, 1 = full normalization. Lower this if short docs dominate results unfairly. |

## Hybrid Search Weights

Set in `cyberark_rag/hybrid_search.py`. Applied at query time (no re-index needed).

| Parameter | Default | Description |
|---|---|---|
| `vector_weight` | 0.7 | Weight for semantic similarity results in RRF |
| `bm25_weight` | 0.3 | Weight for keyword match results in RRF |
| `k` | 60 | RRF constant. Higher = more equal ranking across positions. 60 is Azure AI Search's default. |

### Tuning Guidance

- If exact-match queries (error codes, parameter names) return poorly: increase `bm25_weight` to 0.4-0.5
- If conceptual queries ("how does authentication work") return poorly: increase `vector_weight` to 0.8
- These should sum to 1.0 (not enforced in code, but recommended)

## Intent Boost Matrix

Applied after Reciprocal Rank Fusion, before final top_k selection. Content type is assigned during indexing by the `ContentClassifier`.

| Intent \ Content | procedural | conceptual | reference | code-example |
|---|---|---|---|---|
| how-to | 2.0x | 0.8x | 1.0x | 1.5x |
| explanation | 0.8x | 2.0x | 1.2x | 0.8x |
| reference | 1.0x | 0.8x | 2.0x | 1.5x |
| troubleshooting | 1.5x | 0.8x | 1.2x | 2.0x |
| general | 1.0x | 1.0x | 1.0x | 1.0x |
