"""
CyberArk RAG Chatbot -- Claude Sonnet with hybrid search tools.

Async chatbot that uses the Anthropic SDK with tool use to query the local
RAG search engine. Claude decides when and what to search. Multiple tool
calls in a single response are executed concurrently.
"""

import asyncio
import json
import sys
from typing import AsyncGenerator, Optional

import anthropic

from cyberark_rag.auth import AuthConfig
from cyberark_rag.config import Settings
from cyberark_rag.logging_config import setup_logging

logger = setup_logging(__name__)

SYSTEM_PROMPT = (
    "You are a CyberArk documentation expert. You have access to search tools "
    "that query a comprehensive index of docs.cyberark.com covering 22+ products "
    "including Privilege Cloud, Secrets Manager (SaaS and Self-Hosted), Secrets "
    "Hub, Credential Providers, EPM, Secure Infrastructure Access (SIA), "
    "Identity, and more.\n\n"
    "When answering questions:\n"
    "- Search the documentation to ground your answers in official sources\n"
    "- Always cite the specific documentation URL(s) for your claims\n"
    "- If the search results don't cover the answer, say so honestly\n"
    "- For multi-step procedures, search for each step if needed\n"
    "- Use the product filter when the user specifies a product\n"
    "- You may search multiple times per response for comprehensive answers"
)

