"""
Logging Configuration for CyberArk RAG

All logging goes to stderr. stdout is reserved for MCP JSON-RPC transport.
"""

import logging
import sys


def setup_logging(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Create a logger that writes only to stderr.

    Args:
        name: Logger name (typically __name__)
        level: Logging level (default: INFO)

    Returns:
        Configured Logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid duplicate handlers if called multiple times
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(level)
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger
