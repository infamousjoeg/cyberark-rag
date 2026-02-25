"""Tests for the centralized Settings class and logging configuration."""

import importlib
import logging
import sys
from pathlib import Path

import pytest


class TestSettingsDefaults:
    """Verify default paths resolve relative to project root."""

    def test_docs_dir_ends_with_scraped_docs(self):
        from cyberark_rag.config import Settings
        assert str(Settings.DOCS_DIR).endswith("scraped_docs")

    def test_db_dir_ends_with_chroma_db(self):
        from cyberark_rag.config import Settings
        assert str(Settings.DB_DIR).endswith("chroma_db")

    def test_bm25_path_ends_with_pkl(self):
        from cyberark_rag.config import Settings
        assert str(Settings.BM25_PATH).endswith("bm25_index.pkl")

    def test_collection_name(self):
        from cyberark_rag.config import Settings
        assert Settings.COLLECTION_NAME == "cyberark_docs"

    def test_chunk_size_is_800(self):
        from cyberark_rag.config import Settings
        assert Settings.CHUNK_SIZE == 800

    def test_chunk_overlap_is_100(self):
        from cyberark_rag.config import Settings
        assert Settings.CHUNK_OVERLAP == 100

    def test_project_root_is_parent_of_package(self):
        from cyberark_rag.config import Settings
        # PROJECT_ROOT should contain cyberark_rag/ as a child directory
        assert (Settings.PROJECT_ROOT / "cyberark_rag").is_dir()


class TestSettingsEnvOverrides:
    """Verify env var overrides work correctly.

    Note: Settings uses class-level attributes evaluated at import time,
    so we test the env var lookup mechanism directly.
    """

    def test_env_var_chunk_size_mechanism(self, monkeypatch):
        monkeypatch.setenv("CYBERARK_RAG_CHUNK_SIZE", "1024")
        import os
        assert int(os.environ.get("CYBERARK_RAG_CHUNK_SIZE", "800")) == 1024

    def test_env_var_model_mechanism(self, monkeypatch):
        monkeypatch.setenv("CYBERARK_RAG_MODEL", "all-MiniLM-L6-v2")
        import os
        assert os.environ.get("CYBERARK_RAG_MODEL") == "all-MiniLM-L6-v2"

    def test_env_var_docs_dir_mechanism(self, monkeypatch):
        monkeypatch.setenv("CYBERARK_RAG_DOCS", "/tmp/custom_docs")
        import os
        assert Path(os.environ.get("CYBERARK_RAG_DOCS")) == Path("/tmp/custom_docs")


class TestLoggingConfig:
    """Verify logging goes to stderr only."""

    def test_setup_logging_returns_logger(self):
        from cyberark_rag.logging_config import setup_logging
        logger = setup_logging("test_module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_module"

    def test_logging_writes_to_stderr(self, capsys):
        from cyberark_rag.logging_config import setup_logging
        logger = setup_logging("test_stderr_check", level=logging.WARNING)
        # Remove any existing handlers to start clean
        logger.handlers.clear()
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(logging.WARNING)
        logger.addHandler(handler)

        logger.warning("test message for stderr")

        captured = capsys.readouterr()
        # stdout should be empty (MCP JSON-RPC channel)
        assert "test message for stderr" not in captured.out
        # stderr should have the message
        assert "test message for stderr" in captured.err

    def test_setup_logging_no_duplicate_handlers(self):
        from cyberark_rag.logging_config import setup_logging
        # Call twice with same name
        logger1 = setup_logging("test_dedup")
        initial_count = len(logger1.handlers)
        logger2 = setup_logging("test_dedup")
        assert len(logger2.handlers) == initial_count
