"""Tests for Reciprocal Rank Fusion hybrid search.

Covers deduplication, weight effects, k parameter, metadata preservation,
and edge cases with empty inputs.
"""

import pytest

from cyberark_rag.hybrid_search import hybrid_search, _result_key


def _make_result(url: str, chunk_index: int, score: float = 0.0, **kwargs) -> dict:
    """Helper to create a search result dict."""
    result = {
        "url": url,
        "chunk_index": chunk_index,
        "relevance_score": score,
        "title": kwargs.get("title", f"Title for {url}"),
        "product_category": kwargs.get("product_category", "test"),
        "content": kwargs.get("content", f"Content for {url} chunk {chunk_index}"),
    }
    return result


class TestResultKey:
    """Verify deduplication key generation."""

    def test_key_from_result(self):
        r = _make_result("https://docs.cyberark.com/page1", 0)
        assert _result_key(r) == ("https://docs.cyberark.com/page1", 0)

    def test_different_chunks_different_keys(self):
        r1 = _make_result("https://docs.cyberark.com/page1", 0)
        r2 = _make_result("https://docs.cyberark.com/page1", 1)
        assert _result_key(r1) != _result_key(r2)


class TestRRFBasicMerge:
    """Test fundamental RRF merge behavior."""

    def test_overlap_scores_higher_than_single(self):
        """A result in both lists should score higher than one in only one."""
        overlap = _make_result("url_overlap", 0)
        vector_only = _make_result("url_vector_only", 0)
        bm25_only = _make_result("url_bm25_only", 0)

        vector = [overlap, vector_only]
        bm25 = [overlap, bm25_only]

        results = hybrid_search(vector, bm25)
        overlap_result = next(r for r in results if r["url"] == "url_overlap")
        other_results = [r for r in results if r["url"] != "url_overlap"]

        for other in other_results:
            assert overlap_result["relevance_score"] > other["relevance_score"]

    def test_deduplication(self):
        """Same (url, chunk_index) in both lists appears once."""
        vector = [_make_result("https://docs.cyberark.com/page1", 0)]
        bm25 = [_make_result("https://docs.cyberark.com/page1", 0)]

        results = hybrid_search(vector, bm25)
        assert len(results) == 1
        assert results[0]["relevance_score"] > 0

    def test_disjoint_results_all_appear(self):
        vector = [_make_result("url_a", 0)]
        bm25 = [_make_result("url_b", 0)]

        results = hybrid_search(vector, bm25)
        assert len(results) == 2


class TestWeightEffects:
    """Verify weight parameters control ranking dominance."""

    def test_vector_weight_dominance(self):
        vector = [_make_result("url_vector", 0)]
        bm25 = [_make_result("url_bm25", 0)]

        results = hybrid_search(vector, bm25, vector_weight=0.9, bm25_weight=0.1)
        assert results[0]["url"] == "url_vector"

    def test_bm25_weight_dominance(self):
        vector = [_make_result("url_vector", 0)]
        bm25 = [_make_result("url_bm25", 0)]

        results = hybrid_search(vector, bm25, vector_weight=0.1, bm25_weight=0.9)
        assert results[0]["url"] == "url_bm25"

    def test_equal_weights_overlap_wins(self):
        """With equal weights, a result in both lists should rank first."""
        overlap = _make_result("url_overlap", 0)
        vector_only = _make_result("url_vector", 0)

        results = hybrid_search([overlap, vector_only], [overlap], vector_weight=0.5, bm25_weight=0.5)
        assert results[0]["url"] == "url_overlap"


class TestKParameter:
    """Verify the RRF k smoothing parameter affects score distribution."""

    def test_small_k_amplifies_rank_differences(self):
        r1 = _make_result("url1", 0)
        r2 = _make_result("url2", 0)
        vector = [r1, r2]

        results_k1 = hybrid_search(vector, [], k=1, vector_weight=1.0, bm25_weight=0.0)
        results_k100 = hybrid_search(vector, [], k=100, vector_weight=1.0, bm25_weight=0.0)

        spread_k1 = results_k1[0]["relevance_score"] - results_k1[1]["relevance_score"]
        spread_k100 = results_k100[0]["relevance_score"] - results_k100[1]["relevance_score"]

        assert spread_k1 > spread_k100


class TestMetadataPreservation:
    """RRF output must retain all input metadata fields."""

    def test_preserves_all_fields(self):
        result = _make_result(
            "https://docs.cyberark.com/page", 3,
            title="Test Title",
            product_category="conjur-cloud",
            content="Some content here",
        )
        fused = hybrid_search([result], [])
        assert fused[0]["url"] == "https://docs.cyberark.com/page"
        assert fused[0]["chunk_index"] == 3
        assert fused[0]["title"] == "Test Title"
        assert fused[0]["product_category"] == "conjur-cloud"
        assert fused[0]["content"] == "Some content here"


class TestEmptyInputs:
    """Edge cases with empty result lists."""

    def test_both_empty(self):
        assert hybrid_search([], []) == []

    def test_empty_vector_results(self):
        bm25 = [_make_result("url_a", 0), _make_result("url_b", 0)]
        results = hybrid_search([], bm25)
        assert len(results) == 2

    def test_empty_bm25_results(self):
        vector = [_make_result("url_a", 0)]
        results = hybrid_search(vector, [])
        assert len(results) == 1


class TestSearchMethodTag:
    """All fused results should be tagged as hybrid."""

    def test_tag_present(self):
        results = hybrid_search([_make_result("u", 0)], [_make_result("v", 0)])
        for r in results:
            assert r["search_method"] == "hybrid"
