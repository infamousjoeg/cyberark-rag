"""
Central Configuration for CyberArk RAG

All paths, model names, and tunable parameters are defined here.
Every module imports from this file instead of hardcoding values.
Environment variables override defaults.
"""

import os
from pathlib import Path


class Settings:
    """Central configuration with env var overrides."""

    # Project root: parent of the cyberark_rag package
    PROJECT_ROOT: Path = Path(__file__).parent.parent

    # Directories
    DOCS_DIR: Path = Path(
        os.environ.get("CYBERARK_RAG_DOCS", str(PROJECT_ROOT / "scraped_docs"))
    )
    DB_DIR: Path = Path(
        os.environ.get("CYBERARK_RAG_DB", str(PROJECT_ROOT / "chroma_db"))
    )

    # Derived paths
    BM25_PATH: Path = DB_DIR / "bm25_index.pkl"
    STATE_FILE: Path = PROJECT_ROOT / "scraper_state.json"
    PRODUCTS_CACHE: Path = DB_DIR / "products_cache.json"

    # Embedding model (BAAI/bge-large-en-v1.5: 1024d, ranked #1 MTEB at release)
    # Override with CYBERARK_RAG_MODEL env var if needed
    # Note: changing models requires a full re-index (embedding dimensions change)
    EMBEDDING_MODEL: str = os.environ.get(
        "CYBERARK_RAG_MODEL", "BAAI/bge-large-en-v1.5"
    )

    # ChromaDB collection name -- do not change
    COLLECTION_NAME: str = "cyberark_docs"

    # Chunking parameters (research-informed: 800 tokens optimal)
    CHUNK_SIZE: int = int(os.environ.get("CYBERARK_RAG_CHUNK_SIZE", "800"))
    CHUNK_OVERLAP: int = int(os.environ.get("CYBERARK_RAG_CHUNK_OVERLAP", "100"))

    # Search mode: "hybrid" (vector + BM25), "bm25" (keyword only), "vector" (semantic only)
    # BM25-only mode avoids loading the embedding model (~300MB+ RAM savings)
    SEARCH_MODE: str = os.environ.get("CYBERARK_RAG_SEARCH_MODE", "hybrid")

    # Config files
    PRODUCT_ALIASES_PATH: Path = PROJECT_ROOT / "product_aliases.yaml"
    QUERY_EXPANSIONS_PATH: Path = PROJECT_ROOT / "query_expansions.yaml"
    CONFIG_YAML_PATH: Path = PROJECT_ROOT / "config.yaml"
