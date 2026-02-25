# Search Pipeline

Deep dive into how search works, for users who want to tune or debug retrieval quality.

## Query Flow

Here is how a query moves through the system, with a worked example.

**Input query**: `"how to configure conjur kubernetes authenticator"`

### Step 1: Query Expansion

The `QueryExpander` tokenizes the query and matches tokens against 80+ expansion groups in `query_expansions.yaml`.

| Original Token | Matched Group | Added Terms |
|---|---|---|
| conjur | conjur group | dap, secrets-manager |
| kubernetes | kubernetes group | k8s, openshift |
| configure | setup group | install, setup |

**Expanded query**: `"how to configure conjur kubernetes authenticator dap secrets-manager k8s openshift install setup"`

Original terms keep 1.0x weight; expansion terms get 0.7x weight. A maximum of 5 terms are added per group match.

### Step 2: Intent Detection

The `QueryIntentDetector` classifies the query using regex patterns:

- Pattern "how to" matched -> **how-to** intent (confidence: 0.9)
- Boost factors: procedural 2.0x, code-example 1.5x, reference 1.0x, conceptual 0.8x

### Step 3: Vector Search

The expanded query is encoded using the sentence-transformers model and compared against all chunk embeddings in ChromaDB via cosine similarity.

Returns `top_k * 3` candidates (e.g., 15 results for `top_k=5`) to give the fusion step enough material.

Vector search excels at semantic similarity: it finds chunks about "Kubernetes workload authentication" even when the exact word "authenticator" is absent.

### Step 4: BM25 Search

The expanded query is tokenized (preserving hyphens: "authn-k8s" stays as one token) and scored against the BM25 inverted index.

Returns `top_k * 3` candidates.

BM25 excels at exact-match: it finds chunks containing the literal string "CONJ00004E" or "authn-k8s" that vector search might rank lower.

### Step 5: Reciprocal Rank Fusion

Both result lists merge using weighted RRF:

```
score(d) = (0.7 / (60 + rank_vector + 1)) + (0.3 / (60 + rank_bm25 + 1))
```

- `vector_weight=0.7`: Semantic similarity is the primary signal
- `bm25_weight=0.3`: Keyword matching is the secondary signal
- `k=60`: RRF constant (higher = more equal weighting across rank positions)

Deduplication by `(url, chunk_index)` ensures each chunk appears once with its combined score.

### Step 6: Intent Re-ranking

Each result's fused score is multiplied by the intent boost factor for its content type:

| Result | Content Type | Boost | Final Score |
|---|---|---|---|
| Conjur K8s Auth (chunk 3) | procedural | 2.0x | 0.94 |
| K8s Auth Methods (chunk 0) | conceptual | 0.8x | 0.71 |
| Conjur CLI Reference (chunk 5) | reference | 1.0x | 0.68 |

### Step 7: Return Top K

The top 5 results are returned with `original_text` (not the contextualized prefix text) for display.

## Query Expansion

### How Expansion Groups Work

Each group in `query_expansions.yaml` defines a set of related terms. When any term in a group matches a query token, the other terms are candidates for expansion.

```yaml
# If query contains "spire", add "spiffe", "svid", etc.
spire:
  - spiffe
  - svid
  - workload-identity
```

### Expansion Weight

Expansion terms receive 0.7x weight vs 1.0x for original query terms. This prevents expanded terms from dominating results.

### Typo Correction

Common misspellings are handled as expansion groups:

- "priviledge" expands to include "privilege"
- "authentification" expands to include "authentication"

### Limits

- Maximum 5 expansion terms added per group match
- Expansions are case-insensitive
- Only exact token matches trigger expansion (no partial matching)

## Intent Detection

### 5 Intent Types

| Intent | Trigger Patterns | Example Queries |
|---|---|---|
| how-to | "how to", "configure", "install", "step", "guide", "tutorial" | "how to configure conjur authn-k8s" |
| explanation | "what is", "overview", "architecture", "explain", "concept" | "what is SPIFFE identity" |
| reference | "api", "command", "parameter", "syntax", "specification" | "conjur CLI command reference" |
| troubleshooting | "error", "failed", "not working", "debug", "fix" | "PVWA error 401 access denied" |
| general | (no strong signals) | "conjur authentication" |

