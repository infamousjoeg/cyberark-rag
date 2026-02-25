"""Tests for the FastMCP server tool definitions and annotations.

Validates tool registration, naming conventions, and annotation metadata
without starting the actual MCP transport.
"""

import pytest

from cyberark_rag.mcp_server import mcp


class TestMCPToolRegistration:
    """Verify all four tools are registered with correct names and annotations."""

    def test_all_tools_registered(self):
        tool_names = set(mcp._tool_manager._tools.keys())
        expected = {
            "search_cyberark_docs",
            "get_command_example",
            "list_products",
            "get_index_stats",
        }
        assert expected.issubset(tool_names), f"Missing tools: {expected - tool_names}"

    def test_tool_count(self):
        assert len(mcp._tool_manager._tools) == 4

    def test_search_docs_tool_exists(self):
        assert mcp._tool_manager._tools.get("search_cyberark_docs") is not None

    def test_get_command_example_tool_exists(self):
        assert mcp._tool_manager._tools.get("get_command_example") is not None

    def test_list_products_tool_exists(self):
        assert mcp._tool_manager._tools.get("list_products") is not None

    def test_get_index_stats_tool_exists(self):
        assert mcp._tool_manager._tools.get("get_index_stats") is not None


class TestMCPToolAnnotations:
    """Verify tool annotations match MCP spec requirements."""

    @pytest.fixture
    def tools(self):
        return mcp._tool_manager._tools

    def test_search_docs_has_description(self, tools):
        tool = tools["search_cyberark_docs"]
        assert tool.description
        assert len(tool.description) > 50

    def test_get_command_example_has_description(self, tools):
        tool = tools["get_command_example"]
        assert tool.description
        assert "command" in tool.description.lower()
