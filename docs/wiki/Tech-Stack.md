# Tech Stack

CCE is built on a small set of well-chosen libraries. This page explains what each one does, why it was chosen over the alternatives, and what trade-offs it brings.

---

## Embedding Model — BAAI/bge-small-en-v1.5

**What it does:** Converts code chunks and queries into 384-dimensional vectors for semantic similarity search.

**Why this model:**

| Model | Size | Quality | Speed |
|-------|------|---------|-------|
| `all-MiniLM-L6-v2` | 80MB | Good | Fast |
| `BAAI/bge-small-en-v1.5` | 60MB | Better | Fast |
| `text-embedding-ada-002` (OpenAI) | Cloud | Best | Network-dependent |

BGE-small beats MiniLM on retrieval benchmarks (MTEB) while being 33% smaller. It runs entirely locally with no API keys or network calls. The OpenAI alternative would require a paid API and introduces latency and privacy concerns.

**Runtime:** fastembed (ONNX Runtime) — no PyTorch dependency, no GPU required. The model runs in under 50ms per batch on a standard laptop CPU.

---

## Vector Store — LanceDB

**What it does:** Stores chunk embeddings and handles approximate nearest-neighbor (ANN) search.

**Why LanceDB:**

- **Embedded** — runs in-process, no server to start or manage. The database is a directory on disk.
- **Fast** — columnar storage format (Lance) gives fast scans and good compression. IVF_SQ indexing with int8 quantization reduces storage by ~75% with <2% quality loss.
- **Filtered search** — supports SQL-style `WHERE` clauses on metadata fields (e.g. `file_path = 'auth.py'`). CCE uses this for the graph-aware expansion step.
- **Python-native** — no separate process, no Docker, no config files.

**Alternatives considered:**

- **Chroma** — similar embedded approach but slower writes and higher memory use.
- **Weaviate / Qdrant** — excellent for production deployments but require running a separate server. Wrong for a local CLI tool.
- **pgvector** — requires PostgreSQL. Heavyweight for a developer tool.
- **FAISS** — fast but no persistence or metadata filtering out of the box.

---

## Full-Text Search — SQLite FTS5

**What it does:** BM25 keyword ranking over raw chunk content. Runs in parallel with vector search; results are merged via RRF.

**Why FTS5:**

Vector search alone misses exact matches. If you search for `stripe_api_key`, the vector match for "API key configuration" might rank a generic config chunk higher than the specific constant. FTS5 catches these keyword-exact cases.

FTS5 is built into SQLite (available everywhere, zero dependencies). BM25 is the standard ranking algorithm for keyword search — the same algorithm used by Elasticsearch and Solr under the hood.

The combination of vector + BM25 via RRF consistently outperforms either approach alone on code retrieval tasks.

---

## Code Graph — SQLite

**What it does:** Stores nodes (functions, classes, files) and edges (CALLS, IMPORTS, DEFINES) extracted during indexing. Used for 1-hop graph expansion after retrieval.

**Why SQLite:**

The graph is sparse (most functions call fewer than 10 others) and only needs simple neighbor lookups — no multi-hop traversal, no complex graph algorithms. SQLite with indexed foreign keys handles this trivially. A dedicated graph database (Neo4j, NetworkX) would be massive overkill.

Schema:

```sql
nodes (id, node_type, name, file_path, properties)
edges (source_id, target_id, edge_type, properties)
```

**Graph expansion:** After the primary vector search, CCE queries `edges` to find files reachable via CALLS or IMPORTS from the top result files. This surfaces related context that pure semantic search would miss.

---

## AST Parsing — Tree-sitter

**What it does:** Parses source code into an Abstract Syntax Tree (AST), enabling CCE to split files into meaningful chunks (functions, classes) rather than arbitrary line ranges.

**Why Tree-sitter:**

- **Fast** — incremental parsing, sub-millisecond per file.
- **Multi-language** — same API for Python, JavaScript, TypeScript, PHP, and dozens more.
- **Error-tolerant** — parses files with syntax errors, which matters for in-progress code.
- **Accurate** — produces real ASTs, not regex-based approximations.

**What it enables:** A 800-line Python file becomes 18 independent chunks (15 functions + 3 classes), each embedded separately. Claude retrieves the `calculate_shipping` function (60 lines) instead of the entire file.

**Current language support:** Python, JavaScript, TypeScript, JSX, TSX, PHP.

---

## MCP (Model Context Protocol)

**What it does:** The protocol that connects CCE to Claude Code. CCE runs as an MCP server; Claude Code discovers it via `.mcp.json` and calls its tools (`context_search`, `expand_chunk`, etc.).

**Why MCP:**

MCP is Anthropic's official protocol for extending Claude Code with external tools. It is the only first-party way to give Claude persistent, queryable context. CCE uses stdio transport (local process), which means no network, no authentication, and instant startup.

`.mcp.json` (written by `cce init`):
```json
{
  "mcpServers": {
    "context-engine": {
      "command": "cce",
      "args": ["serve", "--project-dir", "/path/to/your/project"]
    }
  }
}
```

---

## Optional LLM Compression — Ollama

**What it does:** When Ollama is running locally, CCE uses `phi3:mini` (or your configured model) to produce higher-quality summaries of code chunks before including them in responses.

**Why Ollama:**

Ollama makes it trivial to run small LLMs locally with no API keys. `phi3:mini` is a 3.8B parameter model that runs well on 8GB RAM and produces summaries meaningfully better than simple truncation.

**Without Ollama:** CCE falls back to smart truncation — keeping the function signature and docstring, dropping the body. This still saves tokens but with less semantic preservation.

CCE detects Ollama automatically on `http://localhost:11434`. No configuration required.

---

## CLI Framework — Click

**What it does:** Powers the `cce` command-line interface.

Click is the standard Python CLI framework — well-documented, composable, and handles help text, argument parsing, and command groups cleanly. The `cce services` command group (start/stop/status for Ollama and Dashboard) uses Click's group nesting.

---

## Web Dashboard — FastAPI + uvicorn

**What it does:** Serves the `cce dashboard` web UI.

FastAPI gives a typed async API with automatic validation. uvicorn is the ASGI server. The dashboard polls `/api/stats`, `/api/files`, and `/api/sessions` every 5 seconds for live updates.

---

## Why Local-First

CCE stores everything on your machine:

- Embeddings and chunks: `~/.claude-context-engine/projects/<name>/vectors/`
- FTS index: `~/.claude-context-engine/projects/<name>/fts/`
- Graph: `~/.claude-context-engine/projects/<name>/graph/`
- Stats and decisions: `~/.claude-context-engine/projects/<name>/`

No data leaves your machine. No API keys. No cloud dependency. The MCP server starts in under a second because everything is local.