### How Intent Affects Re-ranking

Each intent type defines boost multipliers per content type:

| Intent | Procedural | Conceptual | Reference | Code-Example |
|---|---|---|---|---|
| how-to | 2.0x | 0.8x | 1.0x | 1.5x |
| explanation | 0.8x | 2.0x | 1.2x | 0.8x |
| reference | 1.0x | 0.8x | 2.0x | 1.5x |
| troubleshooting | 1.5x | 0.8x | 1.2x | 2.0x |
| general | 1.0x | 1.0x | 1.0x | 1.0x |

A "how to" query boosts procedural content (step-by-step instructions) to 2.0x while penalizing conceptual content (overviews) to 0.8x.

## Hybrid Search

### Why Both Vector and BM25

**Vector search** encodes meaning. "Kubernetes workload authentication" and "pod identity verification" are semantically similar even though they share no words.

**BM25 keyword search** matches exact terms. Error codes like "CONJ00004E", parameter names like "authn-k8s", and product acronyms like "PVWA" are found reliably.

Together, they cover both semantic and lexical retrieval with 49% fewer failures than vector-only search ([Anthropic research](https://www.anthropic.com/news/contextual-retrieval)).

### Example: "PVWA error 401"

- **BM25** finds chunks containing the literal strings "PVWA" and "401" (exact match)
- **Vector search** finds chunks about "authentication failure in the Password Vault Web Access" (semantic match)
- **Fusion** combines both, ranking chunks that match on both dimensions highest

### Reciprocal Rank Fusion

RRF was chosen over other fusion methods because:
- No score normalization needed (vector cosine scores and BM25 scores are on different scales)
- Simple and robust
- Used by Microsoft Azure AI Search and other production systems

Formula:
```
score(d) = sum_i(weight_i / (k + rank_i + 1))
```

Where `rank_i` is the document's position in result list `i` (0-indexed).

### Tuning Weights

The default `vector_weight=0.7, bm25_weight=0.3` works well for most CyberArk documentation queries. Adjust in `cyberark_rag/hybrid_search.py`:

- **More exact-match**: `vector_weight=0.5, bm25_weight=0.5` (good for error code lookups)
- **More semantic**: `vector_weight=0.9, bm25_weight=0.1` (good for conceptual questions)

## Content Classification

The `ContentClassifier` assigns each chunk a primary type during indexing.

| Type | Detection Signals |
|---|---|
| procedural | Step indicators ("Step 1:", "Navigate to"), numbered lists, action verbs |
| conceptual | Overview language ("provides", "enables"), architecture descriptions |
| reference | Table markers, API endpoints, parameter lists, command syntax |
| code-example | Code blocks (triple backticks), `curl` commands, YAML/JSON snippets |

URL paths also influence classification:
- `/reference/` or `/api/` biases toward "reference"
- `/tutorial/` or `/getting-started/` biases toward "procedural"

## Debugging Search Quality

### Check Query Expansion

If search returns unexpected results, verify the expansion:

```python
from cyberark_rag.query_expansion import expand_query
print(expand_query("your query here"))
```

Watch for expansion terms that are too broad or semantically unrelated.

### Check Intent Detection

```python
from cyberark_rag.query_intent import detect_intent
intent = detect_intent("your query here")
print(f"Intent: {intent.intent_type}, Confidence: {intent.confidence}")
print(f"Boosts: {intent.boost_factors}")
```

### Compare Hybrid vs Vector-Only

```bash
# Hybrid (default)
python -m cyberark_rag search "PVWA error 401" --top-k 5

# To test vector-only, temporarily modify the search call
```

If BM25 results dominate, the `bm25_weight` may be too high. If exact terms are missed, it may be too low.

### Check Product Filter

An overly narrow product filter can exclude relevant results:

```bash
# Without filter (searches all products)
python -m cyberark_rag search "authentication"

# With filter (only one product)
python -m cyberark_rag search "authentication" --product conjur-cloud
```

### Verify Index Health

```bash
$ python -m cyberark_rag search --stats
Total chunks: 52,847
Collection: cyberark_docs
Database: ./chroma_db
```

If the chunk count is zero or the database is missing, rebuild the index.
