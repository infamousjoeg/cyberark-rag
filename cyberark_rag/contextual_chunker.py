"""
Contextual Retrieval Chunk Enrichment

Prepends metadata-derived context prefixes to chunks BEFORE embedding.
This is the single highest-impact improvement: 35% fewer retrieval failures
according to Anthropic's Contextual Retrieval research.

Chunks like "Revenue grew 3%" become:
  "From CyberArk Privilege Cloud documentation, page titled 'Billing Overview',
   section about billing metrics. Revenue grew 3%"

# LLM-POWERED VERSION (future upgrade, requires API key):
# Cost with prompt caching: ~$1.02 per million document tokens
# Prompt:
#   <document>{WHOLE_DOC}</document>
#   <chunk>{CHUNK}</chunk>
#   Please give a short succinct context to situate this chunk within the overall
#   document for the purposes of improving search retrieval of the chunk.
#   Answer only with the succinct context and nothing else.
# Expected improvement: 49% (vs 35% for metadata-only)
# Set ANTHROPIC_API_KEY env var to enable.
"""

import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse


def _extract_product_display_name(product_category: str) -> str:
    """
    Convert a product_category slug to a human-readable display name.

    Args:
        product_category: Raw slug like 'conjur-cloud' or 'pam-self-hosted'

    Returns:
        Human-readable name like 'Conjur Cloud'
    """
    if not product_category or product_category == "general":
        return "CyberArk"
    return product_category.replace("-", " ").replace("_", " ").title()


def _extract_version(url: str) -> Optional[str]:
    """
    Extract a version string from URL path segments.

    Looks for segments matching semver-like patterns (e.g., '13.2', 'v2', 'latest').

    Args:
        url: Full URL

    Returns:
        Version string or None
    """
    try:
        parsed = urlparse(url)
        parts = [p for p in parsed.path.split("/") if p]
        for part in parts:
            if re.match(r"^\d+\.\d+", part) or re.match(r"^v\d+", part):
                return part
            if part == "latest":
                return "latest"
    except Exception:
        pass
    return None


def _extract_nearest_heading(full_content: str, chunk_text: str) -> Optional[str]:
    """
    Find the nearest heading above the chunk within the full document.

    Searches for markdown-style headers (## Heading) and title-case lines
    that appear before the chunk's position.

    Args:
        full_content: The complete document text
        chunk_text: The chunk text to find context for

    Returns:
        The heading text, or None if not found
    """
    if not full_content or not chunk_text:
        return None

    # Find chunk position in the document
    chunk_start = full_content.find(chunk_text[:100])
    if chunk_start < 0:
        return None

    # Look backwards from the chunk for headings
    text_before = full_content[:chunk_start]

    # Pattern: markdown headers or title-case lines (at least 3 words)
    heading_pattern = re.compile(
        r"^(?:#{1,3}\s+(.+)|([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,}))$",
        re.MULTILINE,
    )

    headings = list(heading_pattern.finditer(text_before))
    if headings:
        match = headings[-1]  # Last (nearest) heading
        return (match.group(1) or match.group(2)).strip()

    return None


def build_chunk_context(
    url: str,
    title: str,
    product_category: str,
    chunk_text: str,
    chunk_index: int,
    total_chunks: int,
    full_content: str,
) -> str:
    """
    Build a metadata-derived context prefix for a chunk.

    Args:
        url: Source page URL
        title: Page title
        product_category: Product slug from URL
        chunk_text: The chunk content
        chunk_index: Position of this chunk in the document
        total_chunks: Total chunks from this document
        full_content: The full document text

    Returns:
        Context prefix string to prepend to the chunk
    """
    product_name = _extract_product_display_name(product_category)
    version = _extract_version(url)
    heading = _extract_nearest_heading(full_content, chunk_text)

    # Build prefix
    parts = [f"From CyberArk {product_name} documentation"]

    if version and version != "latest":
        parts[0] += f" (version {version})"

    if title:
        parts.append(f"page titled '{title}'")

    if heading:
        parts.append(f"section about {heading}")

    prefix = ", ".join(parts) + ". "

    return prefix


def contextualize_chunks(
    chunks: List[Tuple[str, Dict]],
    full_content: str,
) -> List[Tuple[str, Dict]]:
    """
    Add context prefixes to all chunks from a document.

    The original chunk text is preserved in metadata['original_text']
    for display purposes. The returned chunk text includes the context
    prefix and is what gets embedded.

    Args:
        chunks: List of (chunk_text, metadata) tuples from the chunker
        full_content: The complete document text

    Returns:
        List of (contextualized_text, enriched_metadata) tuples
    """
    total_chunks = len(chunks)
    result: List[Tuple[str, Dict]] = []

    for chunk_text, metadata in chunks:
        url = metadata.get("url", "")
        title = metadata.get("title", "")
        product_category = metadata.get("product_category", "")
        chunk_index = metadata.get("chunk_index", 0)

        prefix = build_chunk_context(
            url=url,
            title=title,
            product_category=product_category,
            chunk_text=chunk_text,
            chunk_index=chunk_index,
            total_chunks=total_chunks,
            full_content=full_content,
        )

        # Enrich metadata
        enriched_meta = metadata.copy()
        enriched_meta["original_text"] = chunk_text
        enriched_meta["context_prefix"] = prefix

        # Contextualized text for embedding
        contextualized = prefix + chunk_text

        result.append((contextualized, enriched_meta))

    return result
