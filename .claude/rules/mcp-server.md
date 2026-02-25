---
paths:
  - "cyberark_rag/mcp_server.py"
  - "tests/test_mcp_server.py"
---

# MCP Server Rules

## Transport

stdout is the MCP JSON-RPC transport. Never print(), never log to stdout. Use `logging_config.setup_logging()` which writes to stderr.

## FastMCP Migration

Use `from mcp.server.fastmcp import FastMCP` instead of the low-level `Server` class. FastMCP auto-generates JSON schemas from Pydantic input models and handles protocol negotiation.

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("cyberark_rag_mcp")

@mcp.tool()
async def cyberark_rag_search_docs(query: str, top_k: int = 5, product_filter: str | None = None, use_hybrid_search: bool = True) -> str:
    """Search CyberArk documentation using hybrid semantic + keyword search."""
    ...
```

## Tool Definitions

All four tools must have the `cyberark_rag_` prefix:

1. `cyberark_rag_search_docs` -- hybrid search with optional product filter
   - Annotations: readOnlyHint=True, destructiveHint=False, openWorldHint=False
2. `cyberark_rag_get_command_example` -- find CLI/API/config examples
   - Annotations: readOnlyHint=True, destructiveHint=False
3. `cyberark_rag_list_products` -- return product categories with filter keys
   - Annotations: readOnlyHint=True, destructiveHint=False
4. `cyberark_rag_get_index_stats` -- knowledge base health: total chunks, products, last build time, BM25 status
   - Annotations: readOnlyHint=True, destructiveHint=False

## Lazy Loading

Keep the singleton pattern for DocumentSearcher. The embedding model is expensive to load. Initialize on first tool call, not at import time.

## Entry Point

```python
if __name__ == "__main__":
    mcp.run(transport="stdio")
```

Also support `python -m cyberark_rag.mcp_server` via `__main__.py` or direct module execution.
