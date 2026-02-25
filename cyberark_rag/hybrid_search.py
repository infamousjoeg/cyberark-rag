"""
Reciprocal Rank Fusion for Hybrid Search

Combines vector search and BM25 keyword search results using weighted
Reciprocal Rank Fusion (RRF). Reduces retrieval failures by 49% vs
vector-only search (Anthropic Contextual Retrieval research).

RRF formula: score(d) = sum(weight_i / (k + rank_i + 1))
Default: k=60, vector_weight=0.7, bm25_weight=0.3
"""

from typing import Dict, List, Tuple


def hybrid_search(
    vector_results: List[Dict],
    bm25_results: List[Dict],
    vector_weight: float = 0.7,
    bm25_weight: float = 0.3,
    k: int = 60,
) -> List[Dict]:
    """
    Fuse vector and BM25 search results using weighted Reciprocal Rank Fusion.

    Args:
        vector_results: Results from vector search, each with 'url', 'chunk_index', etc.
        bm25_results: Results from BM25 search, each with 'url', 'chunk_index', etc.
        vector_weight: Weight for vector search contribution (default: 0.7)
        bm25_weight: Weight for BM25 search contribution (default: 0.3)
        k: RRF smoothing constant (default: 60)

    Returns:
        Merged results sorted by fused score
    """
    fused_scores: Dict[Tuple, float] = {}
    result_map: Dict[Tuple, Dict] = {}

    # Score vector results
    for rank, result in enumerate(vector_results):
        key = _result_key(result)
        rrf_score = vector_weight / (k + rank + 1)
        fused_scores[key] = fused_scores.get(key, 0.0) + rrf_score
        if key not in result_map:
            result_map[key] = result

    # Score BM25 results
    for rank, result in enumerate(bm25_results):
        key = _result_key(result)
        rrf_score = bm25_weight / (k + rank + 1)
        fused_scores[key] = fused_scores.get(key, 0.0) + rrf_score
        if key not in result_map:
            result_map[key] = result

    # Sort by fused score
    sorted_keys = sorted(fused_scores.keys(), key=lambda k: fused_scores[k], reverse=True)

    results = []
    for key in sorted_keys:
        result = result_map[key].copy()
        result["relevance_score"] = fused_scores[key]
        result["search_method"] = "hybrid"
        results.append(result)

    return results


def _result_key(result: Dict) -> Tuple:
    """
    Create a deduplication key from a search result.

    Args:
        result: Search result dict

    Returns:
        Tuple of (url, chunk_index) for deduplication
    """
    return (result.get("url", ""), result.get("chunk_index", 0))
