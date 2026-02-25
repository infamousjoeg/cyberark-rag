# Test Strategy

## Philosophy

Tests validate behavior, not implementation. Each test answers: "If I changed the internals, would this test still pass if the behavior is correct?" If yes, it is a good test. If it would break because you renamed a private method, it is a brittle test.

## Test Pyramid

```
         /  E2E  \           2-3 tests: full search pipeline
        / Integr. \          ~15 tests: module interactions
       /   Unit    \         ~80 tests: individual functions
```

Most tests should be fast unit tests with mocked dependencies. Integration tests verify module boundaries (indexer -> ChromaDB, search -> BM25 + vector). E2E tests run the full search pipeline against a tiny in-memory index.

## Patterns

### Arrange-Act-Assert

Every test follows this structure. Comments are optional but the structure is not.

```python
def test_bm25_search_returns_ranked_results(bm25_with_docs):
    # Arrange: bm25_with_docs fixture provides a built index with 3 docs

    # Act
    results = bm25_with_docs.search("privilege cloud rotate", top_k=2)

    # Assert
    assert len(results) == 2
    assert results[0]["bm25_score"] > results[1]["bm25_score"]
```

### Parameterized Tests for Boundary Conditions

Use `@pytest.mark.parametrize` aggressively for input validation and edge cases.

```python
@pytest.mark.parametrize("url,expected", [
    ("https://docs.cyberark.com/page", True),
    ("https://docs.cyberark.com/file.pdf", False),
    ("https://evil.com/docs.cyberark.com", False),
    ("https://docs.cyberark.com/image.PNG", False),
    ("", False),
])
def test_url_validation(url, expected):
    assert scraper._is_valid_url(url) == expected
```

### Fixture Scoping

- `scope="session"`: Expensive resources that are read-only (embedding model loading, large YAML parsing)
- `scope="module"`: Resources shared across tests in one file (BM25 index with test docs)
- `scope="function"` (default): Mutable state that needs reset per test (scraper state, tmp directories)

### Mocking External Dependencies

Mock at the boundary, not deep inside the code.

```python
# GOOD: mock the HTTP session
@pytest.fixture
def mock_session(monkeypatch):
    session = MagicMock()
    session.get.return_value = MockResponse(200, SAMPLE_SITEMAP_XML)
    monkeypatch.setattr("incremental_scraper.requests.Session", lambda: session)
    return session

# BAD: mocking internal methods
monkeypatch.setattr(scraper, "_parse_sitemap", lambda x, y: [...])
```

### Temporary Files

Always use `tmp_path` fixture for file I/O tests. Never write to the project directory.

```python
def test_state_save_load_roundtrip(tmp_path):
    state_file = tmp_path / "state.json"
    scraper = IncrementalScraper(state_file=str(state_file))
    scraper.state = {"last_run": "2026-01-01T00:00:00Z", "pages": {"url1": {"lastmod": "2026-01-01"}}}
    scraper._save_state()

    loaded = IncrementalScraper(state_file=str(state_file))
    assert loaded.state["pages"]["url1"]["lastmod"] == "2026-01-01"
```

## Anti-Patterns to Avoid

- Testing private methods directly (test via public API)
- Asserting on exact string formatting of search results (assert on structure, not prose)
- Tests that depend on execution order
- Tests that require the full 19K-doc index
- Tests that make real HTTP requests
- Sleeping in tests (use mocks for rate limiting)
- Testing that logging output contains specific strings (fragile)

## Coverage Targets

| Module | Target | Rationale |
|---|---|---|
| `config.py` | 95% | Simple, no external deps |
| `contextual_chunker.py` | 90% | Pure functions, easy to test |
| `bm25_index.py` | 90% | Self-contained data structure |
| `hybrid_search.py` | 95% | Pure function, critical logic |
| `incremental_scraper.py` | 80% | HTTP mocking adds complexity |
| `search.py` | 75% | Requires ChromaDB mocking |
| `mcp_server.py` | 70% | Async + MCP protocol overhead |
| `indexer.py` | 70% | Heavy I/O, model loading |

## pytest Configuration

```toml
# pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
markers = [
    "slow: marks tests that take >2s (deselect with '-m \"not slow\"')",
    "integration: marks tests requiring built index",
]
filterwarnings = [
    "ignore::DeprecationWarning:chromadb.*",
    "ignore::DeprecationWarning:sentence_transformers.*",
]
```
