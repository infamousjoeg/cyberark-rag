"""
Sitemap-driven Incremental Scraper for CyberArk Documentation

Replaces the BFS crawler (8+ hours) with a sitemap-driven approach (2-10 minutes
for incremental updates). Maintains state to only scrape pages that have changed.

Usage:
    python incremental_scraper.py              # incremental update
    python incremental_scraper.py --full       # full re-scrape
    python incremental_scraper.py --dry-run    # preview changes
    python incremental_scraper.py --delay 1.0  # custom delay
"""

import argparse
import hashlib
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup

from cyberark_rag.config import Settings
from cyberark_rag.logging_config import setup_logging

logger = setup_logging(__name__)

# Sitemap XML namespace
SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

# Binary/non-HTML extensions to skip
SKIP_EXTENSIONS = frozenset({
    ".pdf", ".zip", ".png", ".jpg", ".jpeg", ".gif", ".svg",
    ".css", ".js", ".ico", ".woff", ".woff2", ".ttf", ".eot",
})

USER_AGENT = "CyberArkRAGBot/2.0 (+https://github.com/infamousjoeg/cyberark-rag)"


class ScraperState:
    """Tracks per-URL scraping state for incremental updates."""

    def __init__(self, state_file: Path = None):
        """
        Initialize scraper state.

        Args:
            state_file: Path to state JSON file
        """
        self.state_file = state_file or Settings.STATE_FILE
        self.data: Dict = {"last_run": None, "pages": {}}
        self._load()

    def _load(self) -> None:
        """Load state from disk if it exists."""
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
                logger.info("Loaded state: %d tracked pages", len(self.data.get("pages", {})))
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load state file, starting fresh: %s", e)
                self.data = {"last_run": None, "pages": {}}

    def save(self) -> None:
        """Persist state to disk."""
        self.data["last_run"] = datetime.now(tz=timezone.utc).isoformat()
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)
        logger.info("Saved state: %d tracked pages", len(self.data["pages"]))

    def needs_update(self, url: str, lastmod: Optional[str] = None) -> bool:
        """
        Check if a URL needs to be (re-)scraped.

        Args:
            url: The page URL
            lastmod: Sitemap lastmod timestamp (ISO format), or None

        Returns:
            True if the page should be scraped
        """
        page_state = self.data.get("pages", {}).get(url)
        if page_state is None:
            return True  # Never seen
        if lastmod is None:
            return False  # No new lastmod info, assume unchanged
        stored_lastmod = page_state.get("lastmod")
        if stored_lastmod is None:
            return True
        return lastmod > stored_lastmod

    def record(self, url: str, content_hash: str, lastmod: Optional[str] = None) -> None:
        """
        Record that a URL was successfully scraped.

        Args:
            url: The page URL
            content_hash: SHA-256 hash (first 16 hex chars) of content
            lastmod: Sitemap lastmod timestamp
        """
        if "pages" not in self.data:
            self.data["pages"] = {}
        self.data["pages"][url] = {
            "lastmod": lastmod,
            "content_hash": content_hash,
            "scraped_at": datetime.now(tz=timezone.utc).isoformat(),
        }


