"""Tests for the sitemap-driven incremental scraper.

Covers sitemap XML parsing, URL validation, state management,
incremental logic, content hashing, and filename sanitization.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from incremental_scraper import (
    IncrementalScraper,
    ScraperState,
    content_hash,
    is_valid_doc_url,
    sanitize_filename,
)


# ------------------------------------------------------------------
# URL validation (parameterized per test-specs.md)
# ------------------------------------------------------------------

class TestUrlValidation:
    """Verify URL filtering for docs.cyberark.com pages."""

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
    def test_url_validation(self, url, valid):
        assert is_valid_doc_url(url) == valid


# ------------------------------------------------------------------
# Filename sanitization
# ------------------------------------------------------------------

class TestSanitizeFilename:
    """Verify URL-to-filename conversion."""

    def test_preserves_meaningful_path(self):
        result = sanitize_filename("https://docs.cyberark.com/conjur-cloud/latest/en/Content/Get-Started.htm")
        assert result.endswith(".json")
        assert "/" not in result
        assert "conjur" in result.lower()

    def test_root_url_returns_index(self):
        assert sanitize_filename("https://docs.cyberark.com/") == "index.json"

    def test_truncates_long_paths(self):
        long_path = "https://docs.cyberark.com/" + "a" * 300
        result = sanitize_filename(long_path)
        assert len(result) <= 205  # 200 + ".json"


# ------------------------------------------------------------------
# Content hashing
# ------------------------------------------------------------------

class TestContentHash:
    """Verify SHA-256 content fingerprinting."""

    def test_deterministic(self):
        assert content_hash("hello") == content_hash("hello")

    def test_is_16_hex_chars(self):
        h = content_hash("test content")
        assert len(h) == 16
        assert all(c in "0123456789abcdef" for c in h)

    def test_different_content_different_hash(self):
        assert content_hash("hello") != content_hash("world")


# ------------------------------------------------------------------
# State management
# ------------------------------------------------------------------

class TestScraperState:
    """Verify state persistence and incremental update logic."""

    def test_fresh_start(self, tmp_path):
        state = ScraperState(state_file=tmp_path / "state.json")
        assert state.data == {"last_run": None, "pages": {}}

    def test_new_url_needs_update(self, tmp_path):
        state = ScraperState(state_file=tmp_path / "state.json")
        assert state.needs_update("https://docs.cyberark.com/new-page")

    def test_recorded_url_no_new_lastmod(self, tmp_path):
        state = ScraperState(state_file=tmp_path / "state.json")
        state.record("https://docs.cyberark.com/page", "abc123", "2026-01-01T00:00:00Z")
        assert not state.needs_update("https://docs.cyberark.com/page", None)

    def test_recorded_url_same_lastmod(self, tmp_path):
        state = ScraperState(state_file=tmp_path / "state.json")
        state.record("https://docs.cyberark.com/page", "abc123", "2026-01-01T00:00:00Z")
        assert not state.needs_update("https://docs.cyberark.com/page", "2026-01-01T00:00:00Z")

    def test_recorded_url_newer_lastmod(self, tmp_path):
        state = ScraperState(state_file=tmp_path / "state.json")
        state.record("https://docs.cyberark.com/page", "abc123", "2026-01-01T00:00:00Z")
        assert state.needs_update("https://docs.cyberark.com/page", "2026-02-01T00:00:00Z")

    def test_no_lastmod_in_state_needs_update(self, tmp_path):
        state = ScraperState(state_file=tmp_path / "state.json")
        state.record("https://docs.cyberark.com/page", "abc123", None)
        # If state has no lastmod but sitemap does, we need update
        assert state.needs_update("https://docs.cyberark.com/page", "2026-01-01T00:00:00Z")

    def test_save_load_roundtrip(self, tmp_path):
        state_file = tmp_path / "state.json"
        state = ScraperState(state_file=state_file)
        state.record("https://docs.cyberark.com/page", "abc123", "2026-01-01T00:00:00Z")
        state.save()

        state2 = ScraperState(state_file=state_file)
        assert not state2.needs_update("https://docs.cyberark.com/page", "2026-01-01T00:00:00Z")
        assert state2.needs_update("https://docs.cyberark.com/page", "2026-03-01T00:00:00Z")

    def test_save_updates_last_run(self, tmp_path):
        state_file = tmp_path / "state.json"
        state = ScraperState(state_file=state_file)
        state.save()

        with open(state_file, "r") as f:
            data = json.load(f)
        assert data["last_run"] is not None
        assert "T" in data["last_run"]  # ISO timestamp

    def test_handles_missing_file(self, tmp_path):
        state = ScraperState(state_file=tmp_path / "nonexistent.json")
        assert state.data["pages"] == {}


# ------------------------------------------------------------------
# Sitemap XML parsing
# ------------------------------------------------------------------

class TestSitemapParsing:
    """Verify sitemap and sitemap index XML parsing."""

    def test_parse_simple_sitemap(self, tmp_path):
        scraper = IncrementalScraper(output_dir=tmp_path, dry_run=True)

        xml_content = b"""<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url>
                <loc>https://docs.cyberark.com/conjur-cloud/latest/en/Content/Get-Started.htm</loc>
                <lastmod>2026-01-15T00:00:00Z</lastmod>
            </url>
            <url>
                <loc>https://docs.cyberark.com/pam-self-hosted/latest/en/Content/PASIMP/Overview.htm</loc>
            </url>
            <url>
                <loc>https://docs.cyberark.com/file.pdf</loc>
            </url>
        </urlset>"""

        mock_response = MagicMock()
        mock_response.content = xml_content
        mock_response.raise_for_status = MagicMock()
        scraper.session.get = MagicMock(return_value=mock_response)

        urls = scraper._parse_sitemap("https://docs.cyberark.com/sitemap.xml")

        assert len(urls) == 2
        assert urls[0][0] == "https://docs.cyberark.com/conjur-cloud/latest/en/Content/Get-Started.htm"
        assert urls[0][1] == "2026-01-15T00:00:00Z"
        assert urls[1][1] is None  # Missing lastmod

    def test_parse_sitemap_index_recursive(self, tmp_path):
        scraper = IncrementalScraper(output_dir=tmp_path, dry_run=True)

        index_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
        <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <sitemap>
                <loc>https://docs.cyberark.com/sitemap1.xml</loc>
            </sitemap>
        </sitemapindex>"""

        child_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url>
                <loc>https://docs.cyberark.com/page1.htm</loc>
                <lastmod>2026-02-01T00:00:00Z</lastmod>
            </url>
        </urlset>"""

        call_count = 0
        responses = [
            MagicMock(content=index_xml, raise_for_status=MagicMock()),
            MagicMock(content=child_xml, raise_for_status=MagicMock()),
        ]

        def side_effect(*args, **kwargs):
            nonlocal call_count
            resp = responses[call_count]
            call_count += 1
            return resp

        scraper.session.get = MagicMock(side_effect=side_effect)

        urls = scraper._parse_sitemap("https://docs.cyberark.com/sitemap.xml")
        assert len(urls) == 1
        assert urls[0][0] == "https://docs.cyberark.com/page1.htm"

    def test_parse_invalid_xml_returns_empty(self, tmp_path):
        scraper = IncrementalScraper(output_dir=tmp_path, dry_run=True)

        mock_response = MagicMock()
        mock_response.content = b"this is not valid xml"
        mock_response.raise_for_status = MagicMock()
        scraper.session.get = MagicMock(return_value=mock_response)

        # Should not raise, should return empty
        urls = scraper._parse_sitemap("https://docs.cyberark.com/sitemap.xml")
        assert urls == []

    def test_parse_respects_depth_limit(self, tmp_path):
        scraper = IncrementalScraper(output_dir=tmp_path, dry_run=True)

        # A sitemap index pointing to itself would recurse forever without depth limit
        index_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
        <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <sitemap>
                <loc>https://docs.cyberark.com/sitemap.xml</loc>
            </sitemap>
        </sitemapindex>"""

        mock_response = MagicMock()
        mock_response.content = index_xml
        mock_response.raise_for_status = MagicMock()
        scraper.session.get = MagicMock(return_value=mock_response)

        # Should stop at depth 3, not recurse infinitely
        urls = scraper._parse_sitemap("https://docs.cyberark.com/sitemap.xml", depth=0)
        # Will return empty because it hits depth limit before finding urlset entries
        assert isinstance(urls, list)


# ------------------------------------------------------------------
# Dry run behavior
# ------------------------------------------------------------------

class TestDryRun:
    """Verify dry-run mode does not make page requests."""

    def test_dry_run_does_not_scrape(self, tmp_path):
        scraper = IncrementalScraper(output_dir=tmp_path, dry_run=True)

        # Mock session to track calls
        call_log = []
        original_get = scraper.session.get

        def tracking_get(*args, **kwargs):
            call_log.append(args[0] if args else kwargs.get("url", "unknown"))
            mock_resp = MagicMock()
            mock_resp.content = b"""<?xml version="1.0" encoding="UTF-8"?>
            <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
                <url>
                    <loc>https://docs.cyberark.com/page1.htm</loc>
                    <lastmod>2026-02-01T00:00:00Z</lastmod>
                </url>
            </urlset>"""
            mock_resp.raise_for_status = MagicMock()
            return mock_resp

        scraper.session.get = tracking_get

        scraper.run()

        # Should have called get for sitemap URLs, but not for page URLs
        page_calls = [c for c in call_log if "page1.htm" in str(c) and "sitemap" not in str(c)]
        assert len(page_calls) == 0
