# Per-Module Test Specifications

## tests/test_config.py

Tests the Settings class in `cyberark_rag/config.py`.

### test_defaults_resolve_to_project_root
- Settings.DOCS_DIR ends with "scraped_docs"
- Settings.DB_DIR ends with "chroma_db"
- Settings.BM25_PATH ends with "bm25_index.pkl"
- Settings.COLLECTION_NAME == "cyberark_docs"

### test_env_var_override_docs_dir
- Set `CYBERARK_RAG_DOCS=/tmp/custom_docs` via `monkeypatch.setenv`
- Re-import or re-instantiate Settings
- Assert DOCS_DIR == Path("/tmp/custom_docs")

### test_env_var_override_embedding_model
- Set `CYBERARK_RAG_MODEL=BAAI/bge-large-en-v1.5`
- Assert Settings.EMBEDDING_MODEL == "BAAI/bge-large-en-v1.5"

### test_chunk_size_override
- Set `CYBERARK_RAG_CHUNK_SIZE=1024`
- Assert Settings.CHUNK_SIZE == 1024

### test_logging_writes_to_stderr
- Call setup_logging(), log a message, capture stderr
- Assert message appears in stderr, NOT in stdout

---

## tests/test_incremental_scraper.py

Tests `incremental_scraper.py` at project root.

### Sitemap Parsing

#### test_parse_simple_sitemap
- Feed `_parse_sitemap()` a valid XML bytestring with 3 `<url>` entries
- Assert returns 3 dicts with "url" and "lastmod" keys

#### test_parse_sitemap_index_recursive
- Feed a sitemap index XML that references a child sitemap URL
- Mock the HTTP call for the child sitemap
- Assert all URLs from both levels are returned

#### test_parse_sitemap_respects_depth_limit
- Feed a sitemap index with depth > 3
- Assert recursion stops at depth 3

#### test_parse_invalid_xml_returns_empty
- Feed malformed XML bytes
- Assert returns empty list (no exception)

#### test_parse_sitemap_missing_lastmod
- URL entry has `<loc>` but no `<lastmod>`
- Assert lastmod is None in result dict

### URL Validation (parameterized)

```python
@pytest.mark.parametrize("url,valid", [
    ("https://docs.cyberark.com/Product-Doc/Latest/en/Content/PASIMP/Overview.htm", True),
    ("https://docs.cyberark.com/conjur-cloud/Latest/en/Content/page.htm", True),
    ("https://docs.cyberark.com/file.pdf", False),
    ("https://docs.cyberark.com/image.PNG", False),
    ("https://docs.cyberark.com/style.css", False),
    ("https://docs.cyberark.com/script.js", False),
    ("https://docs.cyberark.com/archive.zip", False),
    ("https://evil.com/page", False),
    ("https://evil.com/docs.cyberark.com/page", False),
    ("", False),
])
```

### State Management

#### test_state_fresh_start
- No state file exists
- Assert state == {"last_run": None, "pages": {}}

#### test_state_save_load_roundtrip (tmp_path)
- Create scraper with state_file in tmp_path
- Add pages to state, save, create new scraper with same state_file
- Assert loaded state matches saved state

#### test_state_save_updates_last_run
- Save state, load it back
- Assert last_run is a valid ISO timestamp

### Incremental Logic

#### test_needs_update_new_url
- URL not in state -> returns True

#### test_needs_update_newer_lastmod
- URL in state with lastmod "2026-01-01", sitemap lastmod "2026-02-01"
- Returns True

#### test_needs_update_same_lastmod
- URL in state with lastmod "2026-01-01", sitemap lastmod "2026-01-01"
- Returns False

#### test_needs_update_no_lastmod_in_sitemap
- URL in state, sitemap lastmod is None
- Returns False (conservative: skip unless --full)

#### test_needs_update_no_lastmod_in_state
- URL in state with no lastmod, sitemap has lastmod
- Returns True (state was incomplete)

### Content Hashing

#### test_content_hash_deterministic
- Same content produces same hash
- Hash is 16 hex chars

#### test_content_hash_differs_for_different_content
- Different content produces different hashes

### Filename Sanitization

#### test_sanitize_preserves_meaningful_path
- URL path segments become underscore-separated
- Result ends with .json

#### test_sanitize_truncates_long_paths
- Path > 200 chars gets truncated to 200 + ".json"

#### test_sanitize_empty_path_returns_index
- Root URL "/" -> "index.json"

### Dry Run

#### test_dry_run_does_not_scrape (monkeypatch)
- Mock session.get to track calls
- Run with dry_run=True
- Assert session.get was called only for sitemap, not for page URLs

