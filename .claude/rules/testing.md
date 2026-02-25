---
paths:
  - "tests/**/*.py"
  - "pyproject.toml"
---

# Testing Rules

Use pytest, not the existing custom test harness. Add `pytest>=8.0.0` and `pytest-asyncio>=0.23.0` to requirements.txt.

## pytest Configuration

In `pyproject.toml`:
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

## Required Test Modules

| Module | Tests |
|---|---|
| `test_incremental_scraper.py` | Sitemap XML parsing, URL validation, state round-trip, needs_update logic |
| `test_contextual_chunker.py` | Non-empty prefix, version extraction, heading extraction, original_text preserved |
| `test_bm25.py` | Hyphenated term tokenization, add/build/search round-trip, save/load, product filter |
| `test_hybrid_search.py` | RRF with known rankings, deduplication, weight parameter effects |
| `test_search.py` | Basic search returns results, product filter, query expansion, intent detection |
| `test_mcp_server.py` | Each tool returns valid TextContent, missing params error, list_products non-empty |

## Fixture Strategy

Use `@pytest.fixture(scope="session")` for expensive resources (DocumentSearcher, BM25Index). Keep in `conftest.py`.

## Validation After Each Phase

After every code change: run `pytest -v` and confirm green before moving on.
