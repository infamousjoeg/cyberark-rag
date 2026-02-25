# Contributing

Development setup, testing conventions, and PR guidelines.

## Development Setup

```bash
# Clone and set up
git clone https://github.com/infamousjoeg/cyberark-rag.git
cd cyberark-rag
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run tests
pytest -v
```

## Project Structure

```
cyberark-rag/
├── README.md                       # Project overview and quick start
├── requirements.txt                # Python dependencies
├── pyproject.toml                  # Project metadata and pytest config
├── incremental_scraper.py          # Sitemap-driven scraper (primary)
├── scraper.py                      # Legacy BFS scraper (preserved, not recommended)
├── scraper_state.json              # Scraper state tracking (auto-generated)
├── config.yaml                     # Terminal assistant config
├── mcp_config.json                 # Claude Desktop MCP config template
├── product_aliases.yaml            # Product name mappings (22+ products)
├── query_expansions.yaml           # Search term expansion groups (80+)
├── scripts/
│   ├── update.sh                   # Incremental scrape + re-index
│   └── full_rebuild.sh             # Full scrape + clean rebuild
├── bin/
│   └── cyai                        # Terminal assistant CLI entry point
├── shell/
│   └── zshrc_integration.sh        # Shell completions and PATH setup
├── cyberark_rag/
│   ├── __init__.py                 # Package version (2.0.0)
│   ├── __main__.py                 # CLI router (index, search, mcp_server, terminal)
│   ├── config.py                   # Settings class (paths, env vars)
│   ├── logging_config.py           # stderr-only logging setup
│   ├── indexer.py                  # Chunking + embedding + ChromaDB + BM25
│   ├── contextual_chunker.py       # Metadata-derived context prefixes
│   ├── bm25_index.py               # Okapi BM25 keyword index
│   ├── hybrid_search.py            # Reciprocal Rank Fusion
│   ├── search.py                   # Search pipeline orchestrator
│   ├── query_expansion.py          # Term expansion from YAML groups
│   ├── query_intent.py             # Intent detection (how-to, reference, etc.)
│   ├── content_classifier.py       # Content type classification
│   ├── product_aliases.py          # Product alias resolution
│   ├── mcp_server.py               # FastMCP server (4 tools, stdio)
│   └── terminal.py                 # Ollama terminal assistant
├── tests/                          # pytest suite
│   ├── conftest.py                 # Shared fixtures
│   ├── test_bm25.py
│   ├── test_config.py
│   ├── test_contextual_chunker.py
│   ├── test_hybrid_search.py
│   ├── test_incremental_scraper.py
│   ├── test_mcp_server.py
│   ├── test_search.py
│   └── ...
├── docs/                           # Documentation
├── scraped_docs/                   # ~19,378 JSON files (not in git)
├── chroma_db/                      # ChromaDB storage (not in git)
└── bm25_index.pkl                  # BM25 index (not in git)
```

**Auto-generated files** (do not commit): `chroma_db/`, `bm25_index.pkl`, `scraper_state.json`, `scraped_docs/`

## Testing

### Running Tests

```bash
# All tests
pytest -v

# Specific module
pytest tests/test_bm25.py -v

# With coverage
pytest -v --cov=cyberark_rag

# Skip slow tests
pytest -v -m "not slow"

# Skip integration tests (require built index)
pytest -v -m "not integration"
```

### Test Structure

Tests follow Arrange-Act-Assert:

```python
def test_bm25_search_returns_ranked_results(bm25_with_docs):
    # Arrange: bm25_with_docs fixture provides a built index with 3 docs

    # Act
    results = bm25_with_docs.search("privilege cloud rotate", top_k=2)

    # Assert
    assert len(results) == 2
    assert results[0]["bm25_score"] > results[1]["bm25_score"]
```

### Fixtures

Shared fixtures live in `tests/conftest.py`. Key fixtures:

| Fixture | Scope | Description |
|---|---|---|
| `sample_scraped_docs` | session | 5 realistic CyberArk doc dicts |
| `sample_sitemap_xml` | session | Valid sitemap XML with 5 URLs |
| `bm25_with_docs` | module | Built BM25 index with 5 test docs |
| `vector_search_results` | session | 5 simulated vector search results |
| `bm25_search_results` | session | 5 simulated BM25 search results |
| `chunk_with_metadata` | session | Factory for creating test chunks |
| `tmp_scraper` | function | IncrementalScraper with mocked HTTP |

### Writing New Tests

- Use `pytest.mark.parametrize` for boundary conditions and input validation
- Mock external dependencies (HTTP, ChromaDB) at the boundary, not deep inside the code
- Use `tmp_path` for file I/O tests; never write to the project directory
- Do not test private methods directly; test via the public API
- Do not assert on exact string formatting (assert on structure)

### Coverage Targets

| Module | Target |
|---|---|
| `config.py` | 95% |
| `contextual_chunker.py` | 90% |
| `bm25_index.py` | 90% |
| `hybrid_search.py` | 95% |
| `incremental_scraper.py` | 80% |
| `search.py` | 75% |
| `mcp_server.py` | 70% |
| `indexer.py` | 70% |

## Adding a New CyberArk Product

1. Add to `product_aliases.yaml`:

```yaml
new-product:
  display_name: "New Product Name"
  category: product
  description: "What this product does"
  aliases:
    - np
    - new-prod
```

2. Add expansion terms to `query_expansions.yaml`:

```yaml
new-product:
  - np
  - new-prod-feature
```

3. Re-scrape if needed (the product may already be in scraped docs).
4. Re-index to pick up alias changes in product category extraction.

## Adding a New MCP Tool

1. Define a Pydantic input model in `cyberark_rag/mcp_server.py`:

```python
class MyToolInput(BaseModel):
    param: str = Field(description="Parameter description")
```

2. Add a `@mcp.tool()` decorated function with the `cyberark_rag_` prefix:

```python
@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
def cyberark_rag_my_tool(param: str) -> str:
    """Tool description for Claude."""
    # Implementation
    return "result"
```

3. Add tests in `tests/test_mcp_server.py`.
4. Update `docs/mcp-integration.md` tool reference.

## Code Style

- Type hints on all functions
- Docstrings on all public methods
- f-strings over `.format()`
- `pathlib.Path` over `os.path`
- Logging to stderr only (never stdout in MCP context)
- No em-dashes in any text, comments, or documentation
- Imports: stdlib, blank line, third-party, blank line, local

## Pull Request Checklist

- [ ] `pytest -v` passes
- [ ] No hardcoded absolute paths (`grep -rn "/Users/" .` returns nothing)
- [ ] New code has tests
- [ ] Documentation updated if behavior changed
- [ ] Commit messages follow conventional commits (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`)