---

## tests/test_contextual_chunker.py

Tests `cyberark_rag/contextual_chunker.py`.

### Context Prefix Generation

#### test_build_chunk_context_basic
- URL: "https://docs.cyberark.com/conjur-cloud/Latest/en/Content/Conjur/auth.htm"
- title: "Conjur Authentication", product_category: "conjur-cloud"
- Assert prefix starts with "From CyberArk Conjur Cloud documentation"
- Assert prefix contains 'page titled "Conjur Authentication"'
- Assert prefix ends with ". "

#### test_build_chunk_context_with_section_heading
- full_content includes "## Setting Up Kubernetes\n...chunk text..."
- Assert prefix contains "in the section about Setting Up Kubernetes"

#### test_build_chunk_context_with_version
- URL contains "/14.2/" path segment
- Assert prefix contains "(version 14.2)"

#### test_build_chunk_context_latest_version
- URL contains "/Latest/" path segment
- Assert prefix contains "(version Latest)"

#### test_build_chunk_context_middle_position
- chunk_index=3, total_chunks=10
- Assert prefix contains "(middle of document)"

#### test_build_chunk_context_end_position
- chunk_index=9, total_chunks=10
- Assert prefix contains "(end of document)"

#### test_build_chunk_context_first_chunk_no_position
- chunk_index=0
- Assert prefix does NOT contain "middle" or "end"

#### test_build_chunk_context_skips_generic_title
- title="Untitled" or "CyberArk Docs"
- Assert prefix does NOT contain 'page titled'

#### test_build_chunk_context_empty_product
- product_category=""
- Assert prefix still starts with "From CyberArk" (graceful degradation)

### Heading Extraction

#### test_extract_nearest_heading_markdown
- full_content: "# Overview\nSome text\n## Authentication\nChunk text here"
- chunk_text: "Chunk text here"
- Assert returns "Authentication"

#### test_extract_nearest_heading_title_case
- full_content: "Getting Started Guide\nSome intro\nChunk text"
- Assert returns "Getting Started Guide"

#### test_extract_nearest_heading_no_heading
- full_content has no headings above chunk
- Assert returns ""

#### test_extract_nearest_heading_chunk_not_found
- chunk_text not in full_content
- Assert returns "" (no crash)

### Version Extraction (parameterized)

```python
@pytest.mark.parametrize("path_parts,expected", [
    (["conjur-cloud", "14.2", "en", "Content"], "14.2"),
    (["Product-Doc", "v12", "en"], "v12"),
    (["Product-Doc", "Latest", "en"], "Latest"),
    (["Product-Doc", "en", "Content"], ""),
    ([], ""),
])
```

### Contextualize Chunks Integration

#### test_contextualize_chunks_preserves_original_text
- 3 input chunks
- After contextualization, each metadata dict has "original_text" key
- original_text == original chunk text (unmodified)

#### test_contextualize_chunks_adds_prefix_to_text
- After contextualization, chunk text starts with the context prefix
- chunk text contains original text after the prefix

#### test_contextualize_chunks_stores_prefix_in_metadata
- Each metadata dict has "context_prefix" key
- context_prefix matches what build_chunk_context would return

#### test_contextualize_chunks_empty_list
- Input: empty list -> returns empty list

---

## tests/test_bm25.py

Tests `cyberark_rag/bm25_index.py`.

### Tokenizer

#### test_tokenize_basic
- "Hello world" -> ["hello", "world"]

#### test_tokenize_preserves_hyphens
- "privilege-cloud configuration" -> ["privilege-cloud", "configuration"]

#### test_tokenize_preserves_aam_dap
- "AAM-DAP secrets manager" -> ["aam-dap", "secrets", "manager"]

#### test_tokenize_single_char_words
- "I am a test" -> ["i", "am", "a", "test"]

#### test_tokenize_strips_punctuation
- "Hello, world! (test)" -> ["hello", "world", "test"]

#### test_tokenize_empty_string
- "" -> []

#### test_tokenize_cyberark_error_code
- "Error APPAP001E occurred" -> ["error", "appap001e", "occurred"]

### Index CRUD

#### test_add_document_and_build
- Add 3 docs, call build()
- Assert doc_count == 3
- Assert avg_doc_len > 0

#### test_search_returns_ranked_results
- Add 3 docs with different term frequencies for "kubernetes"
- Search "kubernetes"
- Assert results are ranked by descending bm25_score

#### test_search_empty_query
- search("") -> returns empty list

#### test_search_no_matching_terms
- Index has docs about "kubernetes", search for "quantum"
- Returns empty list

