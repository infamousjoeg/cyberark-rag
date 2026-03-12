# Google Embeddings v2 Analysis for CyberArk RAG

**Date:** 2026-03-12
**Current Model:** BAAI/bge-large-en-v1.5 (1024 dimensions, self-hosted via sentence-transformers)

## Executive Summary

Google's embedding model lineup has evolved rapidly. The term "Google Embeddings v2" most likely refers to **Gemini Embedding 2** (released March 10, 2026), the successor to `text-embedding-004` (deprecated) and `gemini-embedding-001`. While these models offer strong retrieval performance (MTEB retrieval score ~67.71 for gemini-embedding-001), they are **API-only** with no self-hosted option. This introduces vendor lock-in, ongoing costs, latency concerns, and a privacy trade-off that conflicts with the project's self-hosted architecture.

**Recommendation:** Do not switch to Google Gemini Embedding models. Instead, consider upgrading to an open-source model like **Qwen3-Embedding** or **NV-Embed-v2** if retrieval quality improvements are needed beyond what `bge-large-en-v1.5` provides.

---

## Google Embedding Model Timeline

| Model | Status | Dimensions | MTEB Avg | Notes |
|---|---|---|---|---|
| `text-embedding-004` | Deprecated (Jan 2026) | 768 (truncatable from 3072) | 66.31 | Was Vertex AI's flagship |
| `gemini-embedding-001` | GA | 3072 (truncatable to 768) | 68.32 | #1 MTEB Multilingual |
| `gemini-embedding-2-preview` | Public Preview (Mar 2026) | 3072 (truncatable to 128) | 68.17 | First multimodal embedding model |

### Gemini Embedding 001 Specs

- **Dimensions:** 3072 default, truncatable to 1536 or 768 via Matryoshka Representation Learning
- **Context window:** 2,048 tokens
- **Languages:** 100+
- **MTEB Retrieval (nDCG@10):** 67.71 -- best among API models
- **Pricing:** $0.15 per 1M input tokens
- **Access:** API-only (Gemini API / Vertex AI). No model weights available.

### Gemini Embedding 2 (Preview) Specs

- **Dimensions:** 3072 default, truncatable down to 128
- **Context window:** 8,192 tokens (4x improvement)
- **Modalities:** Text, images, video, audio, documents (single vector space)
- **MTEB scores by dimension:** 68.17 (1536d), 68.16 (2048d), 67.99 (768d)
- **Pricing:** $0.20 per 1M tokens (batch API: $0.10/1M)
- **Access:** API-only. Preview status -- subject to changes before GA.

---

## Comparison: Current Setup vs Google Embeddings

| Factor | BAAI/bge-large-en-v1.5 (Current) | Gemini Embedding 001 | Gemini Embedding 2 |
|---|---|---|---|
| **Hosting** | Self-hosted, local inference | API-only (Google Cloud) | API-only (Google Cloud) |
| **Dimensions** | 1024 | 3072 (truncatable) | 3072 (truncatable to 128) |
| **Max Tokens** | 512 | 2,048 | 8,192 |
| **MTEB Average** | ~63-64 (at release) | 68.32 | 68.17 |
| **Cost** | Free (local compute) | $0.15/1M tokens | $0.20/1M tokens |
| **Latency** | ~50-200ms on M1 Max | ~13ms API + network RTT | Similar + network RTT |
| **Data Privacy** | Full control | Data sent to Google | Data sent to Google |
| **Offline Use** | Yes | No | No |
| **Fine-tunable** | Yes | No | No |
| **sentence-transformers** | Yes | No | No |
| **Multimodal** | No | No | Yes (text, image, video, audio, docs) |

---

## Impact Analysis for CyberArk RAG

### Potential Benefits

1. **Higher retrieval accuracy:** MTEB retrieval score improvement from ~63 (bge-large) to ~67.7 (gemini-embedding-001) could meaningfully improve search quality, especially for ambiguous or cross-product queries.

2. **Longer context windows:** 8,192 tokens (Gemini Embedding 2) vs 512 tokens (bge-large) means larger chunks could be embedded without truncation. Our current 800-token chunk size already exceeds bge-large's 512 limit -- Gemini would handle this natively.

3. **Matryoshka dimensions:** Ability to truncate embeddings (3072 -> 768 -> 256) enables a two-stage retrieval pattern -- fast coarse search with small vectors, then re-rank with full vectors.

### Blocking Concerns

1. **API-only access -- no self-hosting.** The CyberArk RAG system is designed as a fully self-contained, offline-capable tool. Every component (scraper, indexer, ChromaDB, BM25, MCP server) runs locally. Introducing a cloud API dependency breaks this architecture fundamentally.

2. **Vendor lock-in.** Switching embedding models means re-indexing the entire ~19K document corpus (~50K chunks). If Google deprecates or changes the model (as they did with `text-embedding-004`), another full re-index is required. The deprecation of `text-embedding-004` in January 2026 (less than 3 months ago) demonstrates this risk is real.

