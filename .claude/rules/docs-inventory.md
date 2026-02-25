# Documentation Inventory

Every document listed below must be created. Each section heading is mandatory. Add subsections as needed but do not remove any listed here.

---

## README.md

The project's front door. Someone landing on the GitHub repo reads this first.

### Sections

**Project Title and Badges**
- Title: CyberArk Documentation RAG
- Badges: Python 3.13+, License, MCP Compatible
- One-sentence description: "Semantic search over CyberArk's complete product documentation, powered by hybrid vector + BM25 retrieval and served via MCP for Claude Desktop and Claude Code."

**Features**
- Hybrid search (vector + BM25 with Reciprocal Rank Fusion)
- Contextual chunk enrichment (Anthropic's Contextual Retrieval technique)
- Incremental documentation updates via sitemap (minutes, not hours)
- 4 MCP tools for Claude integration
- Query expansion with 80+ CyberArk-specific term groups
- Intent-aware re-ranking (how-to, reference, troubleshooting, explanation)
- Covers 22+ CyberArk products: Privilege Cloud, Conjur Cloud/Enterprise, Secrets Manager, Secrets Hub, EPM, Identity, DPA, Secure Workload Access, and more

**Quick Start**
- 5-step block: clone, install deps, scrape (dry-run first), index, configure Claude Desktop
- Link to docs/getting-started.md for the full walkthrough

**Architecture Diagram**
- ASCII or Mermaid diagram showing: scraper -> scraped_docs -> indexer -> ChromaDB + BM25 -> search -> MCP server -> Claude
- Link to docs/architecture.md

**MCP Tools**
- Table of the 4 tools with name, description, key parameters
- Link to docs/mcp-integration.md

**Configuration**
- Quick reference table of env vars with defaults
- Link to docs/configuration.md

**Documentation**
- Linked list of all docs/ files with one-line descriptions

**Contributing**
- Link to docs/contributing.md

**License**
- MIT or whatever the project uses

---

## docs/getting-started.md

Zero-to-working walkthrough. A developer with Python experience but no CyberArk knowledge should have a working system in 10 minutes.

### Sections

**Prerequisites**
- Python 3.10+ (3.13 recommended)
- pip
- ~2 GB disk for index + model
- (Optional) Claude Desktop or Claude Code for MCP integration
- (Optional) Ollama for terminal assistant

**Installation**
- Clone repo
- Create venv: `python3 -m venv .venv && source .venv/bin/activate`
- Install deps: `pip install -r requirements.txt`
- Verify: `python -m cyberark_rag --help`
- Include expected output

**First Run: Scrape Documentation**
- Dry run first: `python incremental_scraper.py --dry-run`
- Include sample output showing URL discovery
- Full scrape: `python incremental_scraper.py --full`
- Explain this takes 2-4 hours for first run (subsequent runs: minutes)
- Alternative: if user has existing scraped_docs/, skip to indexing

**Build the Index**
- `python -m cyberark_rag index`
- Include sample output showing chunk count, time elapsed
- Explain what contextual chunking and BM25 indexing do (2 sentences each)

**Test a Search**
- `python -m cyberark_rag search "configure conjur kubernetes authenticator"`
- Include sample output showing ranked results with titles, URLs, scores

**Connect to Claude Desktop**
- Copy mcp_config.json content
- Where to put it: `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)
- Restart Claude Desktop
- Verify: ask Claude "Search CyberArk docs for PVWA configuration"

**Connect to Claude Code**
- `claude mcp add cyberark-rag -- python3 -m cyberark_rag.mcp_server`
- Or add to `.claude/mcp.json` in the project
- Verify: `claude "Search CyberArk docs for Conjur Kubernetes authenticator"`

**Next Steps**
- Links to: configuration.md (customize), scraper-guide.md (automate updates), architecture.md (understand internals)

---

## docs/architecture.md

System design for contributors and advanced users.

### Sections

**System Overview**
- Mermaid diagram of complete data flow
- Component responsibilities (1-2 sentences each)

**Data Pipeline**
- Scraper: sitemap-driven, incremental, state tracking
- Indexer: chunk -> contextualize -> embed -> ChromaDB + BM25
- Chunk size rationale (800 tokens, Anthropic research)
- Contextual prefix format and why it matters (35% retrieval improvement)

**Search Pipeline**
- Query expansion (80+ term groups from query_expansions.yaml)
- Intent detection (how-to, explanation, reference, troubleshooting, general)
- Hybrid search: vector (top_k*3) + BM25 (top_k*3) -> RRF -> intent re-ranking -> top_k
- Content classification (procedural, conceptual, reference, code-example)
- Scoring: relevance_score = f(vector_distance, bm25_score, intent_boost)

**Module Dependency Graph**
- ASCII or Mermaid showing import relationships
- Note singleton patterns for expensive resources

**MCP Server**
- FastMCP with Pydantic schemas
- Tool annotations (readOnlyHint, destructiveHint, idempotentHint)
- stdio transport, lazy-load search engine on first call
- JSON-RPC protocol (stdout reserved, logging to stderr)

**Data Footprint**
- scraped_docs/: ~176 MB (~19,378 JSON files)
- chroma_db/: ~1.2 GB (with all-MiniLM-L6-v2), ~3.8 GB (with bge-large-en-v1.5)
- bm25_index.pkl: ~50-100 MB
- Embedding model download: ~80 MB (MiniLM) or ~1.3 GB (BGE-large)

---

## docs/configuration.md

Every knob in the system. Organized by component.

### Sections

**Environment Variables**
- Table: variable name, default, type, description, example
- Cover all CYBERARK_RAG_* vars
- Cover ANTHROPIC_API_KEY (optional, for LLM-powered contextual retrieval)

**config.yaml**
- Full annotated YAML with every key explained
- Ollama endpoint and model
- MCP python path and context chunk count
- Execution settings (auto_execute, show_context)

**mcp_config.json**
- Claude Desktop format with env vars
- How to set PYTHONPATH correctly for different install methods (venv, system, pipx)

**product_aliases.yaml**
- Structure explanation
- How to add a new product alias
- Category meanings: product, deprecated, metadata, navigation

**query_expansions.yaml**
- Structure explanation
- How to add a new expansion group
- Weighting (0.7x for expansion terms vs 1.0x for original)

**Embedding Model Selection**
- Table: model name, dimensions, download size, index size, quality tier
- all-MiniLM-L6-v2: 384d, 80 MB, ~1.2 GB index, good
- BAAI/bge-base-en-v1.5: 768d, 420 MB, ~2.4 GB index, better
- BAAI/bge-large-en-v1.5: 1024d, 1.3 GB, ~3.8 GB index, best
- How to switch: set CYBERARK_RAG_MODEL, delete chroma_db/ and bm25_index.pkl, re-index

**BM25 Parameters**
- k1 (default 1.5): term frequency saturation
- b (default 0.75): document length normalization
- When to adjust: if short docs dominate results, lower b

**Hybrid Search Weights**
- vector_weight (0.7), bm25_weight (0.3), k (60)
- When to adjust: if exact-match queries return poorly, increase bm25_weight

---

## docs/scraper-guide.md

Operating the documentation scraper.

### Sections

**Incremental vs Full Scrape**
- Incremental (default): uses sitemap lastmod to detect changes, 2-10 min
- Full (--full): re-scrapes every URL, 2-4 hours for ~19K pages
- When to use each

**CLI Reference**
- Every flag with examples and expected output
- --dry-run, --full, --delay, --output-dir

**State File (scraper_state.json)**
- Structure explanation
- How to inspect: `python -c "import json; print(json.dumps(json.load(open('scraper_state.json')), indent=2))" | head -20`
- How to reset: delete the file (next run treats everything as new)

**Automating Updates**
- Cron job example (weekly)
- Combined scrape + re-index script (scripts/update.sh)
- Monitoring: check scraper output for error count

**Sitemap Fallback**
- What happens if docs.cyberark.com has no sitemap
- Falls back to URL inventory from existing scraped_docs/*.json
- All existing URLs get re-scraped (equivalent to --full)

**Troubleshooting Scraper Issues**
- "No sitemap found" - check URL, try curl manually
- "0 pages to scrape" in incremental mode - all pages up to date, or state file has future timestamps
- Rate limiting / 429 errors - increase --delay
- SSL errors - check system certificates

---

## docs/indexing-guide.md

Building and maintaining the search index.

### Sections

**Quick Index Build**
- `python -m cyberark_rag index`
- Expected output and timing (~5-15 min for full index)

**What Happens During Indexing**
- Step 1: Load JSON files from scraped_docs/
- Step 2: Chunk text (800 tokens, 100 overlap, paragraph-aware)
- Step 3: Contextualize chunks (prepend metadata-derived prefix)
- Step 4: Embed contextualized text -> ChromaDB
- Step 5: Build BM25 index from same text -> bm25_index.pkl
- Step 6: Save index stats

**Contextual Retrieval Explained**
- What: prepend "From CyberArk {Product} documentation, page titled '{Title}', in the section about {Heading}. " to each chunk before embedding
- Why: Anthropic research shows 35% fewer retrieval failures
- Example: before and after for a Conjur K8s auth chunk

**Re-indexing**
- When to re-index: after scraping new content, after changing embedding model, after changing chunk size
- Partial re-index: not supported; always rebuilds from scratch
- Clean rebuild: `rm -rf chroma_db/ bm25_index.pkl && python -m cyberark_rag index`

**Upgrading the Embedding Model**
- Step-by-step: set env var, delete old index, rebuild
- Timing and disk impact for each model option

**LLM-Powered Contextual Retrieval (Optional)**
- Requires ANTHROPIC_API_KEY
- Uses Claude Haiku with prompt caching
- Cost estimate: ~$1.02 per million document tokens
- Expected improvement: 49-67% fewer retrieval failures (vs 35% for metadata-only)

---

## docs/mcp-integration.md

Connecting the RAG system to Claude Desktop and Claude Code.

### Sections

**Overview**
- MCP (Model Context Protocol) allows Claude to call external tools
- The cyberark-rag MCP server exposes 4 search tools over stdio transport

**Claude Desktop Setup**
- Step-by-step with exact file paths for macOS, Linux
- Full mcp_config.json content (copy-pasteable)
- How to verify: what to ask Claude, what response looks like
- Screenshot placeholder description (tool icon appears in Claude Desktop)

**Claude Code Setup**
- `claude mcp add` command
- .claude/mcp.json alternative
- Verify with `claude "list available MCP tools"`

**Tool Reference**
- For each of the 4 tools:
  - Name, description, parameters (type, default, constraints)
  - Example prompt that triggers the tool
  - Example response format
  - When Claude chooses this tool vs another

**Combining with Other MCP Servers**
- cyberark_rag_* prefix prevents name collisions
- Example: running alongside GitGuardian MCP, GitHub MCP

**Performance Notes**
- First call is slow (loads embedding model, ~5-10 sec on M1 Max)
- Subsequent calls: ~200-500ms
- The MCP server stays running between calls (no cold start after first)

---

## docs/search-pipeline.md

Deep dive into how search works for users who want to tune or debug.

### Sections

**Query Flow**
- Numbered step-by-step with example query "how to configure conjur kubernetes authenticator"
- Show the transformed query at each stage

**Query Expansion**
- How expansion groups work
- Example: "conjur" adds "dap", "secrets-manager"; "kubernetes" adds "k8s", "openshift"
- Expansion weight (0.7x) vs original (1.0x)

**Intent Detection**
- 5 intent types with example queries for each
- How intent affects re-ranking (boost multipliers table)

**Hybrid Search**
- Vector search: encode query, cosine similarity against ChromaDB
- BM25 search: tokenize query, score against inverted index
- Why both: vector catches semantic similarity, BM25 catches exact terms
- Example: "PVWA error 401" - BM25 finds exact error code, vector finds related troubleshooting

**Reciprocal Rank Fusion**
- Formula: score = sum(weight / (k + rank + 1))
- Why RRF over other fusion methods (simple, no score normalization needed)
- Default weights: vector 0.7, BM25 0.3

**Intent Re-ranking**
- Content type classification (procedural, conceptual, reference, code-example)
- Boost matrix: intent x content_type -> multiplier
- Example: how-to query boosts procedural content 2x, penalizes reference content 0.8x

**Debugging Search Quality**
- `python -m cyberark_rag search "your query" --verbose` (if available)
- Check if query expansion is adding wrong terms
- Check if product filter is too narrow
- Check if BM25 vs vector disagree on ranking

---

## docs/troubleshooting.md

Common problems and how to fix them.

### Sections

**Installation Issues**
- "No module named 'chromadb'" - pip install in wrong environment
- "sentence-transformers requires torch" - install torch first on some systems
- Python version conflicts - use pyenv or venv
- M1/M2 Mac specific: torch MPS vs CPU

**Scraper Issues**
- "No sitemap found" - manual sitemap URL check
- "SSL: CERTIFICATE_VERIFY_FAILED" - certifi update or system certs
- Scraper hangs - network timeout, increase --delay
- "0 pages to scrape" - state file issue, try --full or delete state file

**Indexing Issues**
- "Out of memory during indexing" - reduce batch_size, use smaller embedding model
- "ChromaDB collection already exists" - delete chroma_db/ and rebuild
- Indexing takes too long - expected times for each embedding model
- "No documents found in scraped_docs/" - run scraper first

**Search Issues**
- "No results found" - check if index is built, try broader query
- Results are irrelevant - check query expansion, try product filter
- Exact terms not found - verify BM25 index exists (bm25_index.pkl)
- Results show prefixed text instead of clean content - search.py should return original_text

**MCP Server Issues**
- "Connection refused" in Claude Desktop - check mcp_config.json path and PYTHONPATH
- "Tool not found" - restart Claude Desktop after config change
- Server crashes silently - check stderr (MCP servers must not log to stdout)
- "ModuleNotFoundError" - PYTHONPATH not set to project root
- Slow first response - embedding model loading, expected on first call

**Terminal Assistant Issues**
- "Ollama connection refused" - start Ollama: `ollama serve`
- "Model not found" - `ollama pull llama3.1`

**Diagnostic Commands**
```bash
# Check Python environment
python3 --version
pip list | grep -E "chromadb|sentence|mcp|pydantic"

# Check index health
python -m cyberark_rag search --stats

# Check MCP server starts
python -m cyberark_rag.mcp_server 2>/dev/null &
kill %1

# Check scraper state
python3 -c "import json; s=json.load(open('scraper_state.json')); print(f'Last run: {s[\"last_run\"]}'); print(f'Pages tracked: {len(s[\"pages\"])}')"

# Check disk usage
du -sh scraped_docs/ chroma_db/ bm25_index.pkl
```

---

## docs/contributing.md

For developers who want to modify or extend the system.

### Sections

**Development Setup**
- Clone, venv, install deps (including dev deps)
- Install pre-commit hooks (if any)
- Run tests: `pytest -v`

**Project Structure**
- File tree with one-line descriptions for every file
- Which files are auto-generated (chroma_db/, bm25_index.pkl, scraper_state.json)

**Testing**
- How to run tests: `pytest -v`, `pytest -v --cov`
- Test structure: conftest.py fixtures, per-module test files
- Writing new tests: follow Arrange-Act-Assert, use fixtures from conftest.py
- Coverage target: 80%+ on new modules

**Adding a New CyberArk Product**
- Step 1: Add to product_aliases.yaml (canonical name, display name, aliases, category)
- Step 2: Add expansion terms to query_expansions.yaml
- Step 3: Re-scrape if needed (product may already be in scraped docs)
- Step 4: Re-index to pick up alias changes

**Adding a New MCP Tool**
- Define Pydantic input model
- Add @mcp.tool() decorated function with cyberark_rag_ prefix
- Add tool annotations (readOnlyHint, destructiveHint, etc.)
- Add tests in test_mcp_server.py
- Update mcp-integration.md tool reference

**Code Style**
- Type hints on all functions
- Docstrings on all public methods
- f-strings over .format()
- pathlib.Path over os.path
- Logging to stderr only (never stdout in MCP context)
- No em-dashes

**Pull Request Checklist**
- [ ] `pytest -v` passes
- [ ] No hardcoded absolute paths (`grep -rn "/Users/" .`)
- [ ] New code has tests
- [ ] Docs updated if behavior changed
- [ ] Commit messages follow conventional commits (feat:, fix:, docs:, test:, refactor:)

---

## docs/changelog.md

Version history template. Pre-populate with v2.0.0 covering all the improvements.

### Sections

**v2.0.0 (Current)**
- Incremental sitemap-driven scraper (replaces BFS crawler)
- Contextual Retrieval chunk enrichment (Anthropic best practice)
- BM25 hybrid search with Reciprocal Rank Fusion
- FastMCP server with Pydantic schemas and tool annotations
- Central configuration via environment variables
- pytest test suite (replaces custom test harness)
- No more hardcoded paths

**v1.0.0 (Legacy)**
- Initial BFS scraper
- ChromaDB vector-only search
- Low-level MCP Server class
- Custom test framework
- Hardcoded paths to developer machine
