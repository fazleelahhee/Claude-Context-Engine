<p align="center">
  <img src="docs/logo.svg" alt="Claude Context Engine" width="180">
</p>

<h1 align="center">Claude Context Engine</h1>

<p align="center">
  <strong>Index your codebase. Compress context. Cut token costs by 70%.</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/claude-context-engine/"><img src="https://img.shields.io/pypi/v/claude-context-engine?color=blue" alt="PyPI"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+"></a>
  <a href="https://modelcontextprotocol.io"><img src="https://img.shields.io/badge/MCP-compatible-green.svg" alt="MCP Compatible"></a>
  <a href="https://github.com/fazleelahhee/Claude-Context-Engine"><img src="https://img.shields.io/github/stars/fazleelahhee/Claude-Context-Engine?style=social" alt="GitHub stars"></a>
  <a href="https://github.com/fazleelahhee/Claude-Context-Engine/fork"><img src="https://img.shields.io/github/forks/fazleelahhee/Claude-Context-Engine?style=social" alt="GitHub forks"></a>
  <a href="https://github.com/fazleelahhee/Claude-Context-Engine/issues"><img src="https://img.shields.io/github/issues/fazleelahhee/Claude-Context-Engine" alt="GitHub issues"></a>
  <a href="https://github.com/fazleelahhee/Claude-Context-Engine/pulls"><img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="PRs Welcome"></a>
</p>

<p align="center">
  <code>pip install claude-context-engine</code>
</p>

---

A local context indexing system for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) that indexes your codebase, compresses context, and serves it via MCP — so Claude starts every session already knowing your project.

<p align="center">
  <img src="docs/demo.svg" alt="Claude Context Engine Demo" width="800">
</p>

## The Problem

Every time you start a new Claude Code session, Claude has no memory of your project. It re-reads files, re-discovers architecture, and burns tokens understanding code it has seen before. On large codebases, this startup cost adds up fast.

## How It Works

Claude Context Engine runs as a background daemon that:

1. **Indexes** your codebase using AST-aware chunking (tree-sitter) and semantic embeddings
2. **Stores** chunks in a vector database (LanceDB) with a knowledge graph (Kuzu) tracking relationships between functions, classes, and files
3. **Compresses** context using a local LLM (Ollama) or smart truncation, so Claude gets more information in fewer tokens
4. **Serves** the indexed context to Claude Code over MCP (Model Context Protocol), giving Claude instant access to search, graph traversal, and session history

```
Your Code
  │
  ▼
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│  Tree-sitter │───▶│   LanceDB    │───▶│  MCP Server │───▶ Claude Code
│  Chunker     │    │   + Kuzu     │    │  (stdio)    │
└─────────────┘    └──────────────┘    └─────────────┘
  │                                          ▲
  ▼                                          │
┌─────────────┐                    ┌─────────────────┐
│  Embedder   │                    │  Compressor      │
│  (MiniLM)   │                    │  (Ollama/trunc)  │
└─────────────┘                    └─────────────────┘
```

## Key Benefits

### Save Input Tokens (what Claude reads)
- Compressed summaries replace full file reads — Claude gets the same understanding in 60-80% fewer tokens
- Confidence scoring surfaces only the most relevant chunks, avoiding noise
- Progressive disclosure: Claude gets summaries first, expands to full code only when needed

### Save Output Tokens (what Claude writes) — Built-in Output Compression
- Integrated output compression reduces Claude's response verbosity by 65-75%
- Output tokens cost **5x more** than input tokens — this is where the biggest cost savings are
- Four levels: `off`, `lite`, `standard`, `max` — toggle mid-session via MCP tool
- Code blocks, file paths, commands, and error messages are never compressed
- Security warnings always use full clarity regardless of compression level

### Faster Session Startup
- No more "let me read through the codebase" at the start of every conversation
- The bootstrap context gives Claude an instant project overview: architecture, recent changes, key decisions
- Incremental indexing means only changed files get re-processed

### Persistent Project Memory
- Session history captures decisions, code areas explored, and questions asked
- Graph relationships track which functions call what, which files import which modules
- Past sessions are searchable — Claude can recall "why did we choose X over Y?"

### Works Locally, No Cloud Required
- All data stays on your machine (or your own remote server)
- Embeddings run locally via sentence-transformers
- Compression uses Ollama (local LLM) with smart truncation fallback
- Optional remote mode offloads heavy computation to a more powerful machine via SSH

## Installation

### Prerequisites

