# Troubleshooting

Common problems and how to fix them.

## Installation Issues

### "No module named 'chromadb'"

You installed packages in a different Python environment than you are running. Verify you are using the correct virtual environment:

```bash
which python3
pip list | grep chromadb
```

If using a venv, activate it first:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### "sentence-transformers requires torch"

On some systems, PyTorch must be installed before sentence-transformers. Install it explicitly:

```bash
pip install torch
pip install sentence-transformers
```

### Python Version Conflicts

The MCP package requires Python 3.10+. Check your version:

```bash
python3 --version
```

If you have multiple Python versions, use a specific one:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### M1/M2/M3 Mac: Torch MPS vs CPU

PyTorch on Apple Silicon uses the MPS backend by default. If you encounter MPS-related errors during indexing, force CPU mode:

```bash
export PYTORCH_ENABLE_MPS_FALLBACK=1
python -m cyberark_rag index
```

## Scraper Issues

### "No sitemap found"

Check the sitemap URL manually:

```bash
curl -s -o /dev/null -w "%{http_code}" https://docs.cyberark.com/sitemap.xml
```

If the sitemap returns 404, the scraper falls back to inventorying existing `scraped_docs/*.json` files and re-scraping those URLs.

### "SSL: CERTIFICATE_VERIFY_FAILED"

Update your certificates:

```bash
pip install --upgrade certifi
```

On macOS, you may also need to run:

```bash
/Applications/Python\ 3.13/Install\ Certificates.command
```

### Scraper Hangs

The scraper may hang on slow network connections. Increase the delay and check your network:

```bash
python incremental_scraper.py --delay 2.0
```

### "0 pages to scrape" in Incremental Mode

All pages are up to date based on the stored state. This is normal if you ran the scraper recently.

To force a re-scrape:

```bash
python incremental_scraper.py --full
```

Or reset the state file:

```bash
rm scraper_state.json
python incremental_scraper.py
```

## Indexing Issues

### Out of Memory During Indexing

Reduce the batch size:

```bash
python -m cyberark_rag index --batch-size 50
```

Or use a smaller embedding model:

```bash
export CYBERARK_RAG_MODEL="all-MiniLM-L6-v2"
rm -rf chroma_db/ bm25_index.pkl
python -m cyberark_rag index
```

### "ChromaDB collection already exists"

Delete the existing database and rebuild:

```bash
rm -rf chroma_db/
python -m cyberark_rag index
```

### Indexing Takes Too Long

Expected times for ~19K documents:

| Model | Expected Time |
|---|---|
| `all-MiniLM-L6-v2` | ~5 minutes |
| `BAAI/bge-base-en-v1.5` | ~8 minutes |
| `BAAI/bge-large-en-v1.5` | ~15 minutes |

Close other applications to free CPU and memory.

### "No documents found in scraped_docs/"

Run the scraper first:

```bash
python incremental_scraper.py --full
```

Verify documents exist:

```bash
ls scraped_docs/ | head -5
ls scraped_docs/ | wc -l
```

## Search Issues

### "No results found"

1. Verify the index is built:

```bash
python -m cyberark_rag search --stats
```

2. Try a broader query without product filter:

```bash
python -m cyberark_rag search "authentication"
```

3. Verify BM25 index exists:

```bash
ls -la chroma_db/bm25_index.pkl 2>/dev/null || ls -la bm25_index.pkl 2>/dev/null
```

### Results Are Irrelevant

- Check if query expansion is adding wrong terms (see [Search Pipeline](search-pipeline.md#debugging-search-quality))
- Try narrowing with a product filter:

```bash
python -m cyberark_rag search "authentication" --product conjur-cloud
```

### Exact Terms Not Found

Verify the BM25 index exists. Without it, only vector search runs, which may miss exact-match terms like error codes:

```bash
python -m cyberark_rag search --stats
```

If BM25 is not available, rebuild the index:

```bash
python -m cyberark_rag index
```

### Results Show Prefixed Text

If search results start with "From CyberArk..." instead of clean content, the search pipeline is returning contextualized text instead of `original_text`. This is a bug; the search module should strip prefixes before returning results.

## MCP Server Issues

### "Connection refused" in Claude Desktop

1. Check your `claude_desktop_config.json` path and content:

```bash
cat ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

2. Verify the Python path in your config exists:

```bash
ls -la /path/from/config/python3
```

3. Verify the MCP server starts manually:

```bash
python -m cyberark_rag.mcp_server 2>/dev/null &
kill %1
```

### "Tool not found" in Claude

Restart Claude Desktop after changing the MCP configuration. Tools are registered at startup.

### Server Crashes Silently

The MCP server logs to stderr, not stdout (stdout is reserved for JSON-RPC). Check stderr output:

```bash
python -m cyberark_rag.mcp_server 2>/tmp/mcp-stderr.log &
sleep 2
cat /tmp/mcp-stderr.log
kill %1
```

### "ModuleNotFoundError"

The `PYTHONPATH` is not set to the project root. In your MCP config, either:

- Use the venv Python directly (no PYTHONPATH needed):

```json
{
  "command": "/path/to/cyberark-rag/.venv/bin/python3",
  "args": ["-m", "cyberark_rag.mcp_server"]
}
```

- Or set PYTHONPATH explicitly:

```json
{
  "command": "python3",
  "args": ["-m", "cyberark_rag.mcp_server"],
  "env": {"PYTHONPATH": "/path/to/cyberark-rag"}
}
```

### Slow First Response

The first tool call loads the embedding model into memory (5-10 seconds on M1 Max). Subsequent calls are fast (200-500ms). This is expected behavior.

## Terminal Assistant Issues

### "Ollama connection refused"

Start the Ollama server:

```bash
ollama serve
```

Verify it is running:

```bash
curl http://localhost:11434/api/tags
```

### "Model not found"

Pull the model specified in `config.yaml`:

```bash
ollama pull llama3.1
```

### "Permission denied on cyai"

Make the script executable:

```bash
chmod +x bin/cyai
```

## Diagnostic Commands

Run these to gather diagnostic information:

```bash
# Check Python environment
python3 --version
pip list | grep -E "chromadb|sentence|mcp|pydantic|torch"

# Check index health
python -m cyberark_rag search --stats

# Check MCP server starts without error
python -m cyberark_rag.mcp_server 2>/dev/null &
sleep 2
kill %1 2>/dev/null && echo "MCP server starts OK" || echo "MCP server failed"

# Check scraper state
python3 -c "import json; s=json.load(open('scraper_state.json')); print(f'Last run: {s[\"last_run\"]}'); print(f'Pages tracked: {len(s[\"pages\"])}')"

# Check disk usage
du -sh scraped_docs/ chroma_db/ bm25_index.pkl 2>/dev/null

# Verify no hardcoded paths
grep -rn "/Users/" cyberark_rag/ 2>/dev/null && echo "WARNING: hardcoded paths found" || echo "No hardcoded paths"
```
