# Claude Context Engine

<p align="center">
  <img src="docs/logo.svg" alt="Claude Context Engine" width="160">
</p>

**Make Claude understand your codebase without wasting tokens.**

Claude Context Engine is a local-first context engine for Claude Code. It indexes your repository, breaks code into meaningful chunks, and retrieves only the most relevant context for each task.

The goal is simple: give Claude the minimum correct context needed to produce a better answer.

[![PyPI](https://img.shields.io/pypi/v/claude-context-engine?color=blue&label=PyPI)](https://pypi.org/project/claude-context-engine/)
![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)
![MCP Compatible](https://img.shields.io/badge/MCP-compatible-green.svg)
![MIT License](https://img.shields.io/badge/License-MIT-yellow.svg)
[![GitHub stars](https://img.shields.io/github/stars/fazleelahhee/Claude-Context-Engine?style=social)](https://github.com/fazleelahhee/Claude-Context-Engine)

## Overview

Claude Context Engine helps developers avoid three common problems:

- pasting too much code and wasting tokens
- pasting too little and getting weak answers
- repeatedly explaining the same repository structure

Instead of forcing Claude to re-read files every session, CCE indexes your repository and retrieves targeted context only when needed.

## Key Benefits

- Lower token usage through targeted context retrieval
- Better first-pass answers from Claude Code
- Less manual context sharing and prompt repetition
- Local-first workflow with optional remote server mode
- Semantic indexing designed for real repositories, not generic demos

## Quick Start

### 1. Install

```bash
brew tap fazleelahhee/tap && brew install claude-context-engine  # macOS
# or
pip install claude-context-engine                                 # all platforms
```

### 2. Index Your Project

```bash
cd /path/to/your/project
cce init
```

`cce init` handles the initial setup automatically:

- indexes your codebase
- installs git hooks
- writes the MCP config to `.mcp.json`

### 3. Restart Claude Code

Once restarted, Claude can search your indexed codebase instead of re-reading files every session.

## Before and After

| | Without CCE | With CCE |
|---|---|---|
| Session startup | Claude re-reads files and project structure | Claude uses indexed context |
| Finding a function | Large prompt or manual file sharing | Targeted retrieval |
| Token usage | High and repetitive | Smaller and more focused |
| Cross-session memory | None by default | Supported |
| Workflow | Re-explain the repo repeatedly | Ask directly and retrieve context |

Claude Context Engine is designed to reduce prompt bloat while improving the quality of context Claude receives.

## Token Savings

Run `cce savings` to see how much context CCE is saving:

```text
$ cce savings

     my-project · 38 queries
     14.2k / 48.0k tokens used (30%)

     Token savings
     With CCE:     14,200 tokens (30%)
     Tokens saved: 33,800 tokens (70%)
```

Savings grow over time because Claude receives only what it needs, not entire files or repeated context dumps.

Exact savings depend on project size, query pattern, and compression settings, but the objective remains consistent: better context with fewer tokens.

## How It Works

### 1. Code Indexing

CCE indexes your repository and builds a searchable representation of the codebase.

### 2. Semantic Chunking

Instead of treating files as flat text, CCE splits code into meaningful units such as functions, classes, and modules.

```text
Raw file (800 lines, ~12k tokens)
  -> 15 function chunks + 3 class chunks
  -> Only relevant chunks retrieved, not the whole file
```

### 3. Compression

CCE can reduce context size in two ways:

- optional LLM-based summarization through Ollama
- smart truncation fallback using signatures and docstrings

Example:

```python
# Original
def calculate_shipping(order, warehouse, method="standard"):
    """Calculate shipping cost based on order weight and location."""
    total_weight = sum(item.weight * item.quantity for item in order.items)
    # ...

# Compressed
def calculate_shipping(order, warehouse, method="standard"):
    """Calculate shipping cost based on order weight and location."""
```

### 4. Retrieval Ranking

Chunks are ranked using a combination of:

- vector similarity
- keyword match
- recency

Only context above the confidence threshold is returned.

### 5. Progressive Disclosure

CCE helps Claude start small and expand only when needed.

```text
Session start:      Project overview               ->  10k tokens
Search:             "Find payment processing"      ->   800 tokens
Drill-down:         "Show full calculate_shipping" ->   600 tokens
                                                    -------
                                                    11.4k tokens

Without engine:     Read payments.py + shipping.py ->  45k tokens
```

## Features

- Semantic code indexing for repositories
- Relevant code retrieval by developer intent
- Optional context compression
- Cross-session memory support
- Local-first design
- Optional remote server mode
- MCP integration for Claude Code

## CLI Commands

| Command | Description |
|---------|-------------|
| `cce init` | One-time setup: index, git hooks, MCP config |
| `cce index` | Re-index changed files |
| `cce index --full` | Force a full re-index |
| `cce status` | Index config and token savings summary |
| `cce savings` | Visual savings report |
| `cce savings --all` | Savings across all indexed projects |
| `cce savings --json` | Machine-readable savings output |
| `cce serve` | Start MCP server |

## MCP Tools in Claude Code

Once connected, Claude gets these tools automatically:

| Tool | Description |
|------|-------------|
| `context_search` | Semantic search across your indexed codebase |
| `expand_chunk` | Get full source for a compressed chunk |
| `session_recall` | Recall past decisions and code-area notes |
| `record_decision` | Record a decision for future recall |
| `record_code_area` | Record a file and description of work done |
| `index_status` | Check index status and token savings stats |
| `reindex` | Trigger re-indexing of a file or full project |
| `set_output_compression` | Adjust response verbosity: `off`, `lite`, `standard`, `max` |

## Output Compression Levels

Output tokens can be expensive. CCE includes built-in output compression:

| Level | Style | Savings |
|-------|-------|---------|
| `off` | Normal Claude output | 0% |
| `lite` | No filler or hedging | ~30% |
| `standard` | Shorter phrasing and fragments | ~65% |
| `max` | Telegraphic style | ~75% |

Examples:

```text
Switch to max output compression
Turn off output compression
```

Code blocks, file paths, commands, and error messages are never compressed. Security warnings always use full clarity.

## Configuration

CCE works with zero config, but you can customize it.

### Global Configuration

File: `~/.claude-context-engine/config.yaml`

```yaml
compression:
  level: standard        # minimal | standard | full (input)
  output: standard       # off | lite | standard | max (output)
  model: phi3:mini       # Ollama model (auto-detected if running)

indexer:
  watch: true
  ignore: [.git, node_modules, __pycache__, .venv]

retrieval:
  top_k: 20
  confidence_threshold: 0.5
```

### Per-Project Configuration

File: `.context-engine.yaml`

```yaml
compression:
  level: full

indexer:
  ignore: [.git, node_modules, dist, coverage]
```

### Resource Profiles

The engine can auto-detect machine resources:

| RAM | Profile | Behavior |
|-----|---------|----------|
| < 12 GB | light | Truncation only, small batches |
| 12-32 GB | standard | Full pipeline |
| 32+ GB | full | Larger models, all features |

## Optional Ollama Support

Without Ollama, the engine uses smart truncation.

With Ollama running locally, CCE can use higher-quality summaries automatically.

```bash
brew install ollama
ollama pull phi3:mini
ollama serve
```

No extra configuration is required.

## Supported Languages

### AST-Aware Chunking

- Python
- JavaScript
- TypeScript
- JSX
- TSX
- PHP

### Fallback Chunking

- Markdown
- other text-based files

Additional language support such as Go, Rust, and Java is planned.

## Use Cases

- understanding unfamiliar codebases
- locating related logic across multiple files
- reducing prompt size for large repositories
- improving Claude Code workflows
- maintaining context across repeated sessions

## Roadmap

- Tree-sitter support for Go, Rust, Java, C, and C++
- Web dashboard for index inspection
- Persistent session search across projects
- Docker support for remote mode
- More retrieval-quality benchmarks on real repositories

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for setup instructions.

If you only want to use CCE in your own projects, `pip install claude-context-engine` is enough.

Development dependencies and local setup only matter if you want to work on CCE itself.

You can also browse the [good first issues](https://github.com/fazleelahhee/Claude-Context-Engine/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22).

## License

MIT. See [LICENSE](LICENSE).

## Acknowledgments

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code)
- [MCP](https://modelcontextprotocol.io)
- [LanceDB](https://lancedb.com/)
- [Tree-sitter](https://tree-sitter.github.io/)
- [Ollama](https://ollama.com/)

If CCE saves you tokens, give it a star. It helps more developers find it.
