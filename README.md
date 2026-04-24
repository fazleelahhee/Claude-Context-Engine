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
  Claude Context Engine (CCE) is a local-first context engine for Claude Code. It indexes your repository, breaks code into meaningful chunks, and retrieves only the most relevant context for each task — so Claude spends fewer tokens re-reading code it has already seen.
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
uv tool install claude-context-engine   # recommended — isolated, no virtualenv needed
# or
pipx install claude-context-engine
# or
pip install claude-context-engine       # inside a virtualenv
```

### 2. Index your project

```bash
cd /path/to/your/project
cce init
```

`cce init` handles everything in one step:

```
  Claude Context Engine  ·  my-project
  ────────────────────────────────────────────

  Checking embedding model... downloading if needed (60 MB, first time only)... ready.
  Ollama not running — using truncation compression.
  Tip: ollama pull phi3:mini for LLM summarization

  ✓ Git hooks installed  (3 hooks, auto-updates on commit)
  ✓ MCP server registered in .mcp.json
  ✓ CLAUDE.md created with CCE instructions
  ✓ .gitignore updated with CCE entries

  Indexing project...
    ██████████████████████████████  89/89 files  100%

  ✓ Indexed 1,247 chunks from 89 files

  Done!  Restart Claude Code to activate CCE.
```

### 3. Restart Claude Code

Once restarted, Claude can call `context_search` and seven other MCP tools automatically — no setup needed per session.

---

## Documentation

Full documentation is available on the [GitHub Wiki](https://github.com/fazleelahhee/Claude-Context-Engine/wiki):

| Page | What it covers |
|------|---------------|
| [Examples](https://github.com/fazleelahhee/Claude-Context-Engine/wiki/Examples) | Real conversations — what you type, what Claude does |
| [CCE In Practice](https://github.com/fazleelahhee/Claude-Context-Engine/wiki/CCE-In-Practice) | Token counts and internals for each scenario |
| [How It Works](https://github.com/fazleelahhee/Claude-Context-Engine/wiki/How-It-Works) | Full 9-stage pipeline: indexing, retrieval, compression |
| [CLI Reference](https://github.com/fazleelahhee/Claude-Context-Engine/wiki/CLI-Reference) | Every command with expected output |
| [Tech Stack](https://github.com/fazleelahhee/Claude-Context-Engine/wiki/Tech-Stack) | Every library: what it does, where it's used, why chosen |
| [Configuration](https://github.com/fazleelahhee/Claude-Context-Engine/wiki/Configuration) | All config options, global and per-project |

---

## Disk Footprint

CCE is designed to run on a standard developer laptop without special hardware.

### Installed package

| Component | Size | Notes |
|-----------|------|-------|
| CCE source | ~500 KB | The package itself |
| LanceDB | ~98 MB | Embedded vector database |
| ONNX Runtime | ~66 MB | Inference engine for the embedding model |
| fastembed | ~1 MB | Thin wrapper around ONNX Runtime |
| Other dependencies | ~285 MB | click, fastapi, tree-sitter, mcp, httpx, etc. |
| **Total installed** | **~450 MB** | One-time, in your uv/pipx tool environment |

### Embedding model

Downloaded once on first `cce init`, stored in the fastembed cache:

| Model | Size |
|-------|------|
| `BAAI/bge-small-en-v1.5` (default) | ~60 MB |

### Index per project

Stored in `~/.claude-context-engine/projects/<name>/`. Size depends on project scale:

| Project scale | Approximate index size |
|---------------|----------------------|
| Small (under 50 files) | 5 to 15 MB |
| Medium (50 to 200 files) | 15 to 60 MB |
| Large (200 to 1,000 files) | 60 to 250 MB |

The CCE repository itself (134 files, 1,847 chunks) produces a 55 MB index.

### No GPU required

The embedding model runs via ONNX Runtime on CPU. A standard laptop CPU embeds a full project in seconds.

---

## Web Dashboard

```bash
cce dashboard
```

The dashboard opens in your browser. It provides four views:

**Overview.** Chunks indexed, files indexed, queries run, tokens saved — plus live charts updating every 5 seconds.

**Files.** Full file list with staleness detection: `ok`, `stale` (modified since last index), or `missing` (deleted).

**Sessions.** Past architectural decisions and code areas from Claude sessions, organized with expandable detail.

**Savings.** Token usage breakdown with compression controls.

```bash
cce dashboard --port 8080      # custom port
cce dashboard --no-browser     # server only, no browser open
```

![CCE Dashboard](https://raw.githubusercontent.com/fazleelahhee/Claude-Context-Engine/main/docs/dashboard.png)

---

## Token Savings

```bash
cce savings
```

```
     ⛁ ⛁ ⛁ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶   my-project · 38 queries
     ⛁ ⛁ ⛁ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶   14.2k / 48.0k tokens used (30%)
     ⛁ ⛁ ⛁ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶
     ⛁ ⛁ ⛁ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶   Token savings
     ⛁ ⛁ ⛁ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶   ⛁ With CCE:     14,200 tokens  (30%)
     ⛁ ⛁ ⛁ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶   ⛶ Tokens saved:  33,800 tokens  (70%)
