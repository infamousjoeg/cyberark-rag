---
paths:
  - "incremental_scraper.py"
  - "scraper.py"
  - "tests/test_incremental_scraper.py"
---

# Scraper Rules

## Incremental Scraper Design

The new `incremental_scraper.py` replaces the BFS crawler. It lives at project root (sibling to existing `scraper.py`, which is preserved as legacy).

### Sitemap Strategy

1. Try `https://docs.cyberark.com/sitemap.xml`
2. Try `https://docs.cyberark.com/sitemap_index.xml`
3. Handle sitemap index files recursively (up to depth 3)
4. XML namespace: `http://www.sitemaps.org/schemas/sitemap/0.9`
5. If no sitemap found, fall back to URL inventory from existing `scraped_docs/*.json`

### State Tracking

File: `scraper_state.json`
```json
{
  "last_run": "2026-02-24T12:00:00Z",
  "pages": {
    "https://docs.cyberark.com/...": {
      "lastmod": "2026-02-20T00:00:00Z",
      "content_hash": "a1b2c3d4e5f67890",
      "scraped_at": "2026-02-24T12:00:00Z"
    }
  }
}
```

### Incremental Logic

- Default mode: only scrape pages where sitemap `<lastmod>` > stored lastmod, or pages never seen
- `--full`: scrape all valid URLs regardless of state
- `--dry-run`: print what would be scraped, don't fetch
- Content hash: SHA-256 of page content (first 16 hex chars)

### URL Validation

- Must be on `docs.cyberark.com`
- Skip binary extensions: .pdf, .zip, .png, .jpg, .gif, .svg, .css, .js

### Page Extraction

Same logic as existing `scraper.py`: find main/article/content div, strip script/style/nav, normalize whitespace.

### Output

Same JSON format as existing scraper -- do not change:
```json
{"url": "...", "title": "...", "content": "...", "scraped_at": "..."}
```

### HTTP Settings

- User-Agent: `CyberArkRAGBot/2.0 (+https://github.com/infamousjoeg/cyberark-rag)`
- Default delay: 0.5s between requests (configurable via `--delay`)
- Use `requests.Session()` for connection pooling

### CLI

```
python incremental_scraper.py                  # incremental update
python incremental_scraper.py --full           # full re-scrape
python incremental_scraper.py --dry-run        # preview changes
python incremental_scraper.py --delay 1.0      # custom delay
python incremental_scraper.py --output-dir scraped_docs
```
