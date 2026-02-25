"""Tests for contextual retrieval chunk enrichment.

Covers context prefix generation, heading extraction, version extraction,
and the contextualize_chunks integration function.
"""

import pytest

from cyberark_rag.contextual_chunker import (
    _extract_nearest_heading,
    _extract_product_display_name,
    _extract_version,
    build_chunk_context,
    contextualize_chunks,
)


class TestProductDisplayName:
    """Verify product slug to display name conversion."""

    def test_conjur_cloud(self):
        assert _extract_product_display_name("conjur-cloud") == "Conjur Cloud"

    def test_pam_self_hosted(self):
        assert _extract_product_display_name("pam-self-hosted") == "Pam Self Hosted"

    def test_general(self):
        assert _extract_product_display_name("general") == "CyberArk"

    def test_empty(self):
        assert _extract_product_display_name("") == "CyberArk"

    def test_underscore_separated(self):
        result = _extract_product_display_name("secrets_hub")
        assert "Secrets" in result
        assert "Hub" in result


class TestVersionExtraction:
    """Verify version parsing from URL path segments."""

    @pytest.mark.parametrize("url,expected", [
        ("https://docs.cyberark.com/conjur-cloud/13.2/en/Content/page.htm", "13.2"),
        ("https://docs.cyberark.com/Product-Doc/v12/en/page.htm", "v12"),
        ("https://docs.cyberark.com/Product-Doc/latest/en/page.htm", "latest"),
        ("https://docs.cyberark.com/page.htm", None),
        ("https://docs.cyberark.com/pam-self-hosted/14.2/en/Content/PAS/page.htm", "14.2"),
    ])
    def test_version_extraction(self, url, expected):
        assert _extract_version(url) == expected


class TestHeadingExtraction:
    """Verify nearest heading detection above a chunk."""

    def test_markdown_heading(self):
        content = "# Overview\nSome text\n## Authentication\nChunk text here"
        assert _extract_nearest_heading(content, "Chunk text here") == "Authentication"

    def test_title_case_heading(self):
        content = "Getting Started Guide\nSome intro\nChunk text"
        assert _extract_nearest_heading(content, "Chunk text") == "Getting Started Guide"

    def test_no_heading(self):
        content = "Just some plain text without any headings at all."
        assert _extract_nearest_heading(content, "plain text") is None

    def test_empty_content(self):
        assert _extract_nearest_heading("", "chunk") is None

    def test_empty_chunk(self):
        assert _extract_nearest_heading("content", "") is None

    def test_chunk_not_found(self):
        content = "Some document content."
        chunk = "This text does not appear in the document at all in any way."
        assert _extract_nearest_heading(content, chunk) is None


class TestBuildChunkContext:
    """Verify context prefix construction from metadata."""

    def test_basic_prefix(self):
        prefix = build_chunk_context(
            url="https://docs.cyberark.com/conjur-cloud/Latest/en/Content/Conjur/auth.htm",
            title="Conjur Authentication",
            product_category="conjur-cloud",
            chunk_text="Configure the authenticator.",
            chunk_index=0,
            total_chunks=5,
            full_content="# Conjur Authentication\n\nConfigure the authenticator.",
        )
        assert prefix.startswith("From CyberArk Conjur Cloud documentation")
        assert "'Conjur Authentication'" in prefix
        assert prefix.endswith(". ")

    def test_with_section_heading(self):
        full_content = "## Setting Up Kubernetes\n\nDeploy the sidecar container."
        prefix = build_chunk_context(
            url="https://docs.cyberark.com/conjur-cloud/Latest/en/Content/page.htm",
            title="Setup Guide",
            product_category="conjur-cloud",
            chunk_text="Deploy the sidecar container.",
            chunk_index=1,
            total_chunks=5,
            full_content=full_content,
        )
        assert "Setting Up Kubernetes" in prefix

    def test_with_version(self):
        prefix = build_chunk_context(
            url="https://docs.cyberark.com/conjur-cloud/14.2/en/Content/page.htm",
            title="Page",
            product_category="conjur-cloud",
            chunk_text="Content",
            chunk_index=0,
            total_chunks=1,
            full_content="Content",
        )
        assert "version 14.2" in prefix

    def test_latest_version_not_shown(self):
        prefix = build_chunk_context(
            url="https://docs.cyberark.com/conjur-cloud/latest/en/Content/page.htm",
            title="Page",
            product_category="conjur-cloud",
            chunk_text="Content",
            chunk_index=0,
            total_chunks=1,
            full_content="Content",
        )
        # "latest" is the version string but the function skips it when == "latest"
        assert "version latest" not in prefix

    def test_empty_product_graceful(self):
        prefix = build_chunk_context(
            url="",
            title="",
            product_category="",
            chunk_text="Some text",
            chunk_index=0,
            total_chunks=1,
            full_content="Some text",
        )
        assert prefix.startswith("From CyberArk")
        assert prefix.endswith(". ")


class TestContextualizeChunks:
    """Integration tests for the full contextualization pipeline."""

    def test_preserves_original_text(self):
        chunks = [
            ("Step 1: Install.", {"url": "https://docs.cyberark.com/p/latest/en/c.htm", "title": "Setup", "product_category": "conjur-cloud", "chunk_index": 0}),
            ("Step 2: Configure.", {"url": "https://docs.cyberark.com/p/latest/en/c.htm", "title": "Setup", "product_category": "conjur-cloud", "chunk_index": 1}),
            ("Step 3: Verify.", {"url": "https://docs.cyberark.com/p/latest/en/c.htm", "title": "Setup", "product_category": "conjur-cloud", "chunk_index": 2}),
        ]
        full_content = "Step 1: Install.\n\nStep 2: Configure.\n\nStep 3: Verify."

        result = contextualize_chunks(chunks, full_content)

        assert len(result) == 3
        for ctx_text, meta in result:
            assert meta["original_text"] in ["Step 1: Install.", "Step 2: Configure.", "Step 3: Verify."]

    def test_adds_prefix_to_text(self):
        chunks = [
            ("Install Conjur.", {"url": "https://docs.cyberark.com/p/latest/en/c.htm", "title": "Setup", "product_category": "conjur-cloud", "chunk_index": 0}),
        ]
        result = contextualize_chunks(chunks, "Install Conjur.")

        ctx_text, meta = result[0]
        assert ctx_text.startswith(meta["context_prefix"])
        assert "Install Conjur." in ctx_text

    def test_stores_prefix_in_metadata(self):
        chunks = [
            ("Text.", {"url": "https://docs.cyberark.com/p/latest/en/c.htm", "title": "T", "product_category": "pc", "chunk_index": 0}),
        ]
        result = contextualize_chunks(chunks, "Text.")

        _, meta = result[0]
        assert "context_prefix" in meta
        assert meta["context_prefix"].startswith("From CyberArk")

    def test_metadata_keys_preserved(self):
        chunks = [
            ("Text.", {"url": "https://docs.cyberark.com/p/latest/en/c.htm", "title": "T", "product_category": "pc", "chunk_index": 0, "content_type": "guide"}),
        ]
        result = contextualize_chunks(chunks, "Text.")

        _, meta = result[0]
        assert meta["url"] == "https://docs.cyberark.com/p/latest/en/c.htm"
        assert meta["content_type"] == "guide"

    def test_empty_chunks(self):
        assert contextualize_chunks([], "content") == []
