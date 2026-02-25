"""Tests for the document indexer chunking and metadata extraction.

These tests validate the chunking algorithm and metadata logic WITHOUT
loading the embedding model or ChromaDB. We test chunk_text() and
extract_product_category() in isolation using a mock indexer.
"""

import pytest
from unittest.mock import MagicMock, patch

from cyberark_rag.config import Settings


# We avoid importing DocumentIndexer directly because it loads
# ChromaDB + SentenceTransformer at init. Instead we test the
# static/pure methods by patching the expensive __init__.


class TestExtractProductCategory:
    """Verify product category extraction from URLs."""

    def test_conjur_cloud_url(self):
        from cyberark_rag.indexer import DocumentIndexer
        # Patch __init__ to avoid loading models
        with patch.object(DocumentIndexer, "__init__", lambda self, **kw: None):
            indexer = DocumentIndexer()
            result = indexer.extract_product_category(
                "https://docs.cyberark.com/conjur-cloud/Latest/en/Content/Conjur/page.htm"
            )
            assert "conjur" in result.lower()

    def test_privilege_cloud_url(self):
        from cyberark_rag.indexer import DocumentIndexer
        with patch.object(DocumentIndexer, "__init__", lambda self, **kw: None):
            indexer = DocumentIndexer()
            result = indexer.extract_product_category(
                "https://docs.cyberark.com/privilege-cloud-standard/Latest/en/Content/PASIMP/page.htm"
            )
            assert result == "privilege-cloud-standard"

    def test_empty_url_returns_general(self):
        from cyberark_rag.indexer import DocumentIndexer
        with patch.object(DocumentIndexer, "__init__", lambda self, **kw: None):
            indexer = DocumentIndexer()
            assert indexer.extract_product_category("") == "general"


class TestChunking:
    """Test the chunk_text algorithm for size limits and overlap."""

    @pytest.fixture
    def indexer(self):
        """Create a minimal indexer with tiktoken but no model/DB."""
        from cyberark_rag.indexer import DocumentIndexer
        import tiktoken
        with patch.object(DocumentIndexer, "__init__", lambda self, **kw: None):
            idx = DocumentIndexer()
            idx.tokenizer = tiktoken.get_encoding("cl100k_base")
            idx.chunk_size = 50  # Small for testing
            idx.chunk_overlap = 10
            return idx

    def test_short_document_single_chunk(self, indexer):
        text = "This is a short document."
        metadata = {"url": "https://docs.cyberark.com/test", "title": "Test"}
        chunks = indexer.chunk_text(text, metadata)
        assert len(chunks) == 1
        assert chunks[0][0] == text

    def test_chunk_metadata_includes_chunk_index(self, indexer):
        text = "First paragraph.\n\nSecond paragraph."
        metadata = {"url": "https://test.com", "title": "Test"}
        chunks = indexer.chunk_text(text, metadata)
        for i, (_, meta) in enumerate(chunks):
            assert meta["chunk_index"] == i

    def test_long_document_produces_multiple_chunks(self, indexer):
        # Create a document that exceeds chunk_size (50 tokens)
        paragraphs = [f"Paragraph {i} with some content about CyberArk." for i in range(20)]
        text = "\n\n".join(paragraphs)
        metadata = {"url": "https://test.com", "title": "Test"}
        chunks = indexer.chunk_text(text, metadata)
        assert len(chunks) > 1

    def test_chunks_preserve_content(self, indexer):
        # All original content should appear in at least one chunk
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        metadata = {"url": "https://test.com", "title": "Test"}
        chunks = indexer.chunk_text(text, metadata)
        all_text = " ".join(chunk_text for chunk_text, _ in chunks)
        assert "First paragraph" in all_text
        assert "Second paragraph" in all_text
        assert "Third paragraph" in all_text

    def test_metadata_preserved_across_chunks(self, indexer):
        text = "Content " * 100  # Will produce multiple chunks
        metadata = {"url": "https://test.com", "title": "Test", "product_category": "conjur-cloud"}
        chunks = indexer.chunk_text(text, metadata)
        for _, meta in chunks:
            assert meta["url"] == "https://test.com"
            assert meta["title"] == "Test"
            assert meta["product_category"] == "conjur-cloud"
