"""
MCP Server for CyberArk Documentation Search

Exposes the RAG search functionality as MCP tools for integration
with Claude Desktop and Claude Code.

Uses FastMCP for automatic schema generation from function signatures.
All logging goes to stderr; stdout is reserved for MCP JSON-RPC transport.
"""

import json
import sys
from typing import Optional

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from cyberark_rag.config import Settings
from cyberark_rag.logging_config import setup_logging

logger = setup_logging(__name__)

mcp = FastMCP("cyberark_rag_mcp")

# Reusable annotations for read-only search tools
_SEARCH_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)

# Lazy-loaded singleton
_searcher = None


def _get_searcher():
    """Get or initialize the DocumentSearcher singleton."""
    global _searcher
    if _searcher is None:
        from cyberark_rag.search import DocumentSearcher
        try:
            _searcher = DocumentSearcher()
            logger.info("DocumentSearcher initialized")
        except (FileNotFoundError, ValueError) as e:
            raise RuntimeError(
                f"Failed to initialize searcher: {e}\n"
                "Please run 'python -m cyberark_rag index' first."
            )
    return _searcher


@mcp.tool(
    name="search_cyberark_docs",
    description=(
        "Search CyberArk product documentation (Privilege Cloud, Conjur Cloud, "
        "Secrets Manager, EPM, Identity, and related products). "
        "\n\n"
        "USE THIS TOOL FOR:\n"
        "- CyberArk product features, configuration, and setup procedures\n"
        "- CyberArk API references, commands, and parameters\n"
        "- CyberArk architecture, integrations, and troubleshooting\n"
        "- Authentication methods, credential management, and security policies\n"
        "- Installation guides, deployment patterns, and best practices\n"
        "\n"
        "DO NOT USE THIS TOOL FOR:\n"
        "- Current events, recent announcements, or press releases\n"
        "- Pricing, licensing, or sales information\n"
        "- Competitive product comparisons\n"
        "- General security concepts unrelated to CyberArk products\n"
        "- Community forums, blog posts, or third-party content\n"
        "- Topics requiring information newer than January 2025\n"
        "\n"
        "For recent CyberArk news or external content, use web_search instead. "
        "For comprehensive analysis requiring both product docs AND external context, "
        "use both tools together.\n"
        "\n"
        "Features: Intelligent query expansion (e.g., 'SPIRE' -> 'SPIFFE'), "
        "intent-aware re-ranking, semantic search."
    ),
    annotations=_SEARCH_ANNOTATIONS,
)
def cyberark_rag_search_docs(
    query: str,
    top_k: int = 5,
    product_filter: Optional[str] = None,
    use_query_expansion: bool = True,
    use_hybrid_search: bool = True,
) -> str:
    """Search CyberArk documentation using hybrid semantic + keyword search.

    Args:
        query: The search query (e.g., 'How to rotate secrets in Conjur?')
        top_k: Number of results to return (default: 5, max: 20)
        product_filter: Optional product category filter
            (e.g., 'conjur-cloud', 'pam-self-hosted', 'identity-security-platform')
        use_query_expansion: Enable intelligent query expansion with related terms (default: true).
            Helps find relevant content even when terminology differs (e.g., SPIRE vs SPIFFE).
        use_hybrid_search: Enable BM25 keyword search alongside vector search (default: true).
    """
    top_k = max(1, min(top_k, 20))
    searcher = _get_searcher()

    results = searcher.search(
        query=query,
        top_k=top_k,
        filter_product=product_filter,
        use_query_expansion=use_query_expansion,
        use_hybrid=use_hybrid_search,
    )

    return _format_search_results(results, query)


@mcp.tool(
    name="get_command_example",
    description=(
        "Search for specific command examples and CLI usage in CyberArk documentation. "
        "Optimized for finding code snippets, command syntax, and step-by-step procedures. "
        "Use this when you need concrete examples of how to use CyberArk tools and commands."
    ),
    annotations=_SEARCH_ANNOTATIONS,
)
def cyberark_rag_get_command_example(
    product: str,
    task: str,
) -> str:
    """Find CLI/API/config examples for a CyberArk product.

    Args:
        product: Product name (e.g., 'Conjur', 'PAM', 'Privilege Cloud')
        task: The task or command to find examples for
            (e.g., 'authenticate', 'rotate secret', 'create policy')
    """
    searcher = _get_searcher()

    query = f"{product} {task} command example CLI syntax"

    product_mapping = {
        "conjur": "conjur-cloud",
        "pam": "pam-self-hosted",
        "privilege cloud": "privilege-cloud",
        "identity": "identity-security-platform",
    }

    filter_product = None
    product_lower = product.lower()
    for key, value in product_mapping.items():
        if key in product_lower:
            filter_product = value
            break

    results = searcher.search(
        query=query,
        top_k=5,
        filter_product=filter_product,
    )

    if not results:
        return f"No command examples found for {product} - {task}"

    output = [f"Command Examples: {product} - {task}\n"]
    for i, result in enumerate(results, 1):
        output.append(f"[Example {i}] Score: {result['relevance_score']:.4f}")
        output.append(f"Source: {result['title']}")
        output.append(f"URL: {result['url']}\n")

        content = result.get("content", "")
        if len(content) > 800:
            content = content[:800] + "..."
        output.append(content)
        output.append("-" * 80)
        output.append("")

    return "\n".join(output)


