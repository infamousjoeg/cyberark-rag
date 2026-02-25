---
paths:
  - "cyberark_rag/indexer.py"
  - "cyberark_rag/search.py"
  - "cyberark_rag/contextual_chunker.py"
  - "cyberark_rag/bm25_index.py"
  - "cyberark_rag/hybrid_search.py"
---

# Search & Indexing Rules

## Contextual Retrieval (Anthropic Best Practice)

At index time, prepend a metadata-derived context prefix to each chunk BEFORE embedding. This is the single highest-impact improvement (35% fewer retrieval failures).

Prefix format:
```
From CyberArk {Product Name} documentation, page titled "{Title}", in the section about {nearest heading}. 
```

Implementation in `contextual_chunker.py`:
- `build_chunk_context(url, title, product_category, chunk_text, chunk_index, total_chunks, full_content)` -> str
- Extract product display name from product_category (replace hyphens with spaces, title case)
- Find nearest heading above the chunk using regex: `^#{1,3}\s+(.+)$` and title-case lines
- Extract version from URL path segments matching `^\d+\.\d+` or `^v\d+`
- Store `original_text` in metadata (for display), embed the prefixed version

Include a docstring block documenting the LLM-powered upgrade path:
```
# LLM-POWERED VERSION (future upgrade, requires API key):
# Cost with prompt caching: ~$1.02 per million document tokens
# Prompt: <document>{WHOLE_DOC}</document><chunk>{CHUNK}</chunk>
# Give a short succinct context to situate this chunk within the overall document.
# Expected improvement: 49% (vs 35% for metadata-only)
```

## BM25 Hybrid Search

Okapi BM25 with k1=1.5, b=0.75. Critical for exact-match queries like error codes and API parameter names.

Tokenizer regex: `r"\b[\w][\w\-]*[\w]\b|\b\w\b"` -- preserves hyphenated terms (privilege-cloud, AAM-DAP).

## Reciprocal Rank Fusion

Combine vector + BM25 results: `score = sum(weight / (k + rank + 1))` for each list.
Default weights: vector=0.7, BM25=0.3, k=60.
Deduplicate by (url, chunk_index) tuple.

## Index Pipeline Order

1. Load scraped JSON files
2. Chunk text (500 tokens, 100 overlap)
3. Contextualize chunks (prepend metadata prefix)
4. Embed contextualized text -> ChromaDB
5. Build BM25 index from same contextualized text -> bm25_index.pkl

## Search Pipeline Order

1. Expand query (query_expansion.py)
2. Detect intent (query_intent.py)
3. Vector search (top_k * 3)
4. BM25 search (top_k * 3)
5. Reciprocal Rank Fusion
6. Intent-based re-ranking
7. Return top_k results with `original_text` (not prefixed text)