- Python 3.11+
- [CMake](https://cmake.org/) (for building Kuzu graph database)

```bash
# macOS
brew install cmake

# Ubuntu/Debian
sudo apt install cmake
```

### Install from PyPI (recommended)

```bash
pip install claude-context-engine
```

### Install from Source

```bash
git clone git@github.com:fazleelahhee/Claude-Context-Engine.git
cd Claude-Context-Engine
python -m venv .venv
source .venv/bin/activate
pip install -e .

# With dev dependencies (for running tests)
pip install -e ".[dev]"
```

### Optional: Install Ollama for LLM Compression

Without Ollama, the engine falls back to smart truncation (signature extraction + trimming). With Ollama, it produces higher-quality summaries.

```bash
# macOS
brew install ollama
ollama pull phi3:mini
```

## Quick Start

### 1. Initialize Your Project

```bash
cd /path/to/your/project
cce init
```

This will:
- Install git hooks for automatic re-indexing on commits
- Create a storage directory at `~/.claude-context-engine/projects/<project-name>/`
- Run the initial full index

### 2. Connect to Claude Code

Add the MCP server to your project's `.mcp.json`:

```json
{
  "mcpServers": {
    "context-engine": {
      "command": "/path/to/your/.venv/bin/cce",
      "args": ["serve"]
    }
  }
}
```

Restart Claude Code. The context engine tools will now be available.

### 3. Use It

Once connected, Claude Code automatically has access to these tools:

| Tool | What It Does |
|------|-------------|
| `context_search` | Semantic search across your indexed codebase |
| `expand_chunk` | Get the full source code for a compressed chunk |
| `related_context` | Find related code via graph relationships |
| `session_recall` | Recall past decisions and discussions |
| `index_status` | Check when the index was last updated |
| `reindex` | Trigger re-indexing of a file or the entire project |
| `set_output_compression` | Change output compression level mid-session (off/lite/standard/max) |

## Configuration

### Global Config

`~/.claude-context-engine/config.yaml`:

```yaml
remote:
  enabled: false
  host: "user@your-server"
  fallback_to_local: true

compression:
  level: standard        # minimal | standard | full (input compression)
  output: standard       # off | lite | standard | max (output compression)
  model: phi3:mini       # Ollama model for compression

embedding:
  model: all-MiniLM-L6-v2

retrieval:
  confidence_threshold: 0.5
  top_k: 20
  bootstrap_max_tokens: 10000

indexer:
  watch: true
  debounce_ms: 500
  ignore:
    - .git
    - node_modules
    - __pycache__
    - .venv
    - .env

storage:
  path: ~/.claude-context-engine/projects
```

### Per-Project Overrides

Create `.context-engine.yaml` in your project root to override any global setting:

```yaml
compression:
  level: full

indexer:
  ignore:
    - .git
    - node_modules
    - dist
    - coverage
```

### Resource Profiles

The engine auto-detects your machine's resources and adjusts accordingly:

| Profile | RAM | Behavior |
|---------|-----|----------|
| **light** | < 12 GB | Minimal compression, smaller embedding batches |
| **standard** | 12-32 GB | Full local pipeline |
| **full** | 32+ GB or remote | All features enabled, larger models |

## CLI Commands

The short command is `cce` (3 characters). The full `claude-context-engine` also works.

```bash
cce init              # Initialize project + first index
cce index             # Re-index project
cce index --full      # Force full re-index (ignore cache)
cce index --path src/ # Index specific directory
cce status            # Show index stats and config
cce serve             # Start MCP server (used by Claude Code)
cce serve-http        # Start HTTP API (for remote mode)
cce remote-setup      # Set up remote server
```

## Remote Mode

For machines with limited resources, you can offload the database and LLM compression to a remote server:

```yaml
# config.yaml
remote:
  enabled: true
  host: "user@your-server"
  fallback_to_local: true

compression:
  remote_model: llama3:8b  # Use a bigger model on the server
```

The engine will SSH into the remote, run queries there, and fall back to local if the server is unreachable.

## Performance Tips

- **Run `init` once per project** — subsequent indexing is incremental (only changed files)
- **Use `standard` compression** — it balances quality and speed. `minimal` is faster but loses more detail
- **Keep `indexer.watch: true`** — the file watcher auto-reindexes on save with debouncing
- **Git hooks handle the rest** — post-commit hooks trigger re-indexing automatically
- **Remote mode for laptops** — offload heavy computation to a server and keep your local machine responsive

## Supported Languages

AST-aware chunking (tree-sitter):
- Python
- JavaScript
- TypeScript (including JSX/TSX)

Fallback chunking (full-file):
- Markdown
- Any other text file with supported extensions

## How Token Compression Works

The engine uses a **3-layer compression pipeline** to minimize the tokens Claude needs to consume while preserving the information that matters.

### Layer 1: AST-Aware Chunking

Instead of feeding Claude raw files, tree-sitter parses your code into semantic chunks — individual functions, classes, and modules. This eliminates dead space (imports, blank lines, boilerplate) and creates meaningful, self-contained units.

```
Raw file (800 lines, ~12k tokens)
  → 15 function chunks + 3 class chunks
  → Only relevant chunks are retrieved, not the whole file
```

### Layer 2: LLM Summarization (Ollama)

When Ollama is available, each chunk is summarized by a local LLM using type-specific prompts:

| Chunk Type | Prompt Strategy | Example Output |
|-----------|----------------|----------------|
| **Function/Class** | Signature + purpose + inputs/outputs + side effects | `"process_payment(order, method): Validates payment method, charges via Stripe API, returns PaymentResult. Raises PaymentError on failure."` |
| **Architecture/Module** | Role in system + key dependencies | `"API gateway module — routes HTTP requests to service handlers, applies auth middleware and rate limiting."` |
| **Decision** | What + why + outcome | `"Chose PostgreSQL over MongoDB for user data. Reason: relational queries for billing. Outcome: migrated user schema."` |
| **Documentation** | Key info, no boilerplate | Strips headers, TOC, and filler — keeps actionable content. |

A **quality checker** verifies that at least 40% of key identifiers (function names, class names, parameters) survive compression. If the summary loses too much, it falls back to smart truncation.

### Layer 3: Smart Truncation (Fallback)

When Ollama is not available, or if LLM compression fails quality checks:

- **Functions/Classes**: Extracts signature + docstring, drops the body
- **Other chunks**: Truncates to character limits based on compression level

```python
# Original (45 lines, ~600 tokens)
def calculate_shipping(order, warehouse, method="standard"):
    """Calculate shipping cost based on order weight, warehouse location,
    and selected shipping method. Applies regional discounts."""
    total_weight = sum(item.weight * item.quantity for item in order.items)
    distance = haversine(warehouse.location, order.address)
    # ... 40 more lines of business logic ...

# Compressed (3 lines, ~50 tokens)
def calculate_shipping(order, warehouse, method="standard"):
    """Calculate shipping cost based on order weight, warehouse location,
    and selected shipping method. Applies regional discounts."""
```

### Compression Levels

Configure with `compression.level` in your config:

| Level | Char Limit | Behavior | Best For |
|-------|-----------|----------|----------|
| **minimal** | 100 chars | Truncation only, no LLM | Low-resource machines, fast indexing |
| **standard** | 300 chars | LLM when available, fallback to truncation | Most projects (default) |
| **full** | 800 chars | LLM compression; high-confidence chunks kept uncompressed | Large projects where detail matters |

### Output Compression (Built-in)

Output tokens cost **5x more** than input tokens on Claude. The engine includes built-in output compression that instructs Claude to respond concisely — no extra plugins needed.

| Level | Style | Savings | Example |
|-------|-------|---------|---------|
| **off** | Normal Claude responses | 0% | "I'll fix the bug in the authentication module. The issue is that the session token validation is not checking for expiration..." |
| **lite** | No filler, hedging, or pleasantries | ~30% | "Bug is in auth module. Session token validation doesn't check expiration..." |
| **standard** | Fragments, short synonyms, no articles | ~65% | "Bug in auth module. Session token validation missing expiration check..." |
| **max** | Telegraphic with abbreviations and symbols | ~75% | "auth bug → session token no expiry check..." |

Configure in `config.yaml`:
```yaml
compression:
  output: standard   # off | lite | standard | max
```

Or toggle mid-session — just ask Claude to call `set_output_compression`:
```
"Switch to max output compression"
"Turn off output compression"
```

Safety exceptions:
- Code blocks, file paths, commands, URLs, and error messages are **never** compressed
- Security warnings and destructive action confirmations always use **full clarity**

### Confidence-Based Retrieval

Not all chunks are equal. The engine scores every chunk using three signals:

| Signal | Weight | What It Measures |
|--------|--------|-----------------|
| **Vector similarity** | 50% | Semantic relevance to the query |
| **Graph distance** | 30% | How closely related via call/import graph |
| **Recency** | 20% | How recently the code was modified (1-week half-life) |

Only chunks above the confidence threshold (default: 0.5) are returned. High-confidence chunks get full detail; medium-confidence chunks get compressed summaries with a drill-down option.

## Token Savings: Before vs After

### Small Project (~50 files, ~5k lines)

| | Without Engine | With Engine | Savings |
|---|---------------|-------------|---------|
| Session startup | ~8k tokens (read 5-8 files) | ~2k tokens (bootstrap) | **75%** |
| Finding a function | ~3k tokens (read 2-3 files) | ~500 tokens (semantic search) | **83%** |
| Understanding architecture | ~15k tokens (read 10+ files) | ~3k tokens (graph + compressed) | **80%** |

### Medium Project (~500 files, ~50k lines)

| | Without Engine | With Engine | Savings |
|---|---------------|-------------|---------|
| Session startup | ~50k tokens (read 20-30 files) | ~10k tokens (bootstrap) | **80%** |
| Finding a function | ~8k tokens (grep + read files) | ~800 tokens (semantic search) | **90%** |
| Understanding architecture | ~60k tokens (read many files) | ~8k tokens (graph + compressed) | **87%** |
| Cross-session recall | ~20k tokens (re-read + re-discover) | ~1k tokens (session_recall) | **95%** |

### Large Project (~2000+ files, ~200k+ lines)

| | Without Engine | With Engine | Savings |
|---|---------------|-------------|---------|
| Session startup | ~100k+ tokens (often hits limits) | ~10k tokens (bootstrap, capped) | **90%+** |
| Finding a function | ~15k tokens | ~1k tokens | **93%** |
| Full investigation | ~150k+ tokens (may exceed context) | ~15k tokens (progressive disclosure) | **90%** |

### Where the Savings Come From

```
┌─────────────────────────────────────────────────────┐
│            Token Usage Without Engine                │
│                                                     │
│  ████████████████████  Full file reads (60%)        │
│  ██████████           Re-discovery each session(25%)│
│  █████               Irrelevant code in results(15%)│
│                                                     │
│  Total: ~50k tokens per session (medium project)    │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│            Token Usage With Engine                   │
│                                                     │
│  █████  Bootstrap context (40%)                     │
│  ████   Targeted chunk retrieval (35%)              │
│  ██     Graph traversal results (15%)               │
│  █      Session recall (10%)                        │
│                                                     │
│  Total: ~10k tokens per session (medium project)    │
└─────────────────────────────────────────────────────┘
```

### Progressive Disclosure in Action

The engine uses a **3-tier approach** to minimize upfront token cost:

1. **Bootstrap** (~10k tokens max) — Compressed project overview at session start. Covers architecture, recent commits, and active decisions.

2. **Search results** (~500-1k tokens per query) — Returns compressed summaries ranked by confidence. Claude sees what it needs without reading full files.

3. **Expand on demand** (~200-2k tokens per expansion) — When Claude needs the full source, it calls `expand_chunk` to get just that one function or class.

```
Session start:     "Here's your project overview"          → 10k tokens
Claude asks:       "Find the payment processing logic"     → 800 tokens
Claude drills in:  "Show me the full calculate_shipping"   → 600 tokens
                                                    Total: 11.4k tokens

Without engine:    Read payments.py + shipping.py + ...    → 45k tokens
```

### Combined Input + Output Savings

The engine compresses **both sides** of the conversation in a single plugin:

| Scenario (Opus 4) | Input Tokens | Output Tokens | Input Cost | Output Cost | **Total** |
|---|---|---|---|---|---|
| **No engine** | 50k | 20k | $0.75 | $1.50 | **$2.25** |
| **Input compression only** (output=off) | 10k | 20k | $0.15 | $1.50 | **$1.65** |
| **Output compression only** (standard) | 50k | 7k | $0.75 | $0.53 | **$1.28** |
| **Both** (default config) | 10k | 7k | $0.15 | $0.53 | **$0.68** |

**70% total cost reduction** with both compressions enabled — the default configuration.

## Comparison: Claude Context Engine vs Caveman

[Caveman](https://github.com/JuliusBrussee/caveman) is a popular output-compression plugin (36k+ stars). Here's how the two compare:

### Architecture

| | **Claude Context Engine** | **Caveman** |
|---|---|---|
| **Type** | Full context management system + MCP server | Prompt engineering plugin via hooks |
| **Language** | Python | JavaScript + Shell |
| **Storage** | LanceDB (vectors) + Kuzu (graph) + session history | Single flag file |
| **Infrastructure** | Daemon process with background indexing | Stateless — no persistent processes |
| **Integration** | MCP protocol (standard) | Claude Code hooks (SessionStart, UserPromptSubmit) |
| **Agent support** | Any MCP-compatible agent | Claude Code, Codex, Gemini CLI, Cursor, Copilot, 40+ agents |

### What Each Tool Compresses

| | **Claude Context Engine** | **Caveman** |
|---|---|---|
| **Input tokens** (what Claude reads) | Yes — AST chunking, vector search, LLM summarization, graph traversal | No |
| **Output tokens** (what Claude writes) | Yes — built-in output compression (4 levels) | Yes — this is its only focus |
| **Code in responses** | Never compressed | Never compressed |
| **Session memory** | Yes — persists decisions, code areas, Q&A across sessions | No |
| **Codebase indexing** | Yes — incremental, AST-aware | No |

### Output Compression Comparison

Both tools reduce Claude's response verbosity. Here's how the approaches differ:

| | **Context Engine** | **Caveman** |
|---|---|---|
| **Mechanism** | MCP prompt resource + tool response hints | System prompt injection via hooks |
| **Levels** | 4 (`off`, `lite`, `standard`, `max`) | 5 (`lite`, `full`, `ultra`, `wenyan` x3) |
| **Mid-session toggle** | Yes — via `set_output_compression` MCP tool | Yes — via `/caveman` slash command |
| **Output savings** | ~30-75% depending on level | ~22-87% depending on level |
| **Commit messages** | Not included | Yes — `caveman-commit` (<=50 char) |
| **PR reviews** | Not included | Yes — `caveman-review` (one-liners) |
| **File compression** | Compresses code semantically for retrieval | `caveman-compress` rewrites .md files in terse prose |
| **Safety exceptions** | Security warnings + destructive actions use full clarity | Security warnings + irreversible actions use full clarity |

### Token Savings Side-by-Side

Medium project session on **Claude Opus 4** ($15/1M input, $75/1M output):

| Scenario | Input | Output | Input Cost | Output Cost | **Total** | **Savings** |
|---|---|---|---|---|---|---|
| **No tool** | 50k | 20k | $0.75 | $1.50 | **$2.25** | — |
| **Caveman only** (full) | 50k | 7k | $0.75 | $0.53 | **$1.28** | 43% |
| **Context Engine** (input only, output=off) | 10k | 20k | $0.15 | $1.50 | **$1.65** | 27% |
| **Context Engine** (both, default) | 10k | 7k | $0.15 | $0.53 | **$0.68** | 70% |

### When to Use Which

| Use Case | Recommended |
|----------|------------|
| You just want cheaper responses, no setup | **Caveman** — install and go, zero config |
| You want full context management + cost savings | **Context Engine** — one plugin for both sides |
| Large codebase with repeated sessions | **Context Engine** — session memory + incremental indexing pay off over time |
| Multi-agent support (Cursor, Copilot, Gemini) | **Caveman** — supports 40+ agents out of the box |
| You need codebase search + graph traversal | **Context Engine** — Caveman doesn't index code |
| You want commit/PR review compression | **Caveman** — has dedicated skills for these |

### Key Difference

**Caveman** does one thing well: it makes Claude talk less. Zero infrastructure, zero storage, instant setup. It's a communication-style modifier.

**Context Engine** is a full context management system that also includes output compression. It indexes your codebase, builds a knowledge graph, compresses context semantically, persists session history, and reduces both input and output tokens. More setup, but deeper savings over time — especially on large projects with repeated sessions.

## Development

```bash
# Run tests
pytest

# Run tests with coverage
pytest --cov=context_engine

# Run a specific test
pytest tests/integration/test_end_to_end.py
```

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

1. Fork the repo
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'feat: add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Roadmap

- [ ] Tree-sitter support for Go, Rust, Java, C/C++
- [ ] Web dashboard for index inspection
- [ ] PyPI package publishing
- [ ] GitHub Actions CI pipeline
- [ ] Persistent session search across projects
- [ ] Smarter graph edge detection (call graph, import resolution)

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) by Anthropic
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io) for the integration standard
- [LanceDB](https://lancedb.com/) for vector storage
- [Kuzu](https://kuzudb.com/) for the graph database
- [Tree-sitter](https://tree-sitter.github.io/) for AST parsing
- [Ollama](https://ollama.com/) for local LLM compression

---

If this project helps you, give it a star! It helps others discover it.
