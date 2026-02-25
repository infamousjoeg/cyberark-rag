# Test Fixtures

All shared fixtures live in `tests/conftest.py`. Module-specific fixtures can live in the test file itself.

## conftest.py Fixtures

### sample_scraped_docs (scope="session")

Returns a list of 5 realistic CyberArk doc dicts matching the scraped JSON format:

```python
[
    {
        "url": "https://docs.cyberark.com/conjur-cloud/Latest/en/Content/Conjur/conjur-authn-k8s.htm",
        "title": "Kubernetes Authenticator",
        "content": CONJUR_K8S_AUTH_CONTENT,  # ~500 words about Conjur K8s auth
        "scraped_at": "2026-02-01T00:00:00Z"
    },
    # ... 4 more covering different products
]
```

### sample_sitemap_xml (scope="session")

Returns bytes of a valid sitemap XML with 5 URL entries, some with `<lastmod>` and some without.

### sample_sitemap_index_xml (scope="session")

Returns bytes of a sitemap index XML referencing 2 child sitemaps.

### bm25_empty (scope="function")

Returns a fresh BM25Index() with no documents.

### bm25_with_docs (scope="module")

Returns a BM25Index with 5 documents added and build() called. Documents cover different CyberArk products so product filtering can be tested.

### mock_chromadb_collection (scope="function")

Returns a MagicMock that behaves like a ChromaDB collection:
- `.query()` returns a dict with "ids", "documents", "metadatas", "distances" keys
- Pre-loaded with a few results for common test queries

### scraper_state (scope="function")

Returns a dict matching the scraper_state.json format with 3 URLs at different states:
- One URL with recent lastmod (should not need update)
- One URL with old lastmod (should need update)
- One URL not in state at all (implicit: should need update)

### vector_search_results (scope="session")

Returns a list of 5 dicts simulating vector search output:
```python
[
    {"url": "https://docs.cyberark.com/...", "chunk_index": 0, "title": "...", "content": "...", "relevance_score": 0.92, "product_category": "conjur-cloud"},
    # ... 4 more with decreasing relevance_score
]
```

### bm25_search_results (scope="session")

Returns a list of 5 dicts simulating BM25 search output. 2 results overlap with vector_search_results (same url + chunk_index), 3 are unique.

### chunk_with_metadata (scope="session")

Factory fixture returning a function:
```python
def _make(text="sample chunk", url="https://docs.cyberark.com/test", title="Test", product="conjur-cloud", chunk_index=0):
    return (text, {"url": url, "title": title, "product_category": product, "chunk_index": chunk_index})
return _make
```

### tmp_scraper (scope="function")

Returns an IncrementalScraper instance configured with tmp_path for output_dir and state_file. HTTP session is mocked to avoid real requests.

## Fixture Dependencies

```
sample_scraped_docs
    -> used by: test_search.py, test_indexer.py

bm25_with_docs
    -> used by: test_bm25.py, test_hybrid_search.py

vector_search_results + bm25_search_results
    -> used by: test_hybrid_search.py

chunk_with_metadata
    -> used by: test_contextual_chunker.py, test_indexer.py

tmp_scraper
    -> used by: test_incremental_scraper.py
```