TOOLS = [
    {
        "name": "search_cyberark_docs",
        "description": (
            "Search CyberArk documentation using hybrid vector + BM25 retrieval. "
            "Returns ranked results with titles, URLs, and content snippets. "
            "Use this for any question about CyberArk products, configuration, "
            "troubleshooting, or procedures."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Search query (e.g., 'configure Kubernetes authenticator' "
                        "or 'PVWA error 401')"
                    ),
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of results (1-20)",
                    "default": 5,
                },
                "product_filter": {
                    "type": "string",
                    "description": (
                        "Filter by product key (e.g., 'secrets-manager-saas', "
                        "'privilege-cloud-standard', 'secure-infrastructure-access')"
                    ),
                },
                "use_hybrid_search": {
                    "type": "boolean",
                    "description": (
                        "Use BM25 + vector fusion (recommended for "
                        "error codes and exact terms)"
                    ),
                    "default": True,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_command_example",
        "description": (
            "Search for specific command examples and CLI usage in CyberArk "
            "documentation. Optimized for finding code snippets, command syntax, "
            "and step-by-step procedures."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "product": {
                    "type": "string",
                    "description": "Product name (e.g., 'Secrets Manager', 'PAM', 'Privilege Cloud')",
                },
                "task": {
                    "type": "string",
                    "description": (
                        "Task description (e.g., 'authenticate', 'rotate secret', "
                        "'create policy')"
                    ),
                },
            },
            "required": ["product", "task"],
        },
    },
    {
        "name": "list_products",
        "description": (
            "List available CyberArk product categories that can be used for "
            "filtering searches. Returns canonical names and display names."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_index_stats",
        "description": "Get knowledge base health statistics: total chunks, products, BM25 status.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
]


class CyberArkChatbot:
    """Async chatbot with Claude Sonnet and CyberArk RAG tools."""

    def __init__(self, model: str = "claude-sonnet-4-6") -> None:
        """Initialize chatbot with auth credentials and model.

        Args:
            model: Claude model ID to use.

        Raises:
            ValueError: If no authentication credentials found.
        """
        auth_type, token = AuthConfig.resolve()

        if auth_type == "oauth":
            self.client = anthropic.AsyncAnthropic(auth_token=token)
        else:
            self.client = anthropic.AsyncAnthropic(api_key=token)

        self.model = model
        self.messages: list[dict] = []
        self._searcher = None
        self._searcher_lock = asyncio.Lock()

    async def _ensure_searcher(self):
        """Thread-safe lazy initialization of the search engine.

        Runs DocumentSearcher init in a thread pool to avoid blocking
        the event loop (it loads the embedding model which takes seconds).
        """
        async with self._searcher_lock:
            if self._searcher is None:
                from cyberark_rag.search import DocumentSearcher

                self._searcher = await asyncio.to_thread(DocumentSearcher)
                logger.info("DocumentSearcher initialized")
            return self._searcher

    async def _execute_tool(self, name: str, tool_input: dict) -> str:
        """Execute a single tool call. Blocking search runs in thread pool.

        Args:
            name: Tool name.
            tool_input: Tool input parameters.

        Returns:
            JSON string with results.
        """
        searcher = await self._ensure_searcher()

        try:
            if name == "search_cyberark_docs":
                results = await asyncio.to_thread(
                    searcher.search,
                    query=tool_input["query"],
                    top_k=max(1, min(tool_input.get("top_k", 5), 20)),
                    filter_product=tool_input.get("product_filter"),
                    use_hybrid=tool_input.get("use_hybrid_search", True),
                )
                return _format_results(results)

            elif name == "get_command_example":
                product = tool_input["product"]
                task = tool_input["task"]
                query = f"{product} {task} command example CLI syntax"
                results = await asyncio.to_thread(
                    searcher.search,
                    query=query,
                    top_k=5,
                )
                return _format_results(results)

            elif name == "list_products":
                from cyberark_rag.product_aliases import get_resolver

                resolver = get_resolver()
                products = {}
                for canonical in resolver.get_products_only():
                    products[canonical] = resolver.get_display_name(canonical)

                lines = ["Available CyberArk Products:", ""]
                for name_key, display in sorted(products.items()):
                    lines.append(f"  - {display} (filter: {name_key})")
                lines.append(f"\nTotal: {len(products)} products")
                return "\n".join(lines)

            elif name == "get_index_stats":
                stats = await asyncio.to_thread(searcher.get_stats)
                bm25_status = "available" if Settings.BM25_PATH.exists() else "not built"
                return json.dumps({
                    "total_chunks": stats["total_chunks"],
                    "collection": stats["collection_name"],
                    "embedding_model": Settings.EMBEDDING_MODEL,
                    "bm25_index": bm25_status,
                })

            else:
                return json.dumps({"error": f"Unknown tool: {name}"})

        except Exception as e:
            logger.error("Tool %s failed: %s", name, e)
            return json.dumps({"error": str(e)})

    async def _execute_tools_concurrent(
        self, tool_blocks: list
    ) -> list[dict]:
        """Execute all tool calls from one response concurrently.

        Args:
            tool_blocks: List of tool_use content blocks from Claude's response.

        Returns:
            List of tool_result dicts ready to append to messages.
        """
        tasks = [
            self._execute_tool(block.name, block.input)
            for block in tool_blocks
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        tool_results = []
        for block, result in zip(tool_blocks, results):
            if isinstance(result, Exception):
                content = json.dumps({"error": str(result)})
            else:
                content = result
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": content,
            })

        return tool_results

    async def chat_stream(
        self, user_message: str
    ) -> AsyncGenerator[str, None]:
        """Stream one conversation turn. Yields text chunks.

        Handles the tool_use loop internally:
        1. Send message to Claude (streaming)
        2. If Claude calls tools, execute concurrently
        3. Send results back, stream next response
        4. Repeat until Claude gives a text-only response

        Args:
            user_message: The user's message.

        Yields:
            Text chunks as they arrive from Claude.
        """
        self.messages.append({"role": "user", "content": user_message})

        # Pre-warm searcher concurrently with first API call
        searcher_task = asyncio.create_task(self._ensure_searcher())

        while True:
            async with self.client.messages.stream(
                model=self.model,
                max_tokens=Settings.CHATBOT_MAX_TOKENS,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=self.messages,
            ) as stream:
                async for text in stream.text_stream:
                    yield text

                response = await stream.get_final_message()

            # Add assistant response to history
            self.messages.append({
                "role": "assistant",
                "content": response.content,
            })

            if response.stop_reason != "tool_use":
                break

            # Collect tool_use blocks
            tool_blocks = [
                block for block in response.content
                if block.type == "tool_use"
            ]

            if not tool_blocks:
                break

            # Show tool call indicators
            tool_names = [b.name for b in tool_blocks]
            yield f"\n  [Searching: {', '.join(tool_names)}]\n\n"

            # Ensure searcher is ready, then execute tools concurrently
            await searcher_task
            tool_results = await self._execute_tools_concurrent(tool_blocks)

            # Add tool results to history
            self.messages.append({
                "role": "user",
                "content": tool_results,
            })

    async def chat(self, user_message: str) -> str:
        """Non-streaming conversation turn.

        Args:
            user_message: The user's message.

        Returns:
            Complete assistant response text.
        """
        chunks = []
        async for chunk in self.chat_stream(user_message):
            chunks.append(chunk)
        return "".join(chunks)

    def reset(self) -> None:
        """Clear conversation history."""
        self.messages = []

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.close()


def _format_results(results: list[dict]) -> str:
    """Format search results as readable text for Claude.

    Args:
        results: List of search result dicts from DocumentSearcher.

    Returns:
        Formatted string with results.
    """
    if not results:
        return "No results found."

    lines = [f"Found {len(results)} results:\n"]

    for i, result in enumerate(results, 1):
        content = result.get("content", "")
        if len(content) > 600:
            content = content[:600] + "..."

        lines.append(f"[{i}] {result.get('title', 'Untitled')}")
        lines.append(f"    Score: {result.get('relevance_score', 0):.4f}")
        lines.append(f"    Product: {result.get('product_category', 'unknown')}")
        lines.append(f"    URL: {result.get('url', '')}")
        lines.append(f"    {content}")
        lines.append("")

    return "\n".join(lines)
