# CLI Reference

Complete reference for every `cce` command with examples and expected output.

---

## cce init

One-time setup for a project. Indexes all code, installs git hooks, and writes the MCP server entry to `.mcp.json`.

```bash
cd /path/to/your/project
cce init
```

**What it does:**
- Walks the repository and builds a vector + FTS index
- Installs a `post-commit` git hook so the index stays current automatically
- Writes `.mcp.json` pointing Claude Code at the local MCP server
- Creates or updates `CLAUDE.md` with CCE instructions and output style rules

**Example output:**
```
Indexing project...
Indexed 1,240 chunks from 87 files
Git hook installed at .git/hooks/post-commit
MCP server entry written to .mcp.json
CLAUDE.md updated with CCE instructions
```

**Works on non-git projects too.** If the directory is not a git repository, CCE skips the git hook step and indexes normally.

---

## cce index

Re-index files that have changed since the last run.

```bash
cce index
```

**Variants:**

```bash
# Force a full re-index of every file (ignores change detection)
cce index --full

# Index only a specific file
cce index --path src/payments/processor.py

# Index only a specific directory
cce index --path src/payments/
```

**Example output:**
```
Indexed 3 chunks from 1 file, pruned 0 deleted
```

The git hook installed by `cce init` calls `cce index` automatically after every commit. You only need to run it manually if you want to index without committing.

---

## cce status

Show index health and a token savings summary for the current project.

```bash
cce status
```

**Example output:**
```
Project:    my-project
Chunks:     1,240
Files:      87
Queries:    42
Tokens saved: 67%

Embedding model: BAAI/bge-small-en-v1.5
Storage:    ~/.claude-context-engine/projects/my-project/
```

---

## cce savings

Visual token savings report in the terminal.

```bash
cce savings
```

**Example output:**
```
     my-project · 42 queries
     18.4k / 58.0k tokens used (32%)

     Token savings
     With CCE:     18,400 tokens  (32%)
     Tokens saved: 39,600 tokens  (68%)
```

**Variants:**

```bash
# Savings across every indexed project
cce savings --all

# Machine-readable JSON (useful for scripts)
cce savings --json
```

**JSON output example:**
```json
{
  "project": "my-project",
  "queries": 42,
  "served_tokens": 18400,
  "full_file_tokens": 58000,
  "savings_percent": 68.3
}
```

---

## cce commands

Manage project-specific rules, preferences, and commands. Stored in `.cce/commands.yaml`.

```bash
# Add rules Claude must follow
cce commands add-rule 'Never generate down() in migrations'
cce commands add-rule 'Use UUID for primary keys'

# Set project preferences
cce commands set-pref database PostgreSQL
cce commands set-pref auth Sanctum

# Add commands to lifecycle hooks
cce commands add before_push 'composer test'
cce commands add before_commit 'php-cs-fixer fix --dry-run'

# Add named custom commands
cce commands add-custom deploy 'kubectl apply -f k8s/'

# List all (merged with workspace if present)
cce commands list

# Remove
cce commands remove-rule 'Never generate down() in migrations'
cce commands remove-pref database
cce commands remove before_push 'composer test'
cce commands remove custom deploy
```

**Workspace support:** Place a `.cce/commands.yaml` in a parent directory to define shared rules across multiple projects. Project configs extend the workspace. See [Project Commands](Project-Commands) for full details.

---

## cce clear

Clear all index data and reset stats for the current project. Useful when you want a clean slate after major refactoring.

```bash
cce clear
```

CCE will ask for confirmation before deleting:
```
This will delete all index data for my-project. Continue? [y/N]
```

```bash
# Skip the confirmation prompt
cce clear --yes
```

After clearing, run `cce index --full` to rebuild.

---

## cce prune

Remove stored index data for projects whose directories no longer exist on disk. Keeps `~/.claude-context-engine/` tidy.

```bash
cce prune
```

**Preview mode — shows what would be removed without deleting:**
```bash
cce prune --dry-run
```

**Example output:**
```
Would remove: old-project (directory /Users/raj/projects/old-project not found)
Run without --dry-run to delete.
```

---

## cce dashboard

Open the web dashboard in your browser for a visual overview of your index.

```bash
cce dashboard
```

The dashboard provides four views:

- **Overview** — chunks indexed, files indexed, queries run, tokens saved, live charts
- **Files** — full file list with staleness detection (`ok`, `stale`, `missing`)
- **Sessions** — architectural decisions and code areas from past Claude sessions
- **Savings** — token usage breakdown with compression controls

**Variants:**

```bash
# Open on a specific port
cce dashboard --port 8080

# Start the server without opening a browser
cce dashboard --no-browser
```

---

## cce services

Manage Ollama and the Dashboard as background processes. Check status, start, and stop without blocking a terminal.

### Check status

```bash
cce services
```

**Example output:**
```
SERVICE     STATUS    DETAIL
------------------------------------------------
ollama      running   localhost:11434 (external)
dashboard   stopped
mcp         running   managed by Claude Code
```

- `ollama` and `dashboard` can be started and stopped by CCE
- `mcp` is always managed by Claude Code and is shown read-only

### Start services

```bash
# Start everything (Ollama + Dashboard)
cce services start

# Start only Ollama
cce services start ollama

# Start the dashboard on the default port (8080)
cce services start dashboard

# Start the dashboard on a custom port
cce services start dashboard --port 9000
```

**Example output:**
```
  ✓ Ollama started (PID 12345)
  ✓ Dashboard started at http://localhost:8080 (PID 12346)
```

If a service is already running, CCE reports it instead of starting a duplicate:
```
  · Ollama is already running.
```

### Stop services

```bash
# Stop everything CCE started
cce services stop

# Stop only the dashboard
cce services stop dashboard

# Stop only Ollama
cce services stop ollama
```

**Note:** CCE can only stop processes it started. If Ollama was started externally (e.g. via `ollama serve` in another terminal), CCE will report it as `running (external)` and will not stop it.

---

## cce serve

Start the MCP server. Claude Code calls this automatically using the entry in `.mcp.json` — you do not need to run this manually.

```bash
cce serve
```

If you need to point the server at a specific project directory (useful for debugging):

```bash
cce serve --project-dir /path/to/your/project
```
