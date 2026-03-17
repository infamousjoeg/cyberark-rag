"""
Search Module for CyberArk Documentation

This module provides search capabilities over the indexed documentation.
Supports three modes via CYBERARK_RAG_SEARCH_MODE env var:
  - hybrid: vector (ChromaDB) + BM25 keyword search with Reciprocal Rank Fusion
  - vector: ChromaDB semantic search only
  - bm25: BM25 keyword search only (low memory, no embedding model needed)
"""

import sys
from typing import List, Dict, Optional
from pathlib import Path

from cyberark_rag.bm25_index import BM25Index
from cyberark_rag.config import Settings
from cyberark_rag.query_expansion import get_expander
from cyberark_rag.content_classifier import get_classifier, classify_content_primary
from cyberark_rag.query_intent import get_detector, detect_intent


class DocumentSearcher:
    """
    Search over CyberArk documentation.

    In 'bm25' mode, only the BM25 keyword index is loaded (low memory).
    In 'vector' or 'hybrid' mode, ChromaDB and sentence-transformers are also loaded.
    """

    def __init__(
        self,
        db_dir: str = None,
        collection_name: str = None,
        embedding_model: str = None,
        search_mode: str = None,
    ):
        """
        Initialize the document searcher.

        Args:
            db_dir: Directory containing ChromaDB (defaults to Settings.DB_DIR)
            collection_name: Name of the ChromaDB collection
            embedding_model: SentenceTransformer model name
            search_mode: Override Settings.SEARCH_MODE (hybrid/bm25/vector)
        """
        self.db_dir = Path(db_dir) if db_dir else Settings.DB_DIR
        self.collection_name = collection_name or Settings.COLLECTION_NAME
        self.search_mode = search_mode or Settings.SEARCH_MODE

        # These are only initialized when vector search is needed
        self.client = None
        self.collection = None
        self.model = None

        # Lazy-loaded BM25 index
        self._bm25: Optional[BM25Index] = None
        self._bm25_mtime: float = 0.0  # mtime when last loaded

        if self.search_mode in ("vector", "hybrid"):
            self._init_vector_search(embedding_model)
        elif self.search_mode == "bm25":
            # BM25-only mode: just verify the index exists
            if not Settings.BM25_PATH.exists():
                raise FileNotFoundError(
                    f"BM25 index not found at {Settings.BM25_PATH}. "
                    "Please run the indexer first: python -m cyberark_rag index"
                )
        else:
            raise ValueError(f"Unknown search mode: {self.search_mode}")

    def _init_vector_search(self, embedding_model: str = None) -> None:
        """Initialize ChromaDB and embedding model (heavy imports)."""
        import chromadb
        from chromadb.config import Settings as ChromaSettings
        from sentence_transformers import SentenceTransformer

        if not self.db_dir.exists():
            raise FileNotFoundError(
                f"Database not found at {self.db_dir}. "
                "Please run the indexer first: python -m cyberark_rag index"
            )

        self.client = chromadb.PersistentClient(
            path=str(self.db_dir),
            settings=ChromaSettings(anonymized_telemetry=False)
        )

        try:
            self.collection = self.client.get_collection(name=self.collection_name)
        except Exception:
            raise ValueError(
                f"Collection '{self.collection_name}' not found. "
                "Please run the indexer first."
            )

        self.model = SentenceTransformer(embedding_model or Settings.EMBEDDING_MODEL)

    def _get_bm25(self) -> Optional[BM25Index]:
        """Lazy-load BM25 index, auto-reloading if the file changed on disk."""
        bm25_path = Settings.BM25_PATH
        if not bm25_path.exists():
            return self._bm25

        try:
            current_mtime = bm25_path.stat().st_mtime
        except OSError:
            return self._bm25

        if self._bm25 is None or current_mtime > self._bm25_mtime:
            try:
                self._bm25 = BM25Index.load()
                self._bm25_mtime = current_mtime
                print(
                    f"BM25 index loaded: {self._bm25.doc_count} docs",
                    file=sys.stderr,
                )
            except Exception as e:
                print(f"Warning: Failed to load BM25 index: {e}", file=sys.stderr)

        return self._bm25

    def _bm25_search(
        self,
        query: str,
        top_k: int = 15,
        filter_product: Optional[str] = None,
    ) -> List[Dict]:
        """
        Search the BM25 index and return results in the same format as _base_search.

        Args:
            query: Search query
            top_k: Number of results
            filter_product: Optional product filter

        Returns:
            List of result dicts compatible with hybrid_search
        """
        bm25 = self._get_bm25()
        if bm25 is None:
            return []

        raw = bm25.search(query, top_k=top_k, filter_product=filter_product)

        results = []
        for item in raw:
            meta = item["metadata"]
            results.append({
                "content": meta.get("original_text", ""),
                "url": meta.get("url", ""),
                "title": meta.get("title", ""),
                "product_category": meta.get("product_category", ""),
                "chunk_index": meta.get("chunk_index", 0),
                "relevance_score": item["score"],
                "content_type": meta.get("content_type"),
            })
        return results

    def search(
        self,
        query: str,
        top_k: int = 5,
        filter_product: Optional[str] = None,
        use_query_expansion: bool = True,
        use_reranking: bool = True,
        use_hybrid: bool = True,
    ) -> List[Dict]:
        """
        Search documentation using the configured search mode.

        Args:
            query: Search query
            top_k: Number of results to return
            filter_product: Optional product category filter
            use_query_expansion: Whether to expand query with related terms (default: True)
            use_reranking: Whether to re-rank by query intent (default: True)
            use_hybrid: Whether to use hybrid search (ignored in bm25 mode)

        Returns:
            List of search results with content, metadata, and scores
        """
        # BM25-only mode: skip all vector search
        if self.search_mode == "bm25":
            results = self._bm25_search(query, top_k=top_k * 3, filter_product=filter_product)
            results = results[:top_k]
            if use_reranking and results:
                results = self.rerank_by_intent(query, results)
            return results

        # Vector or hybrid mode
        fetch_k = top_k * 3 if (use_hybrid and self.search_mode == "hybrid") else top_k
        if use_query_expansion:
            vector_results = self.search_with_expansion(query, fetch_k, filter_product, use_reranking=False)
        else:
            vector_results = self._base_search(query, fetch_k, filter_product)

        # Hybrid search with BM25 if enabled and available
        if use_hybrid and self.search_mode == "hybrid" and self._get_bm25() is not None:
            from cyberark_rag.hybrid_search import hybrid_search
            bm25_results = self._bm25_search(query, top_k=fetch_k, filter_product=filter_product)
            results = hybrid_search(vector_results, bm25_results)[:top_k]
        else:
            results = vector_results[:top_k]

        # Apply intent-based re-ranking
        if use_reranking and results:
            results = self.rerank_by_intent(query, results)

        # Return original_text for display when available
        for result in results:
            if not result.get("content"):
                meta_text = result.get("original_text", "")
                if meta_text:
                    result["content"] = meta_text

        return results

    def _base_search(
        self,
        query: str,
        top_k: int = 5,
        filter_product: Optional[str] = None
    ) -> List[Dict]:
        """
        Base search without expansion or re-ranking.

        Args:
            query: Search query
            top_k: Number of results to return
            filter_product: Optional product category filter

        Returns:
            List of search results with content, metadata, and scores
        """
        # Generate query embedding
        query_embedding = self.model.encode(
            query,
            convert_to_numpy=True
        ).tolist()

        # Build filter if product specified
        where = None
        if filter_product:
            where = {"product_category": filter_product}

        # Query collection
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where
        )

        # Format results
        formatted_results = []

        if results['documents'] and results['documents'][0]:
            for i in range(len(results['documents'][0])):
                metadata = results['metadatas'][0][i]
                result = {
                    'content': results['documents'][0][i],
                    'url': metadata.get('url', ''),
                    'title': metadata.get('title', ''),
                    'product_category': metadata.get('product_category', ''),
                    'chunk_index': metadata.get('chunk_index', 0),
                    'distance': results['distances'][0][i],
                    'relevance_score': 1 / (1 + results['distances'][0][i]),  # Convert distance to similarity
                    'content_type': metadata.get('content_type', None)  # May be None if not yet indexed
                }
                formatted_results.append(result)

        return formatted_results

    def search_with_expansion(
        self,
        query: str,
        top_k: int = 5,
        filter_product: Optional[str] = None,
        max_expansions: int = 3,
        use_reranking: bool = False
    ) -> List[Dict]:
        """
        Perform semantic search with query expansion.

        This method expands the query with related terms and aliases,
        searches with each term, and merges the results.

        Args:
            query: Search query
            top_k: Number of results to return
            filter_product: Optional product category filter
            max_expansions: Maximum number of expansion terms to use
            use_reranking: Whether to apply re-ranking (default: False, handled by caller)

        Returns:
            List of search results with content, metadata, and scores
        """
        # Get query expander
        expander = get_expander()

        # Expand query
        expanded_queries = expander.expand_query(query, max_expansions=max_expansions)

        # If no expansions, fall back to base search
        if len(expanded_queries) == 1:
            return self._base_search(query, top_k, filter_product)

        # Search with each expanded query
        # Original query gets full weight, expansion terms get reduced weight
        all_results = {}  # Use dict to deduplicate by (url, chunk_index)

        for i, expanded_query in enumerate(expanded_queries):
            # Weight: 1.0 for original query, 0.7 for expansion terms
            weight = 1.0 if i == 0 else 0.7

            # Search with this query (use base search to avoid recursion)
            query_results = self._base_search(
                expanded_query,
                top_k=top_k * 2,  # Get more candidates
                filter_product=filter_product
            )

            # Merge results with weighting
            for result in query_results:
                key = (result['url'], result['chunk_index'])

                if key in all_results:
                    # Already have this result, boost its score
                    all_results[key]['relevance_score'] = max(
                        all_results[key]['relevance_score'],
                        result['relevance_score'] * weight
                    )
                    # Mark that it matched multiple queries
                    all_results[key]['matched_queries'] = all_results[key].get('matched_queries', 1) + 1
                else:
                    # New result
                    result['relevance_score'] *= weight
                    result['matched_queries'] = 1
                    all_results[key] = result

        # Sort by relevance score (with multi-query bonus)
        sorted_results = sorted(
            all_results.values(),
            key=lambda x: (x['relevance_score'] * (1 + 0.1 * x['matched_queries'])),
            reverse=True
        )

        # Return top_k results
        return sorted_results[:top_k]

    def rerank_by_intent(
        self,
        query: str,
        results: List[Dict]
    ) -> List[Dict]:
        """
        Re-rank results based on query intent and content type.

        This method detects the user's intent from the query and boosts results
        that match the appropriate content type.

        Args:
            query: Original search query
            results: Initial search results

        Returns:
            Re-ranked search results
        """
        if not results:
            return results

        # Detect query intent
        intent = detect_intent(query)

        print(f"Re-ranking: Detected intent '{intent.intent_type}' (confidence: {intent.confidence:.2f})")

        # Re-rank each result
        for result in results:
            # Get or classify content type
            content_type = result.get('content_type')

            if not content_type:
                # Content not yet classified in metadata, classify on-the-fly
                content_type = classify_content_primary(
                    result['url'],
                    result['title'],
                    result['content']
                )
                result['content_type'] = content_type

            # Get boost factor for this content type
            boost_factor = intent.boost_factors.get(content_type, 1.0)

            # Store original score
            if 'original_score' not in result:
                result['original_score'] = result['relevance_score']

            # Apply boost
            result['relevance_score'] = result['original_score'] * boost_factor
            result['boost_factor'] = boost_factor

        # Sort by boosted relevance score
        ranked_results = sorted(
            results,
            key=lambda x: x['relevance_score'],
            reverse=True
        )

        return ranked_results

    def get_stats(self) -> Dict:
        """
        Get statistics about the search index.

        Returns:
            Dictionary with index statistics
        """
        stats = {
            'collection_name': self.collection_name,
            'db_path': str(self.db_dir),
            'search_mode': self.search_mode,
        }

        if self.collection is not None:
            stats['total_chunks'] = self.collection.count()
        elif self._get_bm25() is not None:
            stats['total_chunks'] = self._bm25.doc_count
        else:
            stats['total_chunks'] = 0

        return stats

    def print_results(
        self,
        results: List[Dict],
        query: str,
        show_content_length: int = 500
    ) -> None:
        """
        Pretty print search results.

        Args:
            results: List of search results
            query: Original query
            show_content_length: Maximum characters of content to show
        """
        print("\n" + "=" * 80)
        print(f"Search Results for: '{query}'")
        print("=" * 80)

        if not results:
            print("\nNo results found.")
            return

        for i, result in enumerate(results, 1):
            print(f"\n[{i}] Relevance: {result['relevance_score']:.4f}")
            print("-" * 80)
            print(f"Title: {result['title']}")
            print(f"Product: {result['product_category']}")
            print(f"URL: {result['url']}")
            print(f"Chunk: {result['chunk_index']}")
            print("-" * 80)

            # Truncate content if needed
            content = result['content']
            if len(content) > show_content_length:
                content = content[:show_content_length] + "..."

            print(f"Content:\n{content}")
            print("=" * 80)


