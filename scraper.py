"""
CyberArk Documentation Scraper

This script scrapes documentation from docs.cyberark.com, extracting title, content,
and URL from each page. It crawls recursively while staying within the docs.cyberark.com domain.
"""

import os
import json
import time
import re
from urllib.parse import urljoin, urlparse
from datetime import datetime
from collections import deque

import requests
from bs4 import BeautifulSoup


class DocScraper:
    """
    Web scraper for CyberArk documentation.
    """

    def __init__(self, start_url="https://docs.cyberark.com/", output_dir="scraped_docs", delay=1.5, max_pages=None):
        """
        Initialize the documentation scraper.

        Args:
            start_url: Starting URL for scraping (default: docs.cyberark.com)
            output_dir: Directory to save scraped JSON files
            delay: Delay in seconds between requests (rate limiting)
            max_pages: Maximum number of pages to scrape (None for unlimited)
        """
        self.start_url = start_url
        self.output_dir = output_dir
        self.delay = delay
        self.max_pages = max_pages

        # Track visited URLs to avoid duplicates
        self.visited_urls = set()

        # Queue of URLs to visit
        self.url_queue = deque([start_url])

        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

        # Request headers to mimic a browser
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        # Session for connection pooling
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def is_valid_url(self, url):
        """
        Check if URL is within docs.cyberark.com domain.

        Args:
            url: URL to validate

        Returns:
            bool: True if URL is valid, False otherwise
        """
        try:
            parsed = urlparse(url)
            # Check if domain is docs.cyberark.com
            if parsed.netloc != 'docs.cyberark.com':
                return False
            # Exclude certain file types and fragments
            if any(url.lower().endswith(ext) for ext in ['.pdf', '.zip', '.png', '.jpg', '.gif', '.svg']):
                return False
            return True
        except Exception:
            return False

    def sanitize_filename(self, url):
        """
        Convert URL to a safe filename.

        Args:
            url: URL to sanitize

        Returns:
            str: Sanitized filename
        """
        # Remove protocol and domain
        parsed = urlparse(url)
        path = parsed.path

        # Remove leading/trailing slashes
        path = path.strip('/')

        # Replace slashes and special characters with underscores
        filename = re.sub(r'[^\w\-]', '_', path)

        # If empty, use 'index'
        if not filename:
            filename = 'index'

        # Limit length
        if len(filename) > 200:
            filename = filename[:200]

        return f"{filename}.json"

    def extract_page_data(self, url, soup):
        """
        Extract title and content from a page.

        Args:
            url: Page URL
            soup: BeautifulSoup object

        Returns:
            dict: Extracted data with title, content, url, and timestamp
        """
        # Extract title
        title = ""
        if soup.find('title'):
            title = soup.find('title').get_text().strip()
        elif soup.find('h1'):
            title = soup.find('h1').get_text().strip()

        # Extract main content
        # Try to find main content area (common in documentation sites)
        content = ""

        # Common content containers in documentation sites
        main_content = (
            soup.find('main') or
            soup.find('article') or
            soup.find('div', class_=re.compile(r'content|main|article|body', re.I)) or
            soup.find('div', id=re.compile(r'content|main|article|body', re.I))
        )

        if main_content:
            # Remove script and style elements
            for script in main_content(['script', 'style', 'nav', 'header', 'footer']):
                script.decompose()

            # Get text content
            content = main_content.get_text(separator='\n', strip=True)
        else:
            # Fallback: get all text from body
            if soup.find('body'):
                body = soup.find('body')
                for script in body(['script', 'style', 'nav', 'header', 'footer']):
                    script.decompose()
                content = body.get_text(separator='\n', strip=True)

        # Clean up extra whitespace
        content = re.sub(r'\n\s*\n', '\n\n', content)
        content = content.strip()

        return {
            'url': url,
            'title': title,
            'content': content,
            'scraped_at': datetime.utcnow().isoformat()
        }

    def extract_links(self, base_url, soup):
        """
        Extract all valid links from a page.

        Args:
            base_url: Base URL for resolving relative links
            soup: BeautifulSoup object

        Returns:
            list: List of valid URLs
        """
        links = []

        for link in soup.find_all('a', href=True):
            # Get absolute URL
            absolute_url = urljoin(base_url, link['href'])

            # Remove fragment
            absolute_url = absolute_url.split('#')[0]

            # Validate and add to list
            if self.is_valid_url(absolute_url) and absolute_url not in self.visited_urls:
                links.append(absolute_url)

        return links

    def scrape_page(self, url):
        """
        Scrape a single page.

        Args:
            url: URL to scrape

        Returns:
            tuple: (success: bool, new_links: list)
        """
        try:
            print(f"Scraping: {url}")

            # Make request
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            # Parse HTML
            soup = BeautifulSoup(response.content, 'lxml')

            # Extract page data
            page_data = self.extract_page_data(url, soup)

            # Save to JSON file
            filename = self.sanitize_filename(url)
            filepath = os.path.join(self.output_dir, filename)

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(page_data, f, indent=2, ensure_ascii=False)

            print(f"✓ Saved: {filename}")

            # Extract links for further crawling
            new_links = self.extract_links(url, soup)

            return True, new_links

        except requests.RequestException as e:
            print(f"✗ Request error for {url}: {e}")
            return False, []
        except Exception as e:
            print(f"✗ Error scraping {url}: {e}")
            return False, []

    def run(self):
        """
        Run the scraper.
        """
        print(f"Starting scraper from: {self.start_url}")
        print(f"Output directory: {self.output_dir}")
        print(f"Rate limit delay: {self.delay}s")
        if self.max_pages:
            print(f"Max pages: {self.max_pages}")
        print("-" * 60)

        pages_scraped = 0

        while self.url_queue and (self.max_pages is None or pages_scraped < self.max_pages):
            # Get next URL from queue
            url = self.url_queue.popleft()

            # Skip if already visited
            if url in self.visited_urls:
                continue

            # Mark as visited
            self.visited_urls.add(url)

            # Scrape the page
            success, new_links = self.scrape_page(url)

            if success:
                pages_scraped += 1

                # Add new links to queue
                for link in new_links:
                    if link not in self.visited_urls:
                        self.url_queue.append(link)

                print(f"Progress: {pages_scraped} pages scraped, {len(self.url_queue)} in queue")

            # Rate limiting
            time.sleep(self.delay)

        print("-" * 60)
        print(f"Scraping complete!")
        print(f"Total pages scraped: {pages_scraped}")
        print(f"Output directory: {self.output_dir}")


def main():
    """
    Main entry point for the scraper.
    """
    # Configuration
    START_URL = "https://docs.cyberark.com/"
    OUTPUT_DIR = "scraped_docs"
    DELAY = 1.5  # seconds between requests
    MAX_PAGES = None  # Set to a number for testing, None for unlimited

    # Create and run scraper
    scraper = DocScraper(
        start_url=START_URL,
        output_dir=OUTPUT_DIR,
        delay=DELAY,
        max_pages=MAX_PAGES
    )

    try:
        scraper.run()
    except KeyboardInterrupt:
        print("\n\nScraping interrupted by user.")
        print(f"Scraped {len(scraper.visited_urls)} pages before interruption.")
        print(f"Data saved in: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