```

Savings grow over time. Each query retrieves a targeted slice rather than an entire file. The alternative is pasting entire files on every session.

---

## How It Works

### 1. Indexing

CCE walks your repository, hashes each file, and builds three stores: a LanceDB vector index, a SQLite FTS5 full-text index, and a SQLite code graph. Git hooks keep all three current on every commit.

### 2. Semantic Chunking

Tree-sitter parses each file into its actual structure — functions, classes, imports — so each chunk has a single responsibility.

```text
payments.py  (800 lines, ~12k tokens)
  -> calculate_shipping()    chunk  lines 45–90     (640 tokens)
  -> validate_address()      chunk  lines 92–130    (480 tokens)
  -> ShippingMethod          class  lines 132–200   (820 tokens)
```

### 3. Hybrid Retrieval

Every `context_search` runs vector search (semantic similarity via LanceDB) and BM25 keyword search (via SQLite FTS5) in parallel. Results are merged with Reciprocal Rank Fusion so exact-match identifiers rank as well as semantic concepts.

### 4. Graph-Aware Expansion

After primary retrieval, CCE walks the code graph one hop. If the top result is `auth.py:validate_token`, CCE also fetches relevant chunks from files `auth.py` calls or imports.

```text
Query:          "validate user token"
Primary:        auth.py:validate_token      (confidence: 0.91)
Graph expansion: utils.py:decode_jwt        (auth.py CALLS utils.py)
                 db.py:fetch_user_by_id     (auth.py CALLS db.py)
```

### 5. Overflow References

When results exceed the token budget, CCE lists the rest as compact references rather than silently dropping them.

```text
2 more result(s) available (not shown to save tokens):
  expand_chunk(chunk_id="abc123")  → payments.py:45 (confidence: 0.82)
  expand_chunk(chunk_id="def456")  → orders.py:112  (confidence: 0.71)
```

### 6. Compression

Without Ollama: CCE truncates to function signature and docstring.
With Ollama running locally: CCE uses `phi3:mini` for higher-quality LLM summaries. Detected automatically, no configuration needed.

### 7. Cross-Session Memory

When Claude records a decision (`record_decision`) or a code area (`record_code_area`), CCE stores it in SQLite. `session_recall` surfaces it at the start of the next session — no re-explaining.

---

## CLI Commands

### Setup

```bash
cce init                           # index project, install git hooks, write .mcp.json
cce index                          # re-index changed files
cce index --full                   # force full re-index
cce index --path src/payments/     # index one file or directory
```

### Status and Savings

```bash
cce status                         # index health and token savings
cce savings                        # token savings report
cce savings --all                  # savings across every indexed project
cce savings --json                 # machine-readable output
```

### Index Management

```bash
cce clear                          # clear index data (asks for confirmation)
cce clear --yes                    # skip confirmation
cce prune                          # remove data for deleted projects
cce prune --dry-run                # preview without deleting
```

### Services

```bash
cce services                       # show status of Ollama, dashboard, MCP

cce services start                 # start Ollama + dashboard
cce services start ollama          # start only Ollama
cce services start dashboard       # start dashboard on default port (8080)
cce services start dashboard --port 9000

cce services stop                  # stop everything CCE started
cce services stop dashboard        # stop only dashboard
cce services stop ollama           # stop only Ollama
```

Service status example:

```
  SERVICE       STATUS      DETAIL
  ──────────────────────────────────────────────────
  ollama        running     localhost:11434 (external)
  dashboard     stopped
  mcp           running     managed by Claude Code
