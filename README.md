<p align="center">
  <img src="https://raw.githubusercontent.com/fazleelahhee/Claude-Context-Engine/main/docs/logo.svg" alt="Claude Context Engine" width="160">
</p>

<h1 align="center">Claude Context Engine</h1>

<p align="center">
  <strong>Give Claude exactly the context it needs. Nothing more.</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/claude-context-engine/"><img src="https://img.shields.io/pypi/v/claude-context-engine?color=blue&label=PyPI" alt="PyPI"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+"></a>
  <a href="https://modelcontextprotocol.io"><img src="https://img.shields.io/badge/MCP-compatible-green.svg" alt="MCP Compatible"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="MIT License"></a>
  <a href="https://github.com/fazleelahhee/Claude-Context-Engine"><img src="https://img.shields.io/github/stars/fazleelahhee/Claude-Context-Engine?style=social" alt="Stars"></a>
</p>

<p align="center">
  Claude Context Engine (CCE) is a local-first context engine for Claude Code. It indexes your repository, breaks code into meaningful chunks, and retrieves only the most relevant context for each task, so Claude spends fewer tokens re-reading code it has already seen.
</p>

---

## The Problem

Every Claude Code session starts cold. Claude has no memory of your project. You either paste a lot of files to give it context (burns tokens fast) or paste too little and get weak answers.

Without CCE, every session looks like this:

- You open a new session and Claude knows nothing about your project
- You manually paste 3 to 4 files just to set the scene
- Claude re-reads the same files every session
- Large repos mean huge prompts, which are expensive and slow
- Decisions you made last week have to be re-explained today

**The token cost adds up fast:**

```
Without CCE:  paste payments.py + shipping.py = 45,000 tokens
With CCE:     search "payment processing"      =    800 tokens
```

Over 30 queries in a project, that gap compounds into real money.

## How CCE Fixes It

CCE builds a persistent, searchable index of your codebase and feeds Claude only the chunks it actually needs.

**Index once.** CCE splits your code into semantic chunks (functions, classes, modules) and stores them as vector embeddings locally. Git hooks keep the index current after every commit.

**Retrieve exactly what is relevant.** When Claude needs to find `calculate_shipping`, it searches the index and gets back 600 tokens instead of an entire 800-line file.

**Remember across sessions.** Architectural decisions, which files you touched, why you made a choice — stored and recalled automatically. No re-explaining.

```text
Session start:      Project overview               ->  10k tokens
Search:             "Find payment processing"      ->   800 tokens
Drill-down:         "Show full calculate_shipping" ->   600 tokens
                                                    --------
                                                    11.4k tokens

Without CCE:        Read payments.py + shipping.py ->  45k tokens
```

## Overview

| Problem | Without CCE | With CCE |
|---------|-------------|----------|
| Session startup | Claude re-reads files and project structure | Claude queries the index |
| Finding a function | Large prompt or manual file sharing | Targeted semantic retrieval |
| Token usage | High and repetitive | Focused and efficient |
| Cross-session memory | None by default | Decisions and code areas persisted |
| Repeated explanations | Re-explain the repo every session | Ask once, retrieve always |

---

## Quick Start

### 1. Install

```bash
brew tap fazleelahhee/tap && brew install claude-context-engine  # macOS (recommended)
# or
uv tool install claude-context-engine                             # all platforms (recommended)
# or
pipx install claude-context-engine                                # all platforms
# or
pip install claude-context-engine                                 # inside a virtualenv
```

### 2. Index your project

```bash
cd /path/to/your/project
cce init
```

`cce init` handles everything in one step: indexes your codebase, installs git hooks to keep the index current, and writes the MCP server entry to `.mcp.json`.

### 3. Restart Claude Code

Once restarted, Claude can call `context_search` to retrieve relevant code instead of reading files from scratch every session.

---

## Web Dashboard

CCE includes a local web dashboard for inspecting your index, viewing token savings, and managing indexed files.

```bash
cce dashboard
```

The dashboard opens automatically in your browser. Use `--no-browser` to suppress that behavior, or `--port` to specify a port.

