# Scraper Guide

Operating the documentation scraper for initial setup and ongoing updates.

## Incremental vs Full Scrape

| Mode | Command | Time | Use Case |
|---|---|---|---|
| Dry run | `python incremental_scraper.py --dry-run` | Seconds | Preview what would change |
| Incremental | `python incremental_scraper.py` | 2-10 min | Regular updates (default) |
| Full | `python incremental_scraper.py --full` | 2-4 hours | First run, or after major site restructuring |

**Incremental** (default): Compares sitemap `<lastmod>` timestamps against stored state. Only fetches pages that have changed since the last run.

**Full** (`--full`): Ignores stored state and re-scrapes every valid URL. Use this for the initial scrape or when you suspect the state file is out of sync.

**Dry run** (`--dry-run`): Shows what would be scraped without making any HTTP requests (except fetching the sitemap itself).

## CLI Reference

```bash
python incremental_scraper.py [OPTIONS]
```

| Flag | Default | Description |
|---|---|---|
| `--full` | false | Force re-scrape of all URLs regardless of state |
| `--dry-run` | false | Show what would be scraped without fetching |
| `--delay FLOAT` | `0.5` | Seconds between HTTP requests |
| `--output-dir PATH` | `scraped_docs` | Directory for output JSON files |

### Dry Run Example

```bash
$ python incremental_scraper.py --dry-run
Fetching sitemap from https://docs.cyberark.com/sitemap.xml...
Found 18,247 URLs in sitemap
Total valid URLs: 17,893
Pages to scrape: 42
  Would scrape: https://docs.cyberark.com/conjur-cloud/Latest/en/Content/Conjur/conjur-authn-k8s.htm
  Would scrape: https://docs.cyberark.com/privilege-cloud-standard/Latest/en/Content/PASIMP/PVWA-Overview.htm
  ... and 40 more
```

### Incremental Update Example

```bash
$ python incremental_scraper.py
Fetching sitemap from https://docs.cyberark.com/sitemap.xml...
Found 18,247 URLs in sitemap
Total valid URLs: 17,893
Pages to scrape: 42 (17,851 up to date)
Scraping page 1/42: https://docs.cyberark.com/conjur-cloud/Latest/en/Content/Conjur/conjur-authn-k8s.htm
Scraping page 2/42: https://docs.cyberark.com/privilege-cloud-standard/Latest/en/Content/PASIMP/PVWA-Overview.htm
...
Done. Scraped 42 pages in 1m 12s. Errors: 0.
```

### Full Scrape Example

```bash
$ python incremental_scraper.py --full
Fetching sitemap from https://docs.cyberark.com/sitemap.xml...
Found 18,247 URLs in sitemap
Total valid URLs: 17,893
Pages to scrape: 17,893 (full mode)
Scraping page 1/17893: ...
...
Done. Scraped 17,893 pages in 2h 45m. Errors: 12.
```

## State File (scraper_state.json)

The scraper tracks state in `scraper_state.json` at the project root.

### Structure

```json
{
  "last_run": "2026-02-25T12:34:56.789Z",
  "pages": {
    "https://docs.cyberark.com/conjur-cloud/Latest/en/Content/Conjur/conjur-authn-k8s.htm": {
      "lastmod": "2026-02-15T00:00:00Z",
      "content_hash": "a1b2c3d4e5f6g7h8",
      "scraped_at": "2026-02-15T10:30:00Z"
    }
  }
}
```

### Inspecting State

```bash
python3 -c "import json; s=json.load(open('scraper_state.json')); print(f'Last run: {s[\"last_run\"]}'); print(f'Pages tracked: {len(s[\"pages\"])}')"
```

### Resetting State

Delete the file. The next run treats every URL as new:

```bash
rm scraper_state.json
python incremental_scraper.py    # re-scrapes everything
```

## Automating Updates

### Cron Job (Weekly)

```bash
# Edit crontab
crontab -e

# Add weekly scrape + re-index (Sundays at 2 AM)
0 2 * * 0 cd /path/to/cyberark-rag && ./scripts/update.sh >> /tmp/cyberark-rag-update.log 2>&1
```

### Using the Update Script

The `scripts/update.sh` script runs an incremental scrape followed by a re-index:

```bash
$ ./scripts/update.sh
```

Pass flags through to the scraper:

```bash
$ ./scripts/update.sh --delay 1.0
$ ./scripts/update.sh --dry-run
```

### Full Rebuild Script

For a complete clean rebuild (scrape all + delete index + re-index):

```bash
$ ./scripts/full_rebuild.sh
```

This script prompts for confirmation before proceeding.

## Sitemap Behavior

### Normal Operation

The scraper fetches `https://docs.cyberark.com/sitemap.xml`. If the URL returns a sitemap index (multiple child sitemaps), it recursively fetches each child up to depth 3.

### Fallback: No Sitemap

If docs.cyberark.com returns no sitemap (404 or invalid XML), the scraper falls back to inventorying URLs from existing `scraped_docs/*.json` files. All existing URLs are re-scraped, equivalent to `--full` mode.

### URL Validation

The scraper only processes URLs that:
- Are on `docs.cyberark.com`
- Do not end with binary extensions (`.pdf`, `.zip`, `.png`, `.jpg`, `.gif`, `.svg`, `.css`, `.js`, `.ico`, `.woff`, `.woff2`, `.ttf`, `.eot`)

## Output Format

Each scraped page produces a JSON file in `scraped_docs/`:

```json
{
  "url": "https://docs.cyberark.com/conjur-cloud/Latest/en/Content/Conjur/conjur-authn-k8s.htm",
  "title": "Kubernetes Authenticator",
  "content": "The Conjur Kubernetes Authenticator enables workloads...",
  "scraped_at": "2026-02-25T10:30:00.000000"
}
```

Filenames are derived from URL paths with special characters replaced by underscores, truncated to 200 characters.

> **Warning:** Do not modify the JSON format. The indexer depends on the exact `{url, title, content, scraped_at}` structure.

## Legacy Scraper

The original BFS crawler (`scraper.py`) is preserved but not recommended. It crawls by following links (no sitemap), uses a 1.5-second delay, has no state tracking, and takes 8+ hours for a full crawl. Use the incremental scraper instead.

## Troubleshooting

### "No sitemap found"

Check the sitemap URL manually:

```bash
curl -s -o /dev/null -w "%{http_code}" https://docs.cyberark.com/sitemap.xml
```

If the sitemap is unavailable, the scraper falls back to existing doc inventory.

### "0 pages to scrape" in Incremental Mode

All pages are up to date, or the state file has future timestamps. Try:

```bash
python incremental_scraper.py --full
```

### Rate Limiting / 429 Errors

Increase the delay between requests:

```bash
python incremental_scraper.py --delay 2.0
```

### SSL Errors

Update your system certificates:

```bash
pip install --upgrade certifi
```

On macOS, you may also need to run the certificate installer:

```bash
/Applications/Python\ 3.13/Install\ Certificates.command
```