#### test_search_respects_top_k
- Add 10 docs, search with top_k=3
- Assert exactly 3 results returned

#### test_search_product_filter
- Add docs with different product_category metadata
- Search with filter_product="conjur-cloud"
- Assert all results have product_category == "conjur-cloud"

#### test_search_product_filter_no_match
- Filter for product not in index
- Returns empty list

### BM25 Scoring

#### test_idf_rare_term_scores_higher
- Add 10 docs, 1 contains "rare-term", 9 contain "common"
- Search for "rare-term common"
- Assert the doc with "rare-term" scores highest

#### test_tf_saturation
- Doc A: "kubernetes" appears 50 times
- Doc B: "kubernetes" appears 5 times
- Score difference should be less than 10x (saturation via k1)

### Persistence

#### test_save_load_roundtrip (tmp_path)
- Build index with 5 docs, save to tmp_path
- Load from same path
- Search returns identical results as pre-save

#### test_load_nonexistent_file_raises
- BM25Index.load("nonexistent.pkl") -> raises FileNotFoundError

---

## tests/test_hybrid_search.py

Tests `cyberark_rag/hybrid_search.py`.

### Reciprocal Rank Fusion

#### test_rrf_basic_merge
- vector_results: [A, B, C] and bm25_results: [B, D, A]
- B appears in both lists -> should have highest fused score

#### test_rrf_vector_weight_dominance
- vector_weight=0.9, bm25_weight=0.1
- Vector #1 result should outrank BM25 #1 result

#### test_rrf_bm25_weight_dominance
- vector_weight=0.1, bm25_weight=0.9
- BM25 #1 result should outrank Vector #1 result

#### test_rrf_deduplication
- Same (url, chunk_index) in both lists
- Result appears exactly once in output with combined score

#### test_rrf_disjoint_results
- No overlap between vector and BM25 results
- All results from both lists appear in output

#### test_rrf_empty_vector_results
- vector_results=[], bm25_results=[A, B]
- Returns results from BM25 only

#### test_rrf_empty_bm25_results
- bm25_results=[]
- Returns results from vector only

#### test_rrf_both_empty
- Both empty -> returns empty list

#### test_rrf_preserves_metadata
- Input results have metadata keys (url, title, product_category, content)
- Output results retain all metadata

#### test_rrf_k_parameter_affects_scoring
- k=1 produces more dramatic score differences than k=100
- Verify ordering changes with different k values

---

## tests/test_search.py

Integration tests for `cyberark_rag/search.py`. These require either a small in-memory index or mocked ChromaDB.

### Setup: Use a fixture that builds a tiny index from 5-10 sample documents

#### test_search_returns_results
- Query: "configure conjur kubernetes"
- Assert results is non-empty list

#### test_search_result_structure
- Each result has: url, title, content (or original_text), relevance_score, product_category

#### test_search_respects_top_k
- search("authentication", top_k=3) returns exactly 3 results

#### test_search_product_filter_constrains_results
- search("authentication", filter_product="conjur-cloud")
- All results have matching product_category

#### test_search_hybrid_vs_vector_only
- search("PVWA error 401", use_hybrid=True) vs use_hybrid=False
- Hybrid should rank exact keyword matches higher

#### test_search_returns_original_text_not_prefixed
- Results should contain the original chunk text, not the contextual prefix
- Assert no result content starts with "From CyberArk"

#### test_search_empty_query_returns_error_or_empty
- search("") returns empty list or raises ValueError

---

## tests/test_query_expansion.py

Tests `cyberark_rag/query_expansion.py`.

### CyberArk-Specific Expansions (parameterized)

```python
@pytest.mark.parametrize("query,expected_terms", [
    ("configure spire", ["spiffe", "svid"]),
    ("kubernetes auth", ["k8s", "openshift"]),
    ("conjur secrets", ["dap", "secrets-manager"]),
    ("rotate credentials", ["rotation", "password"]),
    ("jwt authentication", ["bearer-token", "oauth"]),
    ("pam setup", ["privilege-cloud", "pas"]),
    ("epm policy", ["least-privilege", "endpoint-privilege-manager"]),
])
def test_expansion_includes_expected_terms(expander, query, expected_terms):
    expanded = expander.expand(query)
    for term in expected_terms:
        assert term in expanded.lower(), f"Expected '{term}' in expansion of '{query}'"
```

#### test_expansion_limits_added_terms
- Expansion adds at most 5 terms per group match

#### test_expansion_preserves_original_query
- Original query terms always present in expanded query

#### test_expansion_no_expansion_for_unknown_terms
- "quantum computing" has no expansion group
- Expanded query == original query