```

### Dashboard

```bash
cce dashboard                      # open in browser
cce dashboard --port 8080
cce dashboard --no-browser
```

---

## MCP Tools

Once connected, Claude has these tools available automatically:

| Tool | What it does |
|------|-------------|
| `context_search` | Hybrid vector + BM25 search with graph expansion |
| `expand_chunk` | Get full source for a compressed or overflow chunk |
| `session_recall` | Recall past architectural decisions |
| `record_decision` | Save a decision for future sessions |
| `record_code_area` | Record which files were worked in and why |
| `index_status` | Check index health and token savings |
| `reindex` | Trigger re-indexing of a file or the full project |
| `set_output_compression` | Adjust response verbosity: `off`, `lite`, `standard`, `max` |

---

## Output Compression

CCE compresses Claude's own responses to reduce output tokens.

| Level | Style | Typical savings |
|-------|-------|-----------------|
| `off` | Full Claude output | 0% |
| `lite` | No filler or hedging | ~30% |
| `standard` | Shorter phrasing and fragments | ~65% |
| `max` | Telegraphic style | ~75% |

Change at any time by telling Claude:

```
Switch to max output compression
Turn off output compression
```

Code blocks, file paths, commands, and error messages are never compressed.

---

## Configuration

CCE works with zero configuration. Override what you need.

**Global config** — `~/.claude-context-engine/config.yaml`:

```yaml
compression:
  level: standard        # minimal | standard | full
  output: standard       # off | lite | standard | max
  model: phi3:mini       # Ollama model (auto-detected)

indexer:
  watch: true
  ignore: [.git, node_modules, __pycache__, .venv]

retrieval:
  top_k: 20
  confidence_threshold: 0.5

embedding:
  model: BAAI/bge-small-en-v1.5
```

**Per-project config** — `.context-engine.yaml` in your project root:

```yaml
compression:
  level: full

indexer:
  ignore: [.git, node_modules, dist, coverage, "*.generated.ts"]
```

### Project commands, rules & preferences

Tell Claude how to work in each project. Stored in `.cce/commands.yaml`:

```bash
cce commands add-rule 'Never generate down() in migrations'
cce commands set-pref database PostgreSQL
cce commands add before_push 'composer test'
cce commands add-custom deploy 'kubectl apply -f k8s/'
```

Claude sees these at every session start and follows them automatically. Supports workspace-level configs for multi-project directories. See the [Project Commands wiki](https://github.com/fazleelahhee/Claude-Context-Engine/wiki/Project-Commands) for details.
---

## Optional Ollama Support

Without Ollama, CCE uses smart truncation. With Ollama, it uses LLM-based summarization automatically — `cce init` tells you which mode is active.

```bash
brew install ollama
ollama pull phi3:mini
ollama serve
```

`cce init` detects Ollama and reports its status during setup. No other configuration required.

---

## Supported Languages

### AST-aware chunking

| Language | Extensions |
|----------|-----------|
| Python | `.py` |
| JavaScript | `.js`, `.jsx` |
| TypeScript | `.ts`, `.tsx` |
| PHP | `.php` |

### Fallback chunking

All other text-based files (Markdown, YAML, config files, etc.) are chunked by line range. Go, Rust, Java, and C are planned.

---

## Roadmap

- [x] Semantic code indexing and retrieval
- [x] Output compression levels (`off` / `lite` / `standard` / `max`)
- [x] Cross-session memory (decisions, code areas)
- [x] Web dashboard with live charts (`cce dashboard`)
- [x] Token savings tracking and reporting (`cce savings`)
- [x] Non-git project support
- [x] Index management (`cce clear`, `cce prune`)
- [x] Service management (`cce services` — Ollama + dashboard background processes)
- [x] Graph-aware 1-hop retrieval expansion via CALLS/IMPORTS edges
- [x] Overflow result references in `context_search`
- [x] Output terseness rules in generated `CLAUDE.md`
- [x] Pre-flight check in `cce init` (embedding model warmup + Ollama hint)
- [x] Comprehensive `.gitignore` for CCE-generated per-machine files
- [ ] Tree-sitter support for Go, Rust, Java, C, and C++
- [ ] Persistent session search across projects
- [ ] Docker support for remote mode
- [ ] Retrieval quality benchmarks on real repositories

---

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for setup instructions.

Browse [good first issues](https://github.com/fazleelahhee/Claude-Context-Engine/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) if you are looking for a place to start.

---

## License

MIT. See [LICENSE](LICENSE).

## Authors

- [Fazle Elahee](https://github.com/fazleelahhee)
- [Raj](https://github.com/rajkumarsakthivel)

## Acknowledgments

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code)
- [MCP](https://modelcontextprotocol.io)
- [LanceDB](https://lancedb.com/)
- [Tree-sitter](https://tree-sitter.github.io/)
- [fastembed](https://github.com/qdrant/fastembed)
- [Ollama](https://ollama.com/)

If CCE saves you tokens, give it a star.
