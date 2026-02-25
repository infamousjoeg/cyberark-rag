# MCP Integration

Connecting the RAG system to Claude Desktop and Claude Code.

## Overview

MCP (Model Context Protocol) allows Claude to call external tools during a conversation. The cyberark-rag MCP server exposes 4 search tools over stdio transport, giving Claude access to CyberArk's complete product documentation.

## Claude Desktop Setup

### 1. Locate Your Config File

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Linux**: `~/.config/claude/claude_desktop_config.json`

Create the file if it does not exist.

### 2. Add the Server Configuration

If you installed with a virtual environment (recommended):

```json
{
  "mcpServers": {
    "cyberark-rag": {
      "command": "/path/to/cyberark-rag/.venv/bin/python3",
      "args": ["-m", "cyberark_rag.mcp_server"],
      "disabled": false
    }
  }
}
```

If you use system Python with PYTHONPATH:

```json
{
  "mcpServers": {
    "cyberark-rag": {
      "command": "python3",
      "args": ["-m", "cyberark_rag.mcp_server"],
      "env": {
        "PYTHONPATH": "/path/to/cyberark-rag"
      },
      "disabled": false
    }
  }
}
```

Replace `/path/to/cyberark-rag` with the absolute path to your project directory. Find it with `pwd` in the project root.

### 3. Restart Claude Desktop

Close and reopen Claude Desktop to load the new MCP server configuration.

### 4. Verify

Ask Claude: "Search CyberArk docs for PVWA configuration"

Claude should use the `search_cyberark_docs` tool and return documentation results. You will see the tool icon in the Claude Desktop interface when the server is connected.

## Claude Code Setup

### Option 1: CLI Command

```bash
claude mcp add cyberark-rag -- python3 -m cyberark_rag.mcp_server
```

### Option 2: Project Configuration

Add to `.claude/mcp.json` in your project directory:

```json
{
  "mcpServers": {
    "cyberark-rag": {
      "command": "python3",
      "args": ["-m", "cyberark_rag.mcp_server"],
      "env": {
        "PYTHONPATH": "/path/to/cyberark-rag"
      }
    }
  }
}
```

### Verify

Ask Claude Code: "Search CyberArk docs for Conjur Kubernetes authenticator"

## Tool Reference

All tools are read-only, non-destructive, and idempotent. They use the `cyberark_rag_` prefix to prevent name collisions with other MCP servers.

### search_cyberark_docs

Search CyberArk product documentation using hybrid semantic + keyword search. This is the primary tool.

**Parameters**:

| Parameter | Type | Default | Constraints | Description |
|---|---|---|---|---|
| `query` | string | (required) | non-empty | Search query in natural language |
| `top_k` | int | 5 | 1-20 | Number of results to return |
| `product_filter` | string | null | valid product key | Filter results to a specific product |
| `use_query_expansion` | bool | true | | Enable synonym and term expansion |
| `use_hybrid_search` | bool | true | | Enable BM25 + vector fusion |

**Example prompts that trigger this tool**:
- "Search CyberArk docs for how to configure Conjur Kubernetes authenticator"
- "Find CyberArk documentation about PVWA error 401"
- "What does CyberArk say about SPIFFE identity?"

**Example response format**:
```
Found 5 results for "configure conjur kubernetes authenticator":

1. Kubernetes Authenticator (Score: 0.94)
   Product: Conjur Cloud | Chunk: 3
   URL: https://docs.cyberark.com/conjur-cloud/Latest/en/Content/Conjur/conjur-authn-k8s.htm

   The Conjur Kubernetes Authenticator enables workloads running in
   Kubernetes to authenticate to Conjur using their Kubernetes identity...

2. Conjur Kubernetes Authentication Methods (Score: 0.89)
   ...
```

### get_command_example

Find CLI commands, API calls, and configuration examples for a specific CyberArk product and task.

**Parameters**:

| Parameter | Type | Default | Description |
|---|---|---|---|
| `product` | string | (required) | Product name (e.g., "Conjur", "PAM", "Privilege Cloud") |
| `task` | string | (required) | Task description (e.g., "authenticate", "rotate secret", "create policy") |

**Example prompts**:
- "Find command examples for authenticating with Conjur"
- "Show me how to rotate secrets in Privilege Cloud"
- "Get API examples for PAM account management"

The tool internally maps short product names to canonical keys (e.g., "conjur" to "conjur-cloud", "pam" to "pam-self-hosted") and searches for command-related content.

### list_products

Return all available product categories with their filter keys. Use this to discover valid values for the `product_filter` parameter.

**No parameters required.**

**Example response**:
```
Available CyberArk product categories:

  conjur-cloud              Conjur Cloud (Secrets Manager SaaS)
  pam-self-hosted           Privileged Access Manager (Self-Hosted)
  privilege-cloud-standard  Privilege Cloud
  endpoint-privilege-manager Endpoint Privilege Manager (EPM)
  dynamic-privileged-access Dynamic Privileged Access (DPA)
  secrets-hub               Secrets Hub
  identity                  CyberArk Identity
  ...

Total: 22 products
```

### get_index_stats

Return index health statistics: total chunks, products indexed, BM25 status, embedding model, and last index build time.

**No parameters required.**

**Example response**:
```
Index Statistics:
  Total chunks: 52,847
  Collection: cyberark_docs
  Database: ./chroma_db
  Embedding model: BAAI/bge-large-en-v1.5
  Chunk size: 800
  BM25 index: available
  Products indexed: 22
  Last indexed: 2026-02-25T10:30:00Z
```

### When Claude Chooses Each Tool

| User Intent | Tool Selected |
|---|---|
| General documentation search | `search_cyberark_docs` |
| Looking for specific commands or API usage | `get_command_example` |
| Wants to know what products are available | `list_products` |
| Checking if the index is healthy | `get_index_stats` |

## Combining with Other MCP Servers

The `cyberark_rag_` prefix on all tool names prevents collisions. You can run the cyberark-rag server alongside other MCP servers:

```json
{
  "mcpServers": {
    "cyberark-rag": {
      "command": "/path/to/cyberark-rag/.venv/bin/python3",
      "args": ["-m", "cyberark_rag.mcp_server"]
    },
    "github": {
      "command": "gh",
      "args": ["mcp", "serve"]
    }
  }
}
```

## Performance Notes

- **First call**: 5-10 seconds on M1 Max (loads embedding model into memory)
- **Subsequent calls**: 200-500ms (model stays in memory)
- **The MCP server process persists** between tool calls. No cold start after the first invocation.
- **Memory**: ~500 MB for MiniLM, ~2 GB for BGE-large (embedding model + ChromaDB)
