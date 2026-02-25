# Getting Started

Zero-to-working walkthrough. You should have a functioning search system in about 10 minutes (excluding scrape time).

## Prerequisites

- Python 3.10+ (3.13 recommended)
- pip
- ~2 GB disk for index + embedding model
- (Optional) [Claude Desktop](https://claude.ai/download) or [Claude Code](https://docs.anthropic.com/en/docs/claude-code) for MCP integration
- (Optional) [Ollama](https://ollama.ai) for the terminal assistant

## Installation

Clone the repository and create a virtual environment:

```bash
git clone https://github.com/infamousjoeg/cyberark-rag.git
cd cyberark-rag
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Verify the installation:

```bash
$ python -m cyberark_rag --help
Usage: python -m cyberark_rag {index|search|mcp_server|terminal}
```

> **Note:** The embedding model downloads on first run (~1.3 GB for BGE-large, ~80 MB for MiniLM).

## First Run: Scrape Documentation

Preview what the scraper will fetch before committing:

```bash
$ python incremental_scraper.py --dry-run
Fetching sitemap from https://docs.cyberark.com/sitemap.xml...
Found 18,247 URLs in sitemap
Total valid URLs: 17,893
Pages to scrape: 17,893
  Would scrape: https://docs.cyberark.com/conjur-cloud/Latest/en/Content/Conjur/conjur-authn-k8s.htm
  Would scrape: https://docs.cyberark.com/privilege-cloud-standard/Latest/en/Content/PASIMP/PVWA-Overview.htm
  ... and 17,891 more
```

Run the full scrape (first run takes 2-4 hours; subsequent incremental runs take minutes):

```bash
python incremental_scraper.py --full
```

If you already have a `scraped_docs/` directory from a previous run, skip straight to indexing.

## Build the Index

```bash
$ python -m cyberark_rag index
Loading documents from scraped_docs/...
Loaded 19,378 documents
Chunking documents...
Created 52,847 chunks (800 tokens, 100 overlap)
Contextualizing chunks...
Building embeddings and indexing to ChromaDB...
Building BM25 index...
Done. 52,847 chunks indexed in 8m 32s.
```

This step:
1. Splits documents into 800-token chunks with paragraph-aware boundaries
2. Adds contextual prefixes (product name, page title, section heading) to each chunk
3. Embeds the contextualized text into ChromaDB using the BGE-large model
4. Builds a BM25 keyword index from the same text for hybrid search

## Test a Search

```bash
$ python -m cyberark_rag search "configure conjur kubernetes authenticator"

Search results for: "configure conjur kubernetes authenticator"
============================================================

[1] Score: 0.94 | conjur-cloud | Chunk 3
    Kubernetes Authenticator
    https://docs.cyberark.com/conjur-cloud/Latest/en/Content/Conjur/conjur-authn-k8s.htm

    The Conjur Kubernetes Authenticator enables workloads running in Kubernetes
    to authenticate to Conjur using their Kubernetes identity. This eliminates
    the need for static API keys or passwords stored in pods...

[2] Score: 0.89 | conjur-cloud | Chunk 0
    Conjur Kubernetes Authentication Methods
    https://docs.cyberark.com/conjur-cloud/Latest/en/Content/Conjur/k8s-auth-methods.htm

    Conjur supports multiple authentication methods for Kubernetes workloads...
```

Try these searches to verify different aspects of the system:

```bash
# Exact-match (tests BM25)
python -m cyberark_rag search "PVWA error 401"

# Conceptual (tests vector search)
python -m cyberark_rag search "what is SPIFFE identity"

# Product-filtered
python -m cyberark_rag search "authentication" --product conjur-cloud

# Index statistics
python -m cyberark_rag search --stats
```

## Connect to Claude Desktop

1. Open your Claude Desktop configuration file:
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Linux: `~/.config/claude/claude_desktop_config.json`

2. Add the cyberark-rag server:

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

Replace `/path/to/cyberark-rag` with the absolute path to your project directory. Find it with `pwd` in the project root.

3. Restart Claude Desktop.

4. Verify by asking Claude: "Search CyberArk docs for PVWA configuration"

Claude will use the `search_cyberark_docs` tool and return documentation results.

## Connect to Claude Code

Add the MCP server to Claude Code:

```bash
claude mcp add cyberark-rag -- python3 -m cyberark_rag.mcp_server
```

Or add it to `.claude/mcp.json` in your project:

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

Verify by asking Claude Code: "Search CyberArk docs for Conjur Kubernetes authenticator"

## Next Steps

- [Configuration](configuration.md) -- Customize embedding models, chunk sizes, search weights
- [Scraper Guide](scraper-guide.md) -- Automate documentation updates with cron
- [Architecture](architecture.md) -- Understand how the search pipeline works
- [MCP Integration](mcp-integration.md) -- Detailed tool reference and usage patterns