def main():
    """
    Main entry point for search CLI.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Search CyberArk documentation using semantic search"
    )
    parser.add_argument(
        'query',
        nargs='+',
        help='Search query'
    )
    parser.add_argument(
        '--top-k',
        type=int,
        default=5,
        help='Number of results to return (default: 5)'
    )
    parser.add_argument(
        '--product',
        help='Filter by product category (e.g., conjur-cloud, pam-self-hosted)'
    )
    parser.add_argument(
        '--db-dir',
        default=None,
        help='Directory containing ChromaDB (default: project chroma_db)'
    )
    parser.add_argument(
        '--content-length',
        type=int,
        default=500,
        help='Maximum characters of content to show (default: 500)'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show database statistics'
    )

    args = parser.parse_args()

    # Initialize searcher
    try:
        searcher = DocumentSearcher(db_dir=args.db_dir)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Show stats if requested
    if args.stats:
        stats = searcher.get_stats()
        print("\nDatabase Statistics:")
        print("-" * 40)
        print(f"Total chunks: {stats['total_chunks']}")
        print(f"Collection: {stats['collection_name']}")
        print(f"Database: {stats['db_path']}")
        print("-" * 40)
        return

    # Perform search
    query = ' '.join(args.query)

    try:
        results = searcher.search(
            query=query,
            top_k=args.top_k,
            filter_product=args.product
        )

        searcher.print_results(
            results=results,
            query=query,
            show_content_length=args.content_length
        )

    except Exception as e:
        print(f"Search error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