def content_hash(text: str) -> str:
    """Return first 16 hex chars of SHA-256 hash of text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def is_valid_doc_url(url: str) -> bool:
    """
    Validate that a URL is a scrapable docs.cyberark.com page.

    Args:
        url: URL to check

    Returns:
        True if the URL should be scraped
    """
    try:
        parsed = urlparse(url)
        if parsed.netloc != "docs.cyberark.com":
            return False
        path_lower = parsed.path.lower()
        for ext in SKIP_EXTENSIONS:
            if path_lower.endswith(ext):
                return False
        return True
    except Exception:
        return False


def sanitize_filename(url: str) -> str:
    """
    Convert URL to a safe filename matching existing scraper output.

    Args:
        url: URL to convert

    Returns:
        Safe filename ending in .json
    """
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    filename = re.sub(r"[^\w\-]", "_", path)
    if not filename:
        filename = "index"
    if len(filename) > 200:
        filename = filename[:200]
    return f"{filename}.json"


class IncrementalScraper:
    """Sitemap-driven incremental scraper for docs.cyberark.com."""

    def __init__(
        self,
        output_dir: Path = None,
        delay: float = 0.5,
        full: bool = False,
        dry_run: bool = False,
        max_pages: int = 0,
        include_products: List[str] = None,
        exclude_products: List[str] = None,
    ):
        """
        Initialize the incremental scraper.

        Args:
            output_dir: Directory to write scraped JSON files
            delay: Seconds to wait between requests
            full: If True, scrape all URLs regardless of state
            dry_run: If True, report what would be done without fetching
            max_pages: Maximum pages to scrape (0 = unlimited)
            include_products: Only scrape URLs whose first path segment matches
            exclude_products: Skip URLs whose first path segment matches
        """
        self.output_dir = output_dir or Settings.DOCS_DIR
        self.delay = delay
        self.full = full
        self.dry_run = dry_run
        self.max_pages = max_pages
        self.include_products = include_products
        self.exclude_products = exclude_products

        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

        self.state = ScraperState()

        # Counters
        self.scraped = 0
        self.skipped = 0
        self.errors = 0

        # Set to True when BFS crawl already scraped pages during discovery
        self._crawl_scraped = False

    @staticmethod
    def _extract_product_slug(url: str) -> str:
        """Extract the first URL path segment (product slug) from a URL."""
        try:
            path = urlparse(url).path.strip("/")
            return path.split("/")[0] if path else ""
        except Exception:
            return ""

    # ------------------------------------------------------------------
    # Sitemap parsing
    # ------------------------------------------------------------------

    def fetch_sitemap_urls(self) -> List[Tuple[str, Optional[str]]]:
        """
        Discover URLs from docs.cyberark.com sitemap(s).

        Tries in order:
          1. Sitemap XML (sitemap.xml, sitemap_index.xml)
          2. Existing scraped_docs inventory
          3. BFS crawl starting from docs.cyberark.com root

        Returns:
            List of (url, lastmod) tuples. lastmod may be None.
        """
        sitemap_candidates = [
            "https://docs.cyberark.com/sitemap.xml",
            "https://docs.cyberark.com/sitemap_index.xml",
        ]

        for sitemap_url in sitemap_candidates:
            try:
                urls = self._parse_sitemap(sitemap_url, depth=0)
                if urls:
                    logger.info("Discovered %d URLs from %s", len(urls), sitemap_url)
                    return urls
            except Exception as e:
                logger.debug("Sitemap %s failed: %s", sitemap_url, e)

        # Fallback 1: inventory existing scraped docs
        logger.warning("No sitemap found, falling back to existing scraped_docs inventory")
        existing = self._inventory_existing_docs()
        if existing:
            return existing

        # Fallback 2: BFS crawl from root
        logger.info("No existing docs found, starting BFS crawl from docs.cyberark.com")
        return self._crawl_discover_urls()

    def _parse_sitemap(
        self, url: str, depth: int = 0
    ) -> List[Tuple[str, Optional[str]]]:
        """
        Parse a sitemap XML, handling sitemap index files recursively.

        Args:
            url: Sitemap URL
            depth: Current recursion depth (max 3)

        Returns:
            List of (page_url, lastmod) tuples
        """
        if depth > 3:
            logger.warning("Sitemap recursion depth exceeded at %s", url)
            return []

        response = self.session.get(url, timeout=30)
        response.raise_for_status()

        try:
            root = ElementTree.fromstring(response.content)
        except ElementTree.ParseError as e:
            logger.warning("Failed to parse sitemap XML from %s: %s", url, e)
            return []
        tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag

        results: List[Tuple[str, Optional[str]]] = []

        if tag == "sitemapindex":
            # Sitemap index -- recurse into child sitemaps
            for sitemap_elem in root.findall("sm:sitemap", SITEMAP_NS):
                loc_elem = sitemap_elem.find("sm:loc", SITEMAP_NS)
                if loc_elem is not None and loc_elem.text:
                    child_urls = self._parse_sitemap(loc_elem.text.strip(), depth + 1)
                    results.extend(child_urls)
        elif tag == "urlset":
            # Regular sitemap -- extract page URLs
            for url_elem in root.findall("sm:url", SITEMAP_NS):
                loc_elem = url_elem.find("sm:loc", SITEMAP_NS)
                lastmod_elem = url_elem.find("sm:lastmod", SITEMAP_NS)

                if loc_elem is not None and loc_elem.text:
                    page_url = loc_elem.text.strip()
                    lastmod = lastmod_elem.text.strip() if lastmod_elem is not None and lastmod_elem.text else None
                    if is_valid_doc_url(page_url):
                        results.append((page_url, lastmod))

        return results

    def _inventory_existing_docs(self) -> List[Tuple[str, Optional[str]]]:
        """
        Build URL list from existing scraped_docs JSON files.

        Returns:
            List of (url, None) tuples
        """
        results: List[Tuple[str, Optional[str]]] = []
        docs_dir = self.output_dir

        if not docs_dir.exists():
            return results

        for json_file in sorted(docs_dir.glob("*.json")):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    doc = json.load(f)
                url = doc.get("url", "")
                if url and is_valid_doc_url(url):
                    results.append((url, None))
            except (json.JSONDecodeError, OSError):
                continue

        logger.info("Inventoried %d URLs from existing scraped docs", len(results))
        return results

    def _crawl_discover_urls(self) -> List[Tuple[str, Optional[str]]]:
        """
        BFS crawl from docs.cyberark.com to discover and scrape page URLs.

        Used as a last-resort fallback when no sitemap exists and no
        existing scraped_docs are available (e.g. fresh Docker build).
        Follows links within docs.cyberark.com, applying product filters
        during discovery.

        Pages are saved as they are crawled (to avoid double-fetching),
        with state recorded so that run() will skip already-scraped URLs.

        Returns:
            List of (url, None) tuples for all discovered URLs
        """
        from collections import deque

        start_url = "https://docs.cyberark.com/"
        visited: Set[str] = set()
        queue: deque = deque([start_url])
        discovered: List[Tuple[str, Optional[str]]] = []

        # Crawl limit: max_pages caps how many pages to scrape (0 = unlimited)
        crawl_limit = self.max_pages if self.max_pages > 0 else 25000

        # Ensure output directory exists for saving pages during crawl
        self.output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            "BFS crawl starting (limit: %d URLs, delay: %.1fs)",
            crawl_limit,
            self.delay,
        )

        while queue and len(discovered) < crawl_limit:
            url = queue.popleft()

            # Normalize: strip fragment
            url = url.split("#")[0]

            if url in visited:
                continue
            visited.add(url)

            if not is_valid_doc_url(url):
                continue

            # Apply product filters early to avoid wasting time on excluded products
            product_slug = self._extract_product_slug(url)
            if self.include_products and product_slug and product_slug not in self.include_products:
                continue
            if self.exclude_products and product_slug and product_slug in self.exclude_products:
                continue

            discovered.append((url, None))

            # Fetch page, extract links, and save content in one pass
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()

                # Extract and save page data (avoids re-fetching in run())
                page_data = self.extract_page_data(url, response.content)
                if page_data["content"] and len(page_data["content"]) >= 50:
                    filename = sanitize_filename(url)
                    filepath = self.output_dir / filename
                    with open(filepath, "w", encoding="utf-8") as f:
                        json.dump(page_data, f, indent=2, ensure_ascii=False)
                    chash = content_hash(page_data["content"])
                    self.state.record(url, chash, None)
                    self.scraped += 1

                # Extract links for further crawling
                soup = BeautifulSoup(response.content, "lxml")
                for link_tag in soup.find_all("a", href=True):
                    href = link_tag["href"]
                    absolute = urljoin(url, href).split("#")[0]
                    if absolute not in visited and is_valid_doc_url(absolute):
                        queue.append(absolute)

            except Exception as e:
                logger.debug("Crawl fetch error for %s: %s", url, e)
                self.errors += 1

            # Rate limiting
            if queue:
                time.sleep(self.delay)

            # Progress logging every 100 pages
            if len(discovered) % 100 == 0 and len(discovered) > 0:
                logger.info(
                    "BFS crawl progress: %d discovered, %d scraped, %d in queue",
                    len(discovered),
                    self.scraped,
                    len(queue),
                )

        # Save state after crawl so run() knows these pages are done
        if self.scraped > 0:
            self.state.save()
            self._crawl_scraped = True

        logger.info(
            "BFS crawl complete: %d URLs discovered, %d pages scraped (visited %d)",
            len(discovered),
            self.scraped,
            len(visited),
        )
        return discovered

    # ------------------------------------------------------------------
    # Page extraction (matches existing scraper.py logic)
    # ------------------------------------------------------------------

    def extract_page_data(self, url: str, html: bytes) -> Dict:
        """
        Extract title and content from HTML, matching existing scraper output format.

        Args:
            url: Page URL
            html: Raw HTML bytes

        Returns:
            Dictionary with url, title, content, scraped_at
        """
        soup = BeautifulSoup(html, "lxml")

        # Extract title
        title = ""
        title_tag = soup.find("title")
        if title_tag:
            title = title_tag.get_text().strip()
        elif soup.find("h1"):
            title = soup.find("h1").get_text().strip()

        # Extract main content
        content = ""
        main_content = (
            soup.find("main")
            or soup.find("article")
            or soup.find("div", class_=re.compile(r"content|main|article|body", re.I))
            or soup.find("div", id=re.compile(r"content|main|article|body", re.I))
        )

        if main_content:
            for tag in main_content(["script", "style", "nav", "header", "footer"]):
                tag.decompose()
            content = main_content.get_text(separator="\n", strip=True)
        elif soup.find("body"):
            body = soup.find("body")
            for tag in body(["script", "style", "nav", "header", "footer"]):
                tag.decompose()
            content = body.get_text(separator="\n", strip=True)

        # Normalize whitespace
        content = re.sub(r"\n\s*\n", "\n\n", content).strip()

        return {
            "url": url,
            "title": title,
            "content": content,
            "scraped_at": datetime.utcnow().isoformat(),
        }

    # ------------------------------------------------------------------
    # Main scraping loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Run the incremental scraping pipeline."""
        mode = "FULL" if self.full else "INCREMENTAL"
        if self.dry_run:
            mode += " (DRY RUN)"
        logger.info("Starting %s scrape", mode)
        logger.info("Output directory: %s", self.output_dir)

        # Discover URLs
        url_list = self.fetch_sitemap_urls()
        if not url_list:
            logger.error("No URLs discovered. Nothing to scrape.")
            return

        logger.info("Total URLs discovered: %d", len(url_list))

        # If BFS crawl already scraped pages during discovery, skip re-scraping
        if self._crawl_scraped:
            logger.info(
                "BFS crawl already scraped %d pages. Skipping re-scrape.",
                self.scraped,
            )
            logger.info(
                "Scraping complete: %d scraped, %d skipped, %d errors",
                self.scraped, self.skipped, self.errors,
            )
            return

        # Filter to only URLs that need updating and match product filters
        urls_to_scrape: List[Tuple[str, Optional[str]]] = []
        for url, lastmod in url_list:
            # Apply product filters based on the first URL path segment
            product_slug = self._extract_product_slug(url)
            if self.include_products and product_slug not in self.include_products:
                self.skipped += 1
                continue
            if self.exclude_products and product_slug in self.exclude_products:
                self.skipped += 1
                continue

            if self.full or self.state.needs_update(url, lastmod):
                urls_to_scrape.append((url, lastmod))
            else:
                self.skipped += 1

        # Apply max_pages limit
        if self.max_pages > 0 and len(urls_to_scrape) > self.max_pages:
            logger.info(
                "Limiting scrape to %d of %d pages (--max-pages)",
                self.max_pages,
                len(urls_to_scrape),
            )
            urls_to_scrape = urls_to_scrape[:self.max_pages]

        logger.info(
            "URLs to scrape: %d (skipping %d unchanged)",
            len(urls_to_scrape),
            self.skipped,
        )

        if self.dry_run:
            for url, lastmod in urls_to_scrape[:20]:
                print(f"  Would scrape: {url}" + (f" (lastmod: {lastmod})" if lastmod else ""))
            if len(urls_to_scrape) > 20:
                print(f"  ... and {len(urls_to_scrape) - 20} more")
            return

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Scrape each URL
        for i, (url, lastmod) in enumerate(urls_to_scrape, 1):
            try:
                logger.info("[%d/%d] Scraping: %s", i, len(urls_to_scrape), url)

                response = self.session.get(url, timeout=30)
                response.raise_for_status()

                page_data = self.extract_page_data(url, response.content)

                # Skip pages with no meaningful content
                if not page_data["content"] or len(page_data["content"]) < 50:
                    logger.debug("Skipping %s (no meaningful content)", url)
                    self.skipped += 1
                    continue

                # Save JSON file
                filename = sanitize_filename(url)
                filepath = self.output_dir / filename
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(page_data, f, indent=2, ensure_ascii=False)

                # Update state
                chash = content_hash(page_data["content"])
                self.state.record(url, chash, lastmod)
                self.scraped += 1

            except requests.RequestException as e:
                logger.warning("Request error for %s: %s", url, e)
                self.errors += 1
            except Exception as e:
                logger.error("Error scraping %s: %s", url, e)
                self.errors += 1

            # Rate limiting
            if i < len(urls_to_scrape):
                time.sleep(self.delay)

        # Save state
        self.state.save()

        # Summary
        logger.info("Scraping complete: %d scraped, %d skipped, %d errors",
                     self.scraped, self.skipped, self.errors)


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Incremental scraper for docs.cyberark.com"
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Full re-scrape (ignore state, scrape all URLs)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be scraped without fetching",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Delay between requests in seconds (default: 0.5)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory for scraped JSON files",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=0,
        help="Maximum pages to scrape (0 = unlimited, useful for CI/Docker builds)",
    )
    parser.add_argument(
        "--include-products",
        type=str,
        default=None,
        help="Comma-separated product URL slugs to include (e.g., 'conjur-cloud,privilege-cloud-standard')",
    )
    parser.add_argument(
        "--exclude-products",
        type=str,
        default=None,
        help="Comma-separated product URL slugs to exclude (e.g., 'pam-self-hosted,secrets-manager-sh')",
    )

    args = parser.parse_args()

    include_products = args.include_products.split(",") if args.include_products else None
    exclude_products = args.exclude_products.split(",") if args.exclude_products else None

    scraper = IncrementalScraper(
        output_dir=args.output_dir,
        delay=args.delay,
        full=args.full,
        dry_run=args.dry_run,
        max_pages=args.max_pages,
        include_products=include_products,
        exclude_products=exclude_products,
    )
    scraper.run()


if __name__ == "__main__":
    main()
