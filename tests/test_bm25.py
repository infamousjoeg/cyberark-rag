"""Tests for BM25 keyword index.

Covers tokenization, index CRUD, BM25 scoring properties,
product filtering, and persistence.
"""

import pytest
from pathlib import Path

from cyberark_rag.bm25_index import BM25Index, tokenize


class TestTokenizer:
    """Verify tokenizer preserves CyberArk domain conventions."""

    def test_basic_words(self):
        assert tokenize("configure conjur kubernetes") == ["configure", "conjur", "kubernetes"]

    def test_preserves_hyphens(self):
        tokens = tokenize("privilege-cloud configuration")
        assert "privilege-cloud" in tokens
        assert "configuration" in tokens

    def test_preserves_aam_dap(self):
        tokens = tokenize("AAM-DAP secrets manager")
        assert "aam-dap" in tokens
        assert "secrets" in tokens
        assert "manager" in tokens

    def test_lowercase(self):
        assert tokenize("PVWA Error 401") == ["pvwa", "error", "401"]

    def test_single_char_words(self):
        assert tokenize("a b c") == ["a", "b", "c"]

    def test_strips_punctuation(self):
        tokens = tokenize("Hello, world! (test)")
        assert "hello" in tokens
        assert "world" in tokens
        assert "test" in tokens

    def test_empty_string(self):
        assert tokenize("") == []

    def test_cyberark_error_code(self):
        tokens = tokenize("Error APPAP001E occurred")
        assert "error" in tokens
        assert "appap001e" in tokens
        assert "occurred" in tokens


class TestBM25IndexCRUD:
    """Test add, build, and search lifecycle."""

    @pytest.fixture
    def index(self):
        """Build a small test index."""
        idx = BM25Index(k1=1.5, b=0.75)
        idx.add_document("doc1", "configure privilege-cloud PVWA for kubernetes", {"product_category": "privilege-cloud"})
        idx.add_document("doc2", "conjur cloud authentication JWT token", {"product_category": "conjur-cloud"})
        idx.add_document("doc3", "PVWA error 401 unauthorized access troubleshooting", {"product_category": "privilege-cloud"})
        idx.add_document("doc4", "install credential provider on linux server", {"product_category": "pam-self-hosted"})
        idx.build()
        return idx

    def test_add_document_and_build(self, index):
        assert index.n_docs == 4
        assert index.avg_dl > 0

    def test_search_returns_ranked_results(self, index):
        results = index.search("PVWA error 401")
        assert len(results) > 0
        assert results[0]["doc_id"] == "doc3"
        # Scores should be descending
        for i in range(len(results) - 1):
            assert results[i]["score"] >= results[i + 1]["score"]

    def test_search_exact_match(self, index):
        results = index.search("PVWA error 401")
        assert results[0]["doc_id"] == "doc3"

    def test_search_hyphenated_term(self, index):
        results = index.search("privilege-cloud")
        doc_ids = [r["doc_id"] for r in results]
        assert "doc1" in doc_ids

    def test_search_empty_query(self, index):
        assert index.search("") == []

    def test_search_no_matching_terms(self, index):
        assert index.search("quantum") == []

    def test_search_respects_top_k(self, index):
        results = index.search("PVWA", top_k=1)
        assert len(results) <= 1

    def test_search_returns_metadata(self, index):
        results = index.search("conjur")
        assert len(results) > 0
        assert "metadata" in results[0]
        assert "product_category" in results[0]["metadata"]


class TestProductFilter:
    """Verify product_category filtering in search."""

    @pytest.fixture
    def index(self):
        idx = BM25Index()
        idx.add_document("d1", "PVWA configure setup", {"product_category": "privilege-cloud"})
        idx.add_document("d2", "conjur PVWA integration", {"product_category": "conjur-cloud"})
        idx.add_document("d3", "PVWA troubleshooting guide", {"product_category": "privilege-cloud"})
        idx.build()
        return idx

    def test_filter_constrains_results(self, index):
        results = index.search("PVWA", filter_product="privilege-cloud")
        for r in results:
            assert r["metadata"]["product_category"] == "privilege-cloud"

    def test_filter_no_match_returns_empty(self, index):
        results = index.search("PVWA", filter_product="nonexistent-product")
        assert results == []


class TestBM25Scoring:
    """Verify BM25 scoring properties (IDF, TF saturation)."""

    def test_idf_rare_term_scores_higher(self):
        idx = BM25Index()
        idx.add_document("rare", "common rare-term common", {})
        for i in range(9):
            idx.add_document(f"common_{i}", "common common common", {})
        idx.build()

        results = idx.search("rare-term common")
        assert len(results) > 0
        assert results[0]["doc_id"] == "rare"

    def test_tf_saturation(self):
        idx = BM25Index(k1=1.5)
        idx.add_document("many", " ".join(["kubernetes"] * 50), {})
        idx.add_document("few", " ".join(["kubernetes"] * 5), {})
        idx.build()

        results = idx.search("kubernetes")
        scores = {r["doc_id"]: r["score"] for r in results}
        # TF saturation means 50x terms should NOT produce 10x the score
        ratio = scores["many"] / scores["few"]
        assert ratio < 10


class TestPersistence:
    """Verify save/load round-trip fidelity."""

    def test_save_load_roundtrip(self, tmp_path):
        idx = BM25Index(k1=1.5, b=0.75)
        for i in range(5):
            idx.add_document(f"doc{i}", f"content for document {i} kubernetes conjur", {"chunk_index": i})
        idx.build()

        path = tmp_path / "test_bm25.pkl"
        idx.save(path)

        loaded = BM25Index.load(path)
        assert loaded.n_docs == idx.n_docs
        assert loaded._built

        orig = idx.search("kubernetes")
        reloaded = loaded.search("kubernetes")
        assert len(orig) == len(reloaded)
        assert orig[0]["doc_id"] == reloaded[0]["doc_id"]

    def test_load_nonexistent_file_raises(self):
        with pytest.raises(FileNotFoundError):
            BM25Index.load(Path("/tmp/nonexistent_bm25.pkl"))


class TestEdgeCases:
    """Guard against degenerate inputs."""

    def test_empty_index(self):
        idx = BM25Index()
        idx.build()
        assert idx.search("anything") == []

    def test_search_before_build_raises(self):
        idx = BM25Index()
        idx.add_document("doc1", "test content")
        with pytest.raises(RuntimeError):
            idx.search("test")