@mcp.tool(
    name="list_products",
    description=(
        "List available CyberArk product categories that can be used for filtering searches. "
        "Returns a list of product names found in the documentation database."
    ),
    annotations=_SEARCH_ANNOTATIONS,
)
def cyberark_rag_list_products() -> str:
    """Return available product categories with filter keys."""
    from cyberark_rag.product_aliases import get_resolver

    try:
        resolver = get_resolver()

        cache_path = Settings.PRODUCTS_CACHE
        raw_products = []

        if cache_path.exists():
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    cache_data = json.load(f)
                    raw_products = cache_data.get("products", [])
                    logger.info("Loaded %d raw products from cache", len(raw_products))
            except Exception as e:
                logger.warning("Cache read failed: %s", e)

        if not raw_products:
            searcher = _get_searcher()
            all_data = searcher.collection.get(
                include=["metadatas"],
                limit=100000,
            )
            raw_products_set = set()
            for metadata in all_data["metadatas"]:
                product = metadata.get("product_category", "")
                if product:
                    raw_products_set.add(product)
            raw_products = sorted(raw_products_set)
            logger.info("Found %d products from ChromaDB", len(raw_products))

        canonical_products = {}
        for raw_name in raw_products:
            canonical = resolver.resolve(raw_name)
            category = resolver.get_category(canonical)
            if category == "product":
                display_name = resolver.get_display_name(canonical)
                canonical_products[canonical] = display_name

        output = ["Available CyberArk Products:", ""]
        for name, display_name in sorted(canonical_products.items()):
            output.append(f"  - {display_name}")
            if name != display_name.lower().replace(" ", "-").replace("(", "").replace(")", ""):
                output.append(f"    Filter value: {name}")
        output.append("")
        output.append(f"Total: {len(canonical_products)} active products")
        output.append("")
        output.append("Use the canonical name (filter value) with the 'product_filter' parameter in search_cyberark_docs")

        return "\n".join(output)

    except Exception as e:
        return f"Error listing products: {e}"


@mcp.tool(
    name="get_index_stats",
    description="Get knowledge base health statistics: total chunks, products, last build time, BM25 status.",
    annotations=_SEARCH_ANNOTATIONS,
)
def cyberark_rag_get_index_stats() -> str:
    """Return index health statistics."""
    searcher = _get_searcher()
    stats = searcher.get_stats()

    bm25_status = "available" if Settings.BM25_PATH.exists() else "not built"

    cache_info = {}
    if Settings.PRODUCTS_CACHE.exists():
        try:
            with open(Settings.PRODUCTS_CACHE, "r", encoding="utf-8") as f:
                cache_info = json.load(f)
        except Exception:
            pass

    output = [
        "CyberArk RAG Index Statistics",
        "-" * 40,
        f"Total chunks: {stats['total_chunks']}",
        f"Collection: {stats['collection_name']}",
        f"Database: {stats['db_path']}",
        f"Embedding model: {Settings.EMBEDDING_MODEL}",
        f"Chunk size: {Settings.CHUNK_SIZE} tokens",
        f"BM25 index: {bm25_status}",
    ]

    if cache_info:
        output.append(f"Products indexed: {cache_info.get('total_products', 'unknown')}")
        output.append(f"Last indexed: {cache_info.get('indexed_at', 'unknown')}")

    return "\n".join(output)


def _format_search_results(results: list, query: str) -> str:
    """Format search results as readable text."""
    if not results:
        return f"No results found for query: '{query}'"

    output = [
        f"Search Results for: '{query}'",
        f"Found {len(results)} relevant chunks:\n",
    ]

    for i, result in enumerate(results, 1):
        output.append(f"[Result {i}]")
        output.append(f"Relevance Score: {result['relevance_score']:.4f}")
        output.append(f"Title: {result['title']}")
        output.append(f"Product: {result['product_category']}")
        output.append(f"URL: {result['url']}")
        output.append(f"Chunk: {result['chunk_index']}")
        output.append("")

        content = result.get("content", "")
        if len(content) > 600:
            content = content[:600] + "..."
        output.append(f"Content:\n{content}")
        output.append("-" * 80)
        output.append("")

    return "\n".join(output)


def main():
    """Entry point for the MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
