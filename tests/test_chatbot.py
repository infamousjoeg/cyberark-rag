"""Tests for cyberark_rag/chatbot.py async chatbot."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cyberark_rag.chatbot import CyberArkChatbot, _format_results, TOOLS, SYSTEM_PROMPT


class TestFormatResults:
    """Tests for search result formatting."""

    def test_empty_results(self):
        assert _format_results([]) == "No results found."

    def test_single_result(self):
        results = [{
            "title": "Test Title",
            "relevance_score": 0.9234,
            "product_category": "conjur-cloud",
            "url": "https://docs.cyberark.com/test",
            "content": "Test content here",
        }]
        formatted = _format_results(results)

        assert "Found 1 results" in formatted
        assert "Test Title" in formatted
        assert "0.9234" in formatted
        assert "conjur-cloud" in formatted
        assert "https://docs.cyberark.com/test" in formatted
        assert "Test content here" in formatted

    def test_truncates_long_content(self):
        results = [{
            "title": "Long",
            "relevance_score": 0.5,
            "product_category": "test",
            "url": "https://example.com",
            "content": "x" * 1000,
        }]
        formatted = _format_results(results)
        assert "..." in formatted
        # Should be truncated to 600 chars + "..."
        assert len("x" * 1000) > 600

    def test_multiple_results_numbered(self):
        results = [
            {"title": f"Result {i}", "relevance_score": 0.9 - i * 0.1,
             "product_category": "test", "url": f"https://example.com/{i}",
             "content": f"Content {i}"}
            for i in range(3)
        ]
        formatted = _format_results(results)
        assert "[1]" in formatted
        assert "[2]" in formatted
        assert "[3]" in formatted


class TestToolSchemas:
    """Tests for tool definitions."""

    def test_four_tools_defined(self):
        assert len(TOOLS) == 4

    def test_tool_names(self):
        names = {t["name"] for t in TOOLS}
        assert names == {
            "search_cyberark_docs",
            "get_command_example",
            "list_products",
            "get_index_stats",
        }

    def test_search_tool_has_required_query(self):
        search_tool = next(t for t in TOOLS if t["name"] == "search_cyberark_docs")
        assert "query" in search_tool["input_schema"]["required"]

    def test_command_example_has_required_fields(self):
        cmd_tool = next(t for t in TOOLS if t["name"] == "get_command_example")
        assert set(cmd_tool["input_schema"]["required"]) == {"product", "task"}

    def test_list_products_no_required(self):
        list_tool = next(t for t in TOOLS if t["name"] == "list_products")
        assert "required" not in list_tool["input_schema"]

    def test_all_tools_have_description(self):
        for tool in TOOLS:
            assert tool.get("description"), f"Tool {tool['name']} missing description"


class TestSystemPrompt:
    """Tests for system prompt content."""

    def test_mentions_updated_product_names(self):
        assert "Secrets Manager" in SYSTEM_PROMPT
        assert "Secure Infrastructure Access" in SYSTEM_PROMPT
        assert "SIA" in SYSTEM_PROMPT

    def test_mentions_key_products(self):
        assert "Privilege Cloud" in SYSTEM_PROMPT
        assert "Secrets Hub" in SYSTEM_PROMPT
        assert "Credential Providers" in SYSTEM_PROMPT
        assert "EPM" in SYSTEM_PROMPT


class TestCyberArkChatbot:
    """Tests for the chatbot class."""

    @pytest.fixture
    def mock_auth(self, monkeypatch):
        """Mock auth to return a test API key."""
        monkeypatch.setattr(
            "cyberark_rag.chatbot.AuthConfig.resolve",
            staticmethod(lambda: ("api_key", "test-key")),
        )

    @pytest.fixture
    def mock_anthropic(self):
        """Mock the AsyncAnthropic client."""
        with patch("cyberark_rag.chatbot.anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            yield mock_client

    @pytest.fixture
    def bot(self, mock_auth, mock_anthropic):
        """Create a chatbot with mocked dependencies."""
        return CyberArkChatbot(model="claude-sonnet-4-6")

    def test_init_with_api_key(self, mock_auth):
        """API key auth creates client with api_key parameter."""
        with patch("cyberark_rag.chatbot.anthropic.AsyncAnthropic") as mock_cls:
            CyberArkChatbot()
            mock_cls.assert_called_once_with(api_key="test-key")

    def test_init_with_oauth(self, monkeypatch):
        """OAuth auth creates client with auth_token parameter."""
        monkeypatch.setattr(
            "cyberark_rag.chatbot.AuthConfig.resolve",
            staticmethod(lambda: ("oauth", "oauth-token")),
        )
        with patch("cyberark_rag.chatbot.anthropic.AsyncAnthropic") as mock_cls:
            CyberArkChatbot()
            mock_cls.assert_called_once_with(auth_token="oauth-token")

    def test_init_no_credentials(self, monkeypatch):
        """Missing credentials raises ValueError."""
        monkeypatch.setattr(
            "cyberark_rag.chatbot.AuthConfig.resolve",
            staticmethod(lambda: (_ for _ in ()).throw(ValueError("no creds"))),
        )
        with pytest.raises(ValueError):
            CyberArkChatbot()

    def test_reset_clears_messages(self, bot):
        bot.messages = [{"role": "user", "content": "test"}]
        bot.reset()
        assert bot.messages == []

    @pytest.mark.asyncio
    async def test_execute_tool_search(self, bot):
        """search_cyberark_docs dispatches to DocumentSearcher.search()."""
        mock_searcher = MagicMock()
        mock_searcher.search.return_value = [
            {"title": "Test", "relevance_score": 0.9, "product_category": "test",
             "url": "https://example.com", "content": "content"},
        ]
        bot._searcher = mock_searcher

        result = await bot._execute_tool("search_cyberark_docs", {
            "query": "test query",
            "top_k": 3,
        })

        mock_searcher.search.assert_called_once()
        call_kwargs = mock_searcher.search.call_args
        assert call_kwargs.kwargs["query"] == "test query"
        assert call_kwargs.kwargs["top_k"] == 3
        assert "Test" in result

    @pytest.mark.asyncio
    async def test_execute_tool_command_example(self, bot):
        """get_command_example constructs search query from product + task."""
        mock_searcher = MagicMock()
        mock_searcher.search.return_value = []
        bot._searcher = mock_searcher

        await bot._execute_tool("get_command_example", {
            "product": "Conjur",
            "task": "authenticate",
        })

        call_kwargs = mock_searcher.search.call_args
        assert "Conjur" in call_kwargs.kwargs["query"]
        assert "authenticate" in call_kwargs.kwargs["query"]

    @pytest.mark.asyncio
    async def test_execute_tool_unknown(self, bot):
        """Unknown tool returns error JSON."""
        bot._searcher = MagicMock()
        result = await bot._execute_tool("nonexistent_tool", {})
        parsed = json.loads(result)
        assert "error" in parsed

    @pytest.mark.asyncio
    async def test_execute_tools_concurrent(self, bot):
        """Multiple tool calls execute concurrently via asyncio.gather."""
        mock_searcher = MagicMock()
        mock_searcher.search.return_value = [
            {"title": "R", "relevance_score": 0.5, "product_category": "t",
             "url": "u", "content": "c"},
        ]
        bot._searcher = mock_searcher

        # Create mock tool_use blocks
        block1 = MagicMock()
        block1.type = "tool_use"
        block1.name = "search_cyberark_docs"
        block1.input = {"query": "query1"}
        block1.id = "id1"

        block2 = MagicMock()
        block2.type = "tool_use"
        block2.name = "search_cyberark_docs"
        block2.input = {"query": "query2"}
        block2.id = "id2"

        results = await bot._execute_tools_concurrent([block1, block2])

        assert len(results) == 2
        assert results[0]["tool_use_id"] == "id1"
        assert results[1]["tool_use_id"] == "id2"
        # Both should have content (not errors)
        for r in results:
            assert r["type"] == "tool_result"
            assert r["content"]  # Non-empty

    @pytest.mark.asyncio
    async def test_execute_tool_handles_exception(self, bot):
        """Tool execution errors are caught and returned as JSON."""
        mock_searcher = MagicMock()
        mock_searcher.search.side_effect = RuntimeError("search failed")
        bot._searcher = mock_searcher

        result = await bot._execute_tool("search_cyberark_docs", {"query": "test"})
        parsed = json.loads(result)
        assert "error" in parsed
        assert "search failed" in parsed["error"]

    @pytest.mark.asyncio
    async def test_execute_tool_clamps_top_k(self, bot):
        """top_k is clamped to 1-20 range."""
        mock_searcher = MagicMock()
        mock_searcher.search.return_value = []
        bot._searcher = mock_searcher

        await bot._execute_tool("search_cyberark_docs", {"query": "test", "top_k": 100})
        call_kwargs = mock_searcher.search.call_args
        assert call_kwargs.kwargs["top_k"] == 20

        await bot._execute_tool("search_cyberark_docs", {"query": "test", "top_k": -5})
        call_kwargs = mock_searcher.search.call_args
        assert call_kwargs.kwargs["top_k"] == 1

    @pytest.mark.asyncio
    async def test_get_index_stats(self, bot):
        """get_index_stats returns JSON with stats."""
        mock_searcher = MagicMock()
        mock_searcher.get_stats.return_value = {
            "total_chunks": 1000,
            "collection_name": "cyberark_docs",
            "db_path": "/tmp/test",
        }
        bot._searcher = mock_searcher

        result = await bot._execute_tool("get_index_stats", {})
        parsed = json.loads(result)
        assert parsed["total_chunks"] == 1000
        assert "embedding_model" in parsed