![CCE Dashboard](https://raw.githubusercontent.com/fazleelahhee/Claude-Context-Engine/main/docs/dashboard.png)

The dashboard provides four views:

**Overview.** Four stat cards (chunks indexed, files indexed, queries run, tokens saved) plus a 2x2 chart grid: token savings donut, file health donut, top files by chunk count, and session decision activity. Live-updating every 5 seconds.

**Files.** Full list of indexed files with staleness detection. Files are marked `ok`, `stale` (modified since last index), or `missing` (deleted). Per-file reindex and removal available inline.

**Sessions.** Architectural decisions and code areas captured during Claude coding sessions, organized by session with expandable detail.

**Savings.** Token usage breakdown with a donut chart and stacked progress bar showing how many tokens CCE saved versus the raw file baseline. Output compression controls on the same page.

---

## Token Savings

Run `cce savings` for a quick terminal report:

```text
$ cce savings

     my-project · 38 queries
     14.2k / 48.0k tokens used (30%)

     Token savings
     With CCE:     14,200 tokens  (30%)
     Tokens saved: 33,800 tokens  (70%)
```

Savings grow over time. On the first query, CCE retrieves a small slice of your codebase. On subsequent queries, it retrieves different slices. The alternative is pasting entire files every time.

Exact savings depend on project size, query patterns, and compression settings.

---

## How It Works

### 1. Code Indexing

CCE walks your repository, hashes each file, and builds a LanceDB vector index. Git hooks keep the index current after each commit.

### 2. Semantic Chunking

Instead of treating files as flat text, CCE splits code into meaningful units: functions, classes, and modules. Each chunk is embedded independently.

```text
Raw file (800 lines, ~12k tokens)
  -> 15 function chunks + 3 class chunks
  -> Only relevant chunks retrieved, not the whole file
```

### 3. Compression

CCE can reduce context size in two ways. With Ollama running locally, it uses LLM-based summarization. Without Ollama, it falls back to smart truncation using function signatures and docstrings.

```python
# Original
def calculate_shipping(order, warehouse, method="standard"):
    """Calculate shipping cost based on order weight and location."""
    total_weight = sum(item.weight * item.quantity for item in order.items)
    # ... 40 more lines

# Compressed (truncation fallback)
def calculate_shipping(order, warehouse, method="standard"):
    """Calculate shipping cost based on order weight and location."""
```

### 4. Retrieval Ranking

Retrieved chunks are ranked by a combination of vector similarity, keyword match, and recency. Only chunks above the confidence threshold are returned.

### 5. Graph-Aware Expansion

After the primary vector search, CCE walks the code graph one hop: if your result is in `auth.py`, it also fetches relevant chunks from files that `auth.py` calls or imports. This surfaces related context without requiring a second query.

```text
Query: "validate user token"
Primary result: auth.py:validate_token (vector match)
Graph hop:      utils.py:decode_jwt  (auth.py CALLS utils.py)
                db.py:fetch_user     (auth.py CALLS db.py)
```

### 6. Overflow References

When search results exceed the token budget, CCE lists the remainder as compact references instead of silently dropping them. Claude sees what exists and can fetch individual chunks on demand.

```text
2 more result(s) available (not shown to save tokens):
  expand_chunk(chunk_id="abc123")  → payments.py:45 (confidence: 0.82)
  expand_chunk(chunk_id="def456")  → orders.py:112  (confidence: 0.71)
```

### 7. Progressive Disclosure

CCE starts with a project overview and expands only when Claude needs more detail. Each search retrieves a small, focused slice rather than loading entire files.

---

## CLI Commands

### Setup

```bash
# Initialize CCE in a project — indexes code, installs git hooks, writes .mcp.json
cd /path/to/your/project
cce init

# Re-index files changed since last commit
cce index

# Force a full re-index of every file
cce index --full

# Index a specific file or directory only
cce index --path src/payments/
```

### Status and Savings

```bash
# Show index health, chunk count, and token savings summary
cce status

# Token savings report for the current project
cce savings

# Savings across every indexed project
cce savings --all

# Machine-readable JSON output
cce savings --json
```

### Index Management

```bash
# Clear all index data and reset stats for the current project
cce clear

# Skip the confirmation prompt
cce clear --yes

# Remove stored index data for projects whose directories no longer exist
cce prune

# Preview what prune would remove without deleting anything
cce prune --dry-run
```

### Dashboard

```bash
# Open the web dashboard in your browser
cce dashboard

# Open on a specific port
cce dashboard --port 8080

# Start the server without opening a browser (run in background)
cce dashboard --no-browser
```

### Services

The `services` command manages Ollama and the Dashboard as background processes so you do not need to leave a terminal blocked.

```bash
# Show status of all services
cce services

# Example output:
# SERVICE     STATUS    DETAIL
# ------------------------------------------------
# ollama      running   localhost:11434 (external)
# dashboard   stopped
# mcp         running   managed by Claude Code

# Start all services
cce services start

# Start only Ollama
cce services start ollama

# Start dashboard on the default port (8080)
cce services start dashboard

# Start dashboard on a custom port
cce services start dashboard --port 9000

# Stop all services started by CCE
cce services stop

# Stop only the dashboard
cce services stop dashboard
```

### MCP Server

```bash
# Start the MCP server — Claude Code calls this automatically via .mcp.json
cce serve
```

---

## MCP Tools

Once connected, Claude gets these tools automatically:

| Tool | Description |
|------|-------------|
| `context_search` | Semantic search across your indexed codebase |
| `expand_chunk` | Get full source for a compressed chunk |
| `session_recall` | Recall past decisions and code-area notes |
| `record_decision` | Save an architectural decision for future sessions |
| `record_code_area` | Record a file and a description of work done |
| `index_status` | Check index status and token savings stats |
| `reindex` | Trigger re-indexing of a file or the full project |
| `set_output_compression` | Adjust response verbosity: `off`, `lite`, `standard`, `max` |

---

## Output Compression

CCE includes built-in output compression to reduce the tokens Claude uses in its responses.

| Level | Style | Typical savings |
|-------|-------|-----------------|
| `off` | Full Claude output | 0% |
| `lite` | No filler or hedging | ~30% |
| `standard` | Shorter phrasing and fragments | ~65% |
| `max` | Telegraphic style | ~75% |

To change the level, tell Claude directly:

```text
Switch to max output compression
Turn off output compression
```

Code blocks, file paths, commands, and error messages are never compressed. Security warnings always use full verbosity.

---

## Configuration

CCE works with zero configuration. The following options are available when you need them.

### Global configuration

File: `~/.claude-context-engine/config.yaml`

```yaml
compression:
  level: standard        # minimal | standard | full (input compression)
  output: standard       # off | lite | standard | max (output compression)
  model: phi3:mini       # Ollama model (auto-detected if Ollama is running)

indexer:
  watch: true
  ignore: [.git, node_modules, __pycache__, .venv]

retrieval:
  top_k: 20
  confidence_threshold: 0.5
```

### Per-project configuration

File: `.context-engine.yaml` in your project root

```yaml
compression:
  level: full

indexer:
  ignore: [.git, node_modules, dist, coverage]
```

### Project commands, rules & preferences

Tell Claude how to work in each project. Stored in `.cce/commands.yaml`:

```bash
cce commands add-rule 'Never generate down() in migrations'
cce commands set-pref database PostgreSQL
cce commands add before_push 'composer test'
cce commands add-custom deploy 'kubectl apply -f k8s/'
```

Claude sees these at every session start and follows them automatically. Supports workspace-level configs for multi-project directories — see [Project Commands wiki](docs/wiki/Project-Commands.md) for details.

### Resource profiles

CCE auto-detects available memory and adjusts its behavior:

| RAM | Profile | Behavior |
|-----|---------|----------|
| Less than 12 GB | light | Truncation only, small batches |
| 12 to 32 GB | standard | Full pipeline |
| More than 32 GB | full | Larger models, all features enabled |

---

## Optional Ollama Support

Without Ollama, CCE uses smart truncation for compression. With Ollama running locally, it uses higher-quality LLM-based summaries automatically.

```bash
brew install ollama
ollama pull phi3:mini
ollama serve
```

No configuration required. CCE detects Ollama automatically.

---

## Supported Languages

### AST-aware chunking

| Language | Extension |
|----------|-----------|
| Python | `.py` |
| JavaScript | `.js` |
| TypeScript | `.ts` |
| JSX | `.jsx` |
| TSX | `.tsx` |
| PHP | `.php` |

### Fallback chunking

Markdown and other text-based files are supported with line-based chunking. Go, Rust, Java, C, and C++ are planned.

---

## Use Cases

- Onboarding to an unfamiliar codebase quickly
- Locating related logic scattered across multiple files
- Reducing prompt size for large repositories
- Maintaining architectural decisions across repeated sessions
- Improving first-pass answer quality from Claude Code

---

## Roadmap

- [x] Semantic code indexing and retrieval
- [x] Output compression levels
- [x] Cross-session memory (decisions, code areas)
- [x] Web dashboard with charts (`cce dashboard`)
- [x] Token savings tracking and reporting
- [x] Non-git project support
- [x] Index management (`cce clear`, `cce prune`)
- [x] Service management (`cce services`)
- [x] Graph-aware 1-hop retrieval expansion
- [x] Overflow result references in `context_search`
- [x] Output terseness rules in generated `CLAUDE.md`
- [ ] Tree-sitter support for Go, Rust, Java, C, and C++
- [ ] Persistent session search across projects
- [ ] Docker support for remote mode
- [ ] Retrieval quality benchmarks on real repositories

---

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for setup instructions.

To use CCE in your own projects, `pip install claude-context-engine` is all you need. Development dependencies only matter if you want to work on CCE itself.

Browse [good first issues](https://github.com/fazleelahhee/Claude-Context-Engine/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) if you are looking for a place to start.

---

## License

MIT. See [LICENSE](LICENSE).

## Acknowledgments

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code)
- [MCP](https://modelcontextprotocol.io)
- [LanceDB](https://lancedb.com/)
- [Tree-sitter](https://tree-sitter.github.io/)
- [Ollama](https://ollama.com/)

If CCE saves you tokens, give it a star.