#### test_typo_correction
- "priviledge" expands to include "privilege"
- "authentification" expands to include "authentication"

---

## tests/test_query_intent.py

Tests `cyberark_rag/query_intent.py`.

### Intent Detection (parameterized)

```python
@pytest.mark.parametrize("query,expected_intent", [
    ("how to configure conjur kubernetes", "how-to"),
    ("how do I configure conjur authn-k8s", "how-to"),
    ("what is SPIFFE", "explanation"),
    ("explain the difference between Conjur and Secrets Hub", "explanation"),
    ("PVWA error 401 troubleshooting", "troubleshooting"),
    ("fix CONJ00004E authenticator not enabled", "troubleshooting"),
    ("conjur CLI reference", "reference"),
    ("list of PVWA API endpoints", "reference"),
    ("conjur authentication", "general"),
])
```

#### test_intent_boost_multipliers
- how-to query + procedural content -> boost >= 1.5
- how-to query + reference content -> boost <= 1.0
- troubleshooting query + troubleshooting content -> boost >= 1.5

---

## tests/test_product_aliases.py

Tests `cyberark_rag/product_aliases.py`.

### Alias Resolution (parameterized)

```python
@pytest.mark.parametrize("raw,canonical", [
    ("AAM-DAP", "secrets-manager-sh"),
    ("conjur-cloud", "secrets-manager-saas"),
    ("PrivCloud", "privilege-cloud-standard"),
    ("PAS", "pam-self-hosted"),
    ("epm", "endpoint-privilege-manager"),
    ("dpa", "dynamic-privileged-access"),
    ("alero", "remote-access"),
])
```

#### test_canonical_name_maps_to_itself
- "secrets-manager-saas" -> "secrets-manager-saas"

#### test_unknown_alias_returns_original
- "nonexistent-product" -> "nonexistent-product" (passthrough)

#### test_display_name_available_for_all_products
- Every canonical product has a non-empty display_name

---

## tests/test_mcp_server.py

Tests `cyberark_rag/mcp_server.py` (FastMCP tools).

### Tool Registration

#### test_all_tools_registered
- Import mcp server, list tools
- Assert exactly 4 tools: cyberark_rag_search_docs, cyberark_rag_get_command_example, cyberark_rag_list_products, cyberark_rag_get_index_stats

#### test_tool_names_have_prefix
- All tool names start with "cyberark_rag_"

#### test_tool_annotations_readonly
- All tools have readOnlyHint=True, destructiveHint=False

### Search Tool

#### test_search_docs_returns_text_content
- Call search_docs with valid query
- Assert response is a non-empty string

#### test_search_docs_missing_query_errors
- Call with empty query
- Assert error message in response

#### test_search_docs_with_product_filter
- Call with product_filter="conjur-cloud"
- Response should contain results (or appropriate message)

### List Products Tool

#### test_list_products_returns_categories
- Call list_products
- Response contains product names
- Response contains "Total:" or similar count

### Index Stats Tool

#### test_get_index_stats_returns_stats
- Response contains: total chunks count, products count, BM25 status

---

## tests/test_indexer.py

Tests `cyberark_rag/indexer.py`.

### Chunking

#### test_chunk_text_respects_size_limit
- Chunk a 2000-token document
- Each chunk <= CHUNK_SIZE tokens (allow 10% overflow for paragraph boundaries)

#### test_chunk_text_overlap
- Adjacent chunks share overlapping content

#### test_chunk_text_single_paragraph
- Short document (< chunk_size) -> single chunk

#### test_chunk_text_preserves_all_content
- Concatenate all chunks (minus overlap) -> covers original content

### Metadata

#### test_chunk_metadata_includes_required_fields
- Each chunk metadata has: url, title, product_category, chunk_index, content_type

#### test_product_category_extracted_from_url
- URL "https://docs.cyberark.com/conjur-cloud/..." -> product_category contains "conjur"

---

## tests/test_content_classifier.py

Tests `cyberark_rag/content_classifier.py`.

### Content Type Detection (parameterized)

```python
@pytest.mark.parametrize("text,expected_type", [
    ("Step 1: Navigate to Settings. Step 2: Click Configure.", "procedural"),
    ("The PVWA is a web-based interface that provides...", "conceptual"),
    ("curl -X POST https://conjur.example.com/authn/...", "code-example"),
    ("| Parameter | Type | Description |", "reference"),
])
```

#### test_url_signals_affect_classification
- URL containing "/reference/" or "/api/" biases toward "reference"
- URL containing "/tutorial/" or "/getting-started/" biases toward "procedural"
