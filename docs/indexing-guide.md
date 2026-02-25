# Indexing Guide

Building and maintaining the search index.

## Quick Index Build

```bash
$ python -m cyberark_rag index
Loading documents from scraped_docs/...
Loaded 19,378 documents
Chunking documents...
Created 52,847 chunks (800 tokens, 100 overlap)
Contextualizing chunks...
Building embeddings and indexing to ChromaDB...
Building BM25 index...
Done. 52,847 chunks indexed in 8m 32s.
```

Expected timing: 5-15 minutes depending on CPU, embedding model, and document count.

## What Happens During Indexing

### Step 1: Load JSON Files

The indexer reads all `*.json` files from `scraped_docs/`. Each file must contain `{url, title, content, scraped_at}`.

### Step 2: Chunk Text

Text is split into chunks using paragraph-aware boundaries:

- Target: 800 tokens per chunk (configurable via `CYBERARK_RAG_CHUNK_SIZE`)
- Overlap: 100 tokens between adjacent chunks (configurable via `CYBERARK_RAG_CHUNK_OVERLAP`)
- Token counting uses the `cl100k_base` tiktoken encoding
- The chunker prefers splitting at paragraph boundaries (`\n\n`), falling back to sentence boundaries for long paragraphs

### Step 3: Contextualize Chunks

Each chunk receives a metadata-derived prefix via `contextual_chunker.py`:

```
From CyberArk {Product} documentation, page titled '{Title}',
in the section about {Heading}, (version {Version}).
```

The prefix is built from:
- **Product**: Resolved from URL path via `product_aliases.yaml`
- **Title**: Page title from the scraped JSON
- **Heading**: Nearest markdown header or title-case line found above the chunk in the source document
- **Version**: Extracted from URL path segments (e.g., "14.2", "Latest")

### Step 4: Embed into ChromaDB

The contextualized text (prefix + original content) is embedded using the configured sentence-transformers model and stored in ChromaDB with metadata:

| Field | Description |
|---|---|
| `url` | Source document URL |
| `title` | Page title |
| `product_category` | Canonical product name |
| `chunk_index` | Position within the document |
| `content_type` | procedural, conceptual, reference, or code-example |
| `original_text` | Uncontextualized chunk text |
| `context_prefix` | The metadata-derived prefix |

### Step 5: Build BM25 Index

The same contextualized text is tokenized (preserving hyphenated terms like "privilege-cloud" and "AAM-DAP") and added to an Okapi BM25 inverted index. The index is saved to `bm25_index.pkl`.

### Step 6: Save Stats

Index statistics are cached for the `get_index_stats` MCP tool (total chunks, products, timestamp).

## Contextual Retrieval Explained

**What**: Prepend a metadata-derived context string to each chunk before embedding. This makes chunks self-describing so the embedding captures both the content and its origin.

**Why**: [Anthropic's research](https://www.anthropic.com/news/contextual-retrieval) shows this technique reduces retrieval failures by 35%.

**Example**:

Before (bare chunk):
```
Step 2: Load the policy and set the CA certificate variables.
Step 3: Deploy the authenticator client as a sidecar container.
```

After (contextualized):
```
From CyberArk Conjur Cloud documentation, page titled 'Kubernetes Authenticator',
in the section about Configuration Steps, (version Latest). Step 2: Load the policy
and set the CA certificate variables. Step 3: Deploy the authenticator client as a
sidecar container.
```

The original text is preserved in the `original_text` metadata field and returned in search results (not the prefixed version).

## Re-indexing

### When to Re-index

- After scraping new or updated documentation
- After changing the embedding model (`CYBERARK_RAG_MODEL`)
- After changing chunk size or overlap settings

### Partial Re-index

Not supported. The indexer always rebuilds the full index from scratch.

### Clean Rebuild

Delete the existing index before rebuilding:

```bash
rm -rf chroma_db/ bm25_index.pkl
python -m cyberark_rag index
```

Or use the full rebuild script:

```bash
./scripts/full_rebuild.sh
```

## CLI Options

```bash
python -m cyberark_rag index [OPTIONS]
```

| Flag | Default | Description |
|---|---|---|
| `--docs-dir PATH` | `scraped_docs` | Directory containing scraped JSON files |
| `--db-dir PATH` | `chroma_db` | Directory for ChromaDB storage |
| `--chunk-size INT` | `800` | Target tokens per chunk |
| `--chunk-overlap INT` | `100` | Overlap tokens between chunks |
| `--batch-size INT` | `100` | Embedding batch size (lower if running out of memory) |

## Upgrading the Embedding Model

The default model is `BAAI/bge-large-en-v1.5` (1024 dimensions). To switch models:

1. Set the environment variable:

```bash
export CYBERARK_RAG_MODEL="BAAI/bge-large-en-v1.5"
```

2. Delete the existing index (embedding dimensions change):

```bash
rm -rf chroma_db/ bm25_index.pkl
```

3. Rebuild:

```bash
python -m cyberark_rag index
```

### Model Comparison

| Model | Dimensions | Download | Index Size | Quality | Index Time* |
|---|---|---|---|---|---|
| `all-MiniLM-L6-v2` | 384 | ~80 MB | ~1.2 GB | Good | ~5 min |
| `BAAI/bge-base-en-v1.5` | 768 | ~420 MB | ~2.4 GB | Better | ~8 min |
| `BAAI/bge-large-en-v1.5` | 1024 | ~1.3 GB | ~3.8 GB | Best | ~15 min |

*Approximate times for ~19K docs on M1 Max.

## LLM-Powered Contextual Retrieval (Optional)

The default contextual prefixes are built from metadata (URL, title, heading). For higher quality, you can use Claude Haiku to generate richer context for each chunk.

### Requirements

- `ANTHROPIC_API_KEY` environment variable set
- Additional cost: ~$1.02 per million document tokens (with prompt caching)

### Expected Improvement

- Metadata-only prefixes: 35% fewer retrieval failures (current default)
- LLM-generated context: 49-67% fewer retrieval failures

The upgrade path is documented in `cyberark_rag/contextual_chunker.py` with Anthropic's recommended prompt.

## Troubleshooting

### Out of Memory During Indexing

Reduce the batch size:

```bash
python -m cyberark_rag index --batch-size 50
```

Or use a smaller embedding model:

```bash
export CYBERARK_RAG_MODEL="all-MiniLM-L6-v2"
```

### "No documents found in scraped_docs/"

Run the scraper first:

```bash
python incremental_scraper.py --full
```

### Indexing Takes Too Long

Expected times vary by model:
- MiniLM: ~5 minutes for 19K docs
- BGE-base: ~8 minutes
- BGE-large: ~15 minutes

Close other applications to free CPU/memory resources.

### "ChromaDB collection already exists"

Delete the existing database and rebuild:

```bash
rm -rf chroma_db/
python -m cyberark_rag index
```