3. **Ongoing cost.** At $0.15-0.20 per 1M tokens, indexing ~50K chunks at ~800 tokens each = ~40M tokens = ~$6-8 per full re-index. Not expensive, but every search query also requires an API call for the query embedding. At scale, this adds up vs. zero marginal cost with local inference.

4. **Latency and reliability.** Local inference on M1 Max gives consistent ~50-200ms per query. API calls add network round-trip time and introduce a dependency on Google Cloud availability. The MCP server model (long-running process, lazy-loaded model) is optimized for local inference -- the model loads once and stays in memory.

5. **Data privacy.** CyberArk documentation is public, so privacy is less of a concern here. However, user queries sent to Google's API could reveal what an organization is troubleshooting or configuring, which may be sensitive in security contexts.

6. **Code architecture changes required.** The current pipeline uses `sentence-transformers` throughout (indexer.py and search.py). Switching to Gemini Embedding requires:
   - Replacing `SentenceTransformer.encode()` with async HTTP calls to the Gemini API
   - Adding `google-genai` SDK as a dependency
   - Handling API authentication (API key management)
   - Adding retry logic, rate limiting, and error handling for API calls
   - Modifying both indexer and search to use the API client
   - The embedding function abstraction does not exist -- this is a significant refactor

7. **Embedding space incompatibility.** Gemini Embedding 2 embeddings are incompatible with Gemini Embedding 001 embeddings. Any future model upgrade from Google requires a complete re-index. With self-hosted models, you control the timing of such migrations.

---

## Better Alternatives

If retrieval quality needs improvement beyond bge-large-en-v1.5, these open-source models maintain the self-hosted architecture:

| Model | Dimensions | Params | MTEB Avg | Context | Notes |
|---|---|---|---|---|---|
| **Qwen3-Embedding-8B** | 32-4096 | 8B | Competitive with Gemini | 32K tokens | Best overall open-source; Matryoshka support |
| **NV-Embed-v2** | 4096 | 7B | 72.31 | 32K tokens | Top MTEB overall, based on Mistral-7B |
| **ModernBERT-Embed** | 768 | ~150M | Strong English | 8192 tokens | Apache-2.0, lightweight, Nomic AI |
| **Nomic Embed Text V2** | Flexible | MoE | 86.2% top-5 acc | Long context | Good accuracy/speed balance |
| **Snowflake Arctic-Embed L v2** | 1024 | 335M | Strong retrieval | Standard | Apache-2.0, 74 languages |

### Recommended Upgrade Path

If the current model is insufficient:

1. **Low effort, moderate gain:** Switch to `Snowflake/snowflake-arctic-embed-l-v2.0` (1024d, same dimension as current, drop-in via sentence-transformers, Apache-2.0)
2. **Medium effort, large gain:** Switch to `nomic-ai/modernbert-embed` (768d, Apache-2.0, 8192 token context, runs via sentence-transformers)
3. **High effort, maximum gain:** Deploy `Qwen3-Embedding-8B` via a local inference server (vLLM/Ollama), requires GPU and more infrastructure

All of these maintain the self-hosted, zero-cost, offline-capable architecture.

---

## Conclusion

Google's Gemini Embedding models are impressive on benchmarks, but they are a poor fit for this project because:

1. **API-only** -- breaks the self-hosted architecture
2. **Vendor lock-in** -- Google has already deprecated one embedding model this year
3. **Ongoing cost** -- vs. zero marginal cost for local inference
4. **Significant refactor** -- requires replacing sentence-transformers with API calls throughout

The current `BAAI/bge-large-en-v1.5` model is solid. If retrieval quality improvements are needed, open-source alternatives (Snowflake Arctic, ModernBERT-Embed, Qwen3-Embedding) provide better gains without sacrificing the project's core architecture.

---

## Sources

- [Google Developers Blog: Gemini Embedding now generally available](https://developers.googleblog.com/en/gemini-embedding-text-model-now-available-gemini-api/)
- [Gemini Embedding 2 Launch (adwaitx.com)](https://www.adwaitx.com/gemini-embedding-2-multimodal-ai-model/)
- [Gemini API Embeddings Documentation](https://ai.google.dev/gemini-api/docs/embeddings)
- [MTEB Rankings March 2026](https://awesomeagents.ai/leaderboards/embedding-model-leaderboard-mteb-march-2026/)
- [Embedding Models Pricing March 2026](https://awesomeagents.ai/pricing/embedding-models-pricing/)
- [Best Open-Source Embedding Models 2026 (BentoML)](https://www.bentoml.com/blog/a-guide-to-open-source-embedding-models)
- [Best Open-Source Embedding Models Benchmarked (Supermemory)](https://supermemory.ai/blog/best-open-source-embedding-models-benchmarked-and-ranked/)
- [Gemini Embedding 2 Pricing vs OpenAI (TokenCost)](https://tokencost.app/blog/gemini-embedding-2-pricing)
- [BAAI/bge-large-en-v1.5 on Hugging Face](https://huggingface.co/BAAI/bge-large-en-v1.5)
- [10 Best Embedding Models 2026 (Openxcell)](https://www.openxcell.com/blog/best-embedding-models/)
