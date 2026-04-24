# src/context_engine/cli.py
"""CLI entry point for claude-context-engine."""
import asyncio
import json
import socket
import sys
from pathlib import Path

import click

from context_engine.config import load_config, PROJECT_CONFIG_NAME


def _configure_mcp(project_dir: Path) -> bool:
    """Write MCP server config to .mcp.json in the project directory.

    Returns True if the entry was added. Uses an atomic write so a crash or
    partial write can't destroy pre-existing MCP server entries in the file.
    """
    import os
    import tempfile

    mcp_path = project_dir / ".mcp.json"
    cce_bin = Path(sys.executable).parent / "cce"
    command = str(cce_bin) if cce_bin.exists() else "cce"

    entry = {"command": command, "args": ["serve", "--project-dir", str(project_dir)]}

    if mcp_path.exists():
        try:
            data = json.loads(mcp_path.read_text())
        except (json.JSONDecodeError, OSError):
            data = {}
    else:
        data = {}

    servers = data.setdefault("mcpServers", {})
    if "context-engine" in servers:
        return False  # already configured

    servers["context-engine"] = entry

    # Atomic write: serialise to a tempfile in the same dir, then rename.
    fd, tmp_name = tempfile.mkstemp(
        prefix=".mcp.json.", suffix=".tmp", dir=str(project_dir)
    )
    try:
        with os.fdopen(fd, "w") as f:
            f.write(json.dumps(data, indent=2) + "\n")
        os.replace(tmp_name, mcp_path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return True


_CCE_CLAUDE_MD_MARKER = "## Context Engine (CCE)"

_CCE_CLAUDE_MD_BLOCK = """\
## Context Engine (CCE)

This project uses Claude Context Engine for intelligent code retrieval.

**IMPORTANT: You MUST use `context_search` instead of reading files directly**
when exploring the codebase, answering questions about code, or understanding
how things work. This is a hard requirement, not a suggestion. The `context_search`
MCP tool routes queries through the semantic search engine, which:
- Returns only the most relevant code chunks (not entire files)
- Tracks token savings automatically
- Provides confidence scores for each result

**When to use `context_search`:**
- Answering questions about the codebase ("how does X work?", "where is Y?")
- Exploring code structure or architecture
- Finding related code, functions, or patterns
- Any time you would otherwise read a file to understand it

**When to use `Read` instead:**
- You need to edit a specific file (read before editing)
- You need the exact, complete content of a known file path

Other useful MCP tools:
- `expand_chunk` — get full source for a compressed result
- `related_context` — find what calls/imports a function
- `session_recall` — retrieve decisions from past sessions
- `record_decision` — persist an important decision for future sessions

## Output Style

Be concise. Lead with the answer or action, not reasoning. Skip filler words,
preamble, and phrases like "I'll help you with that" or "Certainly!". Prefer
fragments over full sentences in explanations. No trailing summaries of what
you just did. One sentence if it fits.

Code blocks, file paths, commands, and error messages are always written in full.
"""


def _resolve_cce_cmd() -> str:
    """Find the globally installed cce binary path."""
    from context_engine.utils import resolve_cce_binary
    return resolve_cce_binary()


def _has_cce_hook(hook_list: list, marker: str) -> bool:
    """Check if a CCE hook already exists in a hooks list."""
    for entry in hook_list:
        for h in entry.get("hooks", []):
            if marker in h.get("command", ""):
                return True
    return False


def _ensure_session_hook(project_dir: Path) -> None:
    """Add Claude Code hooks so CCE status shows on startup."""
    settings_dir = project_dir / ".claude"
    settings_dir.mkdir(exist_ok=True)
    settings_path = settings_dir / "settings.local.json"

    if settings_path.exists():
        try:
            data = json.loads(settings_path.read_text())
        except (json.JSONDecodeError, OSError):
            data = {}
    else:
        data = {}

    hooks = data.setdefault("hooks", {})
    cce_cmd = _resolve_cce_cmd()
    changed = False

    # SessionStart hook — show CCE status
    session_hooks = hooks.setdefault("SessionStart", [])
    if not _has_cce_hook(session_hooks, "cce status"):
        session_hooks.append({
            "matcher": "",
            "hooks": [{"type": "command", "command": f"{cce_cmd} status --oneline"}],
        })
        changed = True

    if changed:
        settings_path.write_text(json.dumps(data, indent=2) + "\n")
        _ok("SessionStart hook installed for CCE status")


from context_engine.cli_style import success, warn as _warn_style, dim as _dim_style, value, header, label, CHECK, CROSS, DOT, ARROW


def _ok(msg: str) -> None:
    """Print a green ✓ success line."""
    click.echo(f"  {CHECK} {msg}")


def _warn(msg: str) -> None:
    """Print a yellow ! warning line."""
    click.echo(f"  {DOT} {_warn_style(msg)}")


def _dim(msg: str) -> str:
    return _dim_style(msg)


def _preflight_check(config) -> None:
    """Verify all required components are ready before indexing starts.

    Downloads the embedding model on first use with a clear progress message,
    and reports Ollama status so users know what compression level they will get.
    """
    # --- Embedding model ---
    click.echo(_dim("  Checking embedding model") + "...", nl=False)
    try:
        from fastembed import TextEmbedding
        model_name = getattr(config, "embedding_model", "BAAI/bge-small-en-v1.5")
        if "/" not in model_name:
            model_name = f"sentence-transformers/{model_name}"
        click.echo(_dim(" downloading if needed (60 MB, first time only)") + "...", nl=False)
        TextEmbedding(model_name)
        click.echo(" " + click.style("ready", fg="green"))
    except Exception as exc:
        click.echo("")
        _warn(f"Could not load embedding model: {exc}")
        _warn("Indexing will attempt to continue but may fail.")

    # --- Ollama (optional) ---
    try:
        import httpx
        resp = httpx.get("http://localhost:11434/api/tags", timeout=2.0)
        if resp.status_code == 200:
            click.echo(
                "  Ollama " + click.style("detected", fg="green") +
                " — LLM summarization enabled."
            )
        else:
            click.echo(
                "  Ollama " + click.style("not running", fg="yellow") +
                " — using truncation compression."
            )
            click.echo(_dim("  Tip: ollama pull phi3:mini for LLM summarization"))
    except Exception:
        click.echo(
            "  Ollama " + click.style("not running", fg="yellow") +
            " — using truncation compression."
        )
        click.echo(_dim("  Tip: ollama pull phi3:mini for LLM summarization"))


def _ensure_claude_md(project_dir: Path) -> None:
    """Add CCE instructions to CLAUDE.md if not already present."""
    claude_md = project_dir / "CLAUDE.md"
    if claude_md.exists():
        existing = claude_md.read_text()
        if _CCE_CLAUDE_MD_MARKER in existing:
            return  # already has CCE block
        new_content = existing.rstrip() + "\n\n" + _CCE_CLAUDE_MD_BLOCK
        claude_md.write_text(new_content)
        _ok("CLAUDE.md updated with CCE instructions")
    else:
        claude_md.write_text(_CCE_CLAUDE_MD_BLOCK)
        _ok("CLAUDE.md created with CCE instructions")


@click.group()
@click.version_option(package_name="claude-context-engine")
@click.option("--verbose", "-v", is_flag=True, help="Enable detailed logging output")
@click.pass_context
def main(ctx: click.Context, verbose: bool) -> None:
    """claude-context-engine — Local context engine for Claude Code."""
    ctx.ensure_object(dict)
    project_path = Path.cwd() / PROJECT_CONFIG_NAME
    ctx.obj["config"] = load_config(project_path=project_path if project_path.exists() else None)
    ctx.obj["verbose"] = verbose


@main.command()
@click.pass_context
def init(ctx: click.Context) -> None:
    """Initialize context engine and connect it to Claude Code."""
    from context_engine.indexer.git_hooks import install_hooks
    from context_engine.project_commands import ensure_gitignore
    config = ctx.obj["config"]
    project_dir = Path.cwd()

    click.echo("")
    click.echo(
        click.style("  Claude Context Engine", fg="cyan", bold=True) +
        click.style(f"  ·  {project_dir.name}", fg="white", bold=True)
    )
    click.echo(_dim("  " + "─" * 44))
    click.echo("")

    # 1. Pre-flight: verify embedding model + report Ollama status
    _preflight_check(config)
    click.echo("")

    # 2. Storage
    project_name = project_dir.name
    storage_dir = Path(config.storage_path) / project_name
    storage_dir.mkdir(parents=True, exist_ok=True)
    meta_path = storage_dir / "meta.json"
    meta_path.write_text(json.dumps({"project_dir": str(project_dir.resolve())}))

    # 3. Git hooks
    is_git_repo = (project_dir / ".git").exists()
    if is_git_repo:
        installed = install_hooks(str(project_dir))
        if installed:
            _ok(f"Git hooks installed  " + _dim(f"({len(installed)} hooks, auto-updates on commit)"))
    else:
        _warn("Not a git repository — git hook skipped")
        click.echo(_dim("    Run `cce index` manually after making changes."))

    # 4. MCP config
    configured = _configure_mcp(project_dir)
    if configured:
        _ok("MCP server registered in " + click.style(".mcp.json", fg="cyan"))
    else:
        _ok("MCP server already configured in " + click.style(".mcp.json", fg="cyan"))

    # 5. CLAUDE.md + session hook
    _ensure_claude_md(project_dir)
    _ensure_session_hook(project_dir)

    # 6. .gitignore — add CCE per-machine entries
    ensure_gitignore(str(project_dir))
    _ok(".gitignore updated with CCE entries")

    click.echo("")
    click.echo(
        "  " + click.style("Indexing project", fg="cyan", bold=True) + "..."
    )
    asyncio.run(_run_index(config, str(project_dir), full=True))
    click.echo("")
    click.echo(
        click.style("  Done!", fg="green", bold=True) +
        click.style("  Restart Claude Code to activate CCE.", fg="white")
    )
    click.echo("")


@main.command()
@click.option("--full", is_flag=True, help="Force full re-index of every file")
@click.option("--path", type=str, default=None, help="Index only this file or directory")
@click.pass_context
def index(ctx: click.Context, full: bool, path: str | None) -> None:
    """Index or re-index project files."""
    config = ctx.obj["config"]
    verbose = ctx.obj["verbose"]
    project_dir = str(Path.cwd())
    from context_engine.cli_style import header
    click.echo("  " + header("Indexing") + "...")
    asyncio.run(_run_index(config, project_dir, full=full, target_path=path, verbose=verbose))


@main.command()
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.option("--oneline", is_flag=True, help="Single-line status for hooks")
@click.pass_context
def status(ctx: click.Context, output_json: bool, oneline: bool) -> None:
    """Show index status and config."""
    import json as _json
    from importlib.metadata import version as pkg_version
    config = ctx.obj["config"]
    verbose = ctx.obj["verbose"]

    if oneline:
        try:
            ver = pkg_version("claude-context-engine")
        except Exception:
            ver = "?"
        project_name = Path.cwd().name
        storage = Path(config.storage_path) / project_name
        stats_path = storage / "stats.json"
        chunks = 0
        savings = ""
        try:
            from context_engine.storage.vector_store import VectorStore
            vs = VectorStore(db_path=str(storage / "vectors"))
            chunks = vs.count()
        except Exception:
            pass
        if stats_path.exists():
            try:
                stats = _json.loads(stats_path.read_text())
                q = stats.get("queries", 0)
                full = stats.get("full_file_tokens", 0)
                served = stats.get("served_tokens", 0)
                if q > 0 and full > 0:
                    pct = int((full - served) / full * 100)
                    savings = f" · {pct}% saved over {q} queries"
            except Exception:
                pass
        click.echo(
            f"CCE v{ver} · {project_name} · {chunks} chunks indexed{savings}\n"
            f"USE context_search MCP tool for all code questions. Do NOT use Read/Grep to explore code."
        )
        return

    if output_json:
        out = {
            "storage_path": config.storage_path,
            "compression_level": config.compression_level,
            "resource_profile": config.detect_resource_profile(),
        }
        click.echo(_json.dumps(out, indent=2))
        return

    from context_engine.cli_style import header, label, value, dim, success, warn, CHECK, DOT

    click.echo(f"  {label('Storage path')}     {value(config.storage_path)}")
    click.echo(f"  {label('Compression')}      {value(config.compression_level)}")
    click.echo(f"  {label('Resource profile')} {value(config.detect_resource_profile())}")

    # Token savings
    project_name = Path.cwd().name
    stats_path = Path(config.storage_path) / project_name / "stats.json"
    if stats_path.exists():
        try:
            stats = _json.loads(stats_path.read_text())
            raw = stats.get("raw_tokens", 0)
            full = stats.get("full_file_tokens", 0)
            served = stats.get("served_tokens", 0)
            queries = stats.get("queries", 0)
            baseline = max(full, raw) if full > 0 else raw
            saved = max(0, baseline - served)
            pct = int(saved / baseline * 100) if baseline > 0 else 0
            click.echo()
            click.echo(f"  {header('Token savings')} {dim(f'({queries} queries)')}")
            click.echo(f"    Full codebase: {value(f'{baseline:,}')}")
            click.echo(f"    Served tokens: {value(f'{served:,}')}")
            click.echo(f"    {CHECK} Saved:         {success(f'{saved:,}')} {dim(f'({pct}%)')}")
        except (KeyError, _json.JSONDecodeError):
            pass
    else:
        click.echo()
        storage_dir = Path(config.storage_path) / Path.cwd().name
        vectors_dir = storage_dir / "vectors"
        if not vectors_dir.exists():
            click.echo(f"  {DOT} {dim('Project not indexed yet — run: cce init')}")
        else:
            click.echo(f"  {DOT} {dim('No usage recorded yet — run context_search via MCP')}")

    if verbose:
        storage_path = Path(config.storage_path)
        if storage_path.exists():
            projects = [d for d in storage_path.iterdir() if d.is_dir()]
            click.echo()
            click.echo(f"  {header('Projects indexed')} {value(str(len(projects)))}")
            for project in projects:
                chunks = list(project.glob("**/*.json"))
                click.echo(f"    {dim('·')} {project.name}: {chunks} stored files")
        else:
            click.echo(f"  {DOT} {dim('Storage directory does not exist yet.')}")


@main.group()
def commands():
    """Manage project-specific commands (before_push, before_commit, etc.)."""


@commands.command("add")
@click.argument("hook", type=click.Choice(["before_push", "before_commit", "on_start"]))
@click.argument("command")
def commands_add(hook: str, command: str) -> None:
    """Add a command to a hook. Example: cce commands add before_push 'composer test'"""
    from context_engine.project_commands import load_project_only, add_command
    from context_engine.cli_style import success, warn, CHECK, DOT
    existing = load_project_only(str(Path.cwd())).get(hook, [])
    if command in existing:
        click.echo(f"  {DOT} {warn('Already exists')} in {hook}: {command}")
        return
    add_command(str(Path.cwd()), hook, command)
    click.echo(f"  {CHECK} {success('Added')} to {hook}: {command}")


@commands.command("add-custom")
@click.argument("name")
@click.argument("command")
def commands_add_custom(name: str, command: str) -> None:
    """Add a named custom command. Example: cce commands add-custom deploy 'kubectl apply -f k8s/'"""
    from context_engine.project_commands import add_custom_command
    from context_engine.cli_style import success, CHECK
    add_custom_command(str(Path.cwd()), name, command)
    click.echo(f"  {CHECK} {success('Added')} custom command '{name}': {command}")


@commands.command("remove")
@click.argument("hook")
@click.argument("command")
def commands_remove(hook: str, command: str) -> None:
    """Remove a command from a hook."""
    from context_engine.project_commands import remove_command
    from context_engine.cli_style import success, warn, CHECK, DOT
    if remove_command(str(Path.cwd()), hook, command):
        click.echo(f"  {CHECK} {success('Removed')} from {hook}: {command}")
    else:
        click.echo(f"  {DOT} {warn('Not found')} in {hook}: {command}")


@commands.command("add-rule")
@click.argument("rule")
def commands_add_rule(rule: str) -> None:
    """Add a project rule. Example: cce commands add-rule 'Never use down() in migrations'"""
    from context_engine.project_commands import load_project_only, add_rule
    existing = load_project_only(str(Path.cwd())).get("rules", [])
    from context_engine.cli_style import success, warn, CHECK, DOT
    if rule in existing:
        click.echo(f"  {DOT} {warn('Already exists')}: {rule}")
        return
    add_rule(str(Path.cwd()), rule)
    click.echo(f"  {CHECK} {success('Rule added')}: {rule}")


@commands.command("remove-rule")
@click.argument("rule")
def commands_remove_rule(rule: str) -> None:
    """Remove a project rule."""
    from context_engine.project_commands import remove_rule
    from context_engine.cli_style import success, warn, CHECK, DOT
    if remove_rule(str(Path.cwd()), rule):
        click.echo(f"  {CHECK} {success('Rule removed')}: {rule}")
    else:
        click.echo(f"  {DOT} {warn('Not found')}: {rule}")


@commands.command("set-pref")
@click.argument("key")
@click.argument("value")
def commands_set_pref(key: str, value: str) -> None:
    """Set a preference. Example: cce commands set-pref database PostgreSQL"""
    from context_engine.project_commands import set_preference
    from context_engine.cli_style import success, CHECK
    set_preference(str(Path.cwd()), key, value)
    click.echo(f"  {CHECK} {success('Preference set')}: {key} = {value}")


@commands.command("remove-pref")
@click.argument("key")
def commands_remove_pref(key: str) -> None:
    """Remove a preference."""
    from context_engine.project_commands import remove_preference
    from context_engine.cli_style import success, warn, CHECK, DOT
    if remove_preference(str(Path.cwd()), key):
        click.echo(f"  {CHECK} {success('Preference removed')}: {key}")
    else:
        click.echo(f"  {DOT} {warn('Not found')}: {key}")


@commands.command("list")
def commands_list() -> None:
    """Show all project commands, rules, and preferences (merged with workspace)."""
    from context_engine.project_commands import load_commands
    from context_engine.cli_style import header, label, dim, value, DOT, ARROW
    cmds = load_commands(str(Path.cwd()))
    if not cmds:
        click.echo(f"  {DOT} {dim('No project configuration found.')}")
        click.echo(f"    {dim('cce commands add-rule')} 'Never use down() in migrations'")
        click.echo(f"    {dim('cce commands set-pref')} database PostgreSQL")
        click.echo(f"    {dim('cce commands add')} before_push 'composer test'")
        return

    rules = cmds.get("rules", [])
    prefs = cmds.get("preferences", {})
    hooks = {k: v for k, v in cmds.items() if k not in ("rules", "preferences", "custom") and isinstance(v, list)}
    custom = cmds.get("custom", {})

    if rules:
        click.echo(f"  {header('Rules')}")
        for r in rules:
            click.echo(f"    {ARROW} {r}")
    if prefs:
        click.echo(f"  {header('Preferences')}")
        for k, v in prefs.items():
            click.echo(f"    {label(k)}: {value(str(v))}")
    hook_labels = {"before_push": "Before push", "before_commit": "Before commit", "on_start": "On start"}
    for hook_key, hook_cmds in hooks.items():
        hook_name = hook_labels.get(hook_key, hook_key)
        click.echo(f"  {header(hook_name)}")
        for c in hook_cmds:
            click.echo(f"    {ARROW} {dim('$')} {c}")
    if custom:
        click.echo(f"  {header('Custom commands')}")
        for name, cmd in custom.items():
            click.echo(f"    {label(name)} {ARROW} {dim('$')} {cmd}")


@main.command()
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.option("--all", "all_projects", is_flag=True, help="Show savings for all indexed projects")
@click.pass_context
def savings(ctx: click.Context, as_json: bool, all_projects: bool) -> None:
    """Show token savings report — how much CCE is saving you."""
    config = ctx.obj["config"]
    _run_savings_report(config, as_json=as_json, all_projects=all_projects)


def _run_savings_report(config, *, as_json: bool = False, all_projects: bool = False) -> None:
    """Shared implementation for savings report (used by subcommand and shortcut)."""
    import json as _json

    storage_root = Path(config.storage_path)

    def _load_stats(project_dir: Path) -> dict | None:
        stats_path = project_dir / "stats.json"
        if not stats_path.exists():
            return None
        try:
            return _json.loads(stats_path.read_text())
        except (KeyError, _json.JSONDecodeError):
            return None

    from context_engine.cli_style import header, label, value, dim, success, bold

    _COLS = 10

    def _fmt_k(n: int) -> str:
        return f"{n / 1000:.1f}k" if n >= 1000 else str(n)

    def _grid_rows(used_pct: float, rows: int) -> list[str]:
        total = _COLS * rows
        filled = max(0, min(total, round(used_pct * total)))
        result = []
        for r in range(rows):
            cells = []
            for c in range(_COLS):
                if r * _COLS + c < filled:
                    cells.append(click.style("█", fg="cyan"))
                else:
                    cells.append(click.style("░", dim=True))
            result.append("     " + " ".join(cells))
        return result

    def _print_project(name: str, stats: dict) -> None:
        full_file = stats.get("full_file_tokens", 0)
        served = stats.get("served_tokens", 0)
        queries = stats.get("queries", 0)
        raw = stats.get("raw_tokens", 0)
        baseline = max(full_file, raw) if full_file > 0 else raw
        saved = max(0, baseline - served)
        used_pct = served / baseline if baseline > 0 else 0
        saved_pct = int((1 - used_pct) * 100) if baseline > 0 else 0
        used_pct_int = int(used_pct * 100)

        labels: list[str] = [
            f"  {bold(name)} {dim('·')} {value(f'{queries:,}')} {dim('queries')}",
            f"  {value(_fmt_k(served))}{dim('/')}{value(_fmt_k(baseline))} {dim('tokens used')} {dim(f'({used_pct_int}%)')}",
            "",
            f"  {header('Token savings')}",
            f"  {label('With CCE:')}    {value(f'{served:>10,}')} {dim('tokens')}  {dim(f'({used_pct_int}%)')}",
            f"  {success('Saved:')}       {success(f'{saved:>10,}')} {dim('tokens')}  {success(f'({saved_pct}%)')}",
        ]

        grid = _grid_rows(used_pct, rows=len(labels))
        click.echo()
        for g, l in zip(grid, labels):
            click.echo(f"{g}   {l}")

    def _json_entry(name: str, stats: dict) -> dict:
        full_file = stats.get("full_file_tokens", 0)
        raw = stats.get("raw_tokens", 0)
        served = stats.get("served_tokens", 0)
        baseline = max(full_file, raw) if full_file > 0 else raw
        saved = baseline - served
        return {
            "project": name,
            "queries": stats.get("queries", 0),
            "full_file_tokens": full_file,
            "served_tokens": served,
            "tokens_saved": saved,
            "savings_pct": int(saved / baseline * 100) if baseline > 0 else 0,
        }

    # Collect projects
    if all_projects:
        if not storage_root.exists():
            if as_json:
                click.echo(_json.dumps({"projects": []}))
            else:
                click.echo("No indexed projects found.")
            return
        project_dirs = sorted(
            (d for d in storage_root.iterdir() if d.is_dir()),
            key=lambda d: d.name,
        )
    else:
        project_name = Path.cwd().name
        project_dirs = [storage_root / project_name]

    reports: list[tuple[str, dict]] = []
    for pd in project_dirs:
        stats = _load_stats(pd)
        if stats is not None:
            reports.append((pd.name, stats))

    if not reports:
        if as_json:
            if all_projects:
                click.echo(_json.dumps({"projects": []}))
            else:
                click.echo(_json.dumps(_json_entry(Path.cwd().name, {
                    "raw_tokens": 0, "served_tokens": 0, "queries": 0,
                })))
        else:
            click.echo(f"  {dim('No usage recorded yet.')}")
            click.echo(f"  {dim('Run context_search queries via MCP to start tracking savings.')}")
        return

    if as_json:
        if all_projects:
            click.echo(_json.dumps(
                {"projects": [_json_entry(n, s) for n, s in reports]}, indent=2,
            ))
        else:
            click.echo(_json.dumps(_json_entry(*reports[0]), indent=2))
        return

    # Text output
    for name, stats in reports:
        _print_project(name, stats)
        if len(reports) > 1:
            click.echo()
            click.echo("  " + "─" * 52)

    if len(reports) > 1:
        total_raw = sum(s.get("raw_tokens", 0) for _, s in reports)
        total_served = sum(s.get("served_tokens", 0) for _, s in reports)
        total_queries = sum(s.get("queries", 0) for _, s in reports)
        total_saved = total_raw - total_served
        total_pct = int(total_saved / total_raw * 100) if total_raw > 0 else 0
        click.echo()
        click.echo(f"  {bold('Total')} {dim('across')} {value(str(len(reports)))} {dim('projects ·')} {value(f'{total_queries:,}')} {dim('queries')}")
        click.echo(f"  {success(f'Saved: {total_saved:,} tokens ({total_pct}%)')}")

    click.echo()


@main.command()
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
def clear(ctx: click.Context, yes: bool) -> None:
    """Clear all index data for the current project (vectors, FTS, graph, manifest)."""
    from context_engine.storage.local_backend import LocalBackend

    config = ctx.obj["config"]
    project_name = Path.cwd().name
    storage_dir = Path(config.storage_path) / project_name

    from context_engine.cli_style import warn, success, dim, CHECK, DOT

    if not storage_dir.exists():
        click.echo(f"  {DOT} {dim(f'No index data found for')} {project_name}")
        return

    if not yes:
        click.confirm(f"  {warn('Clear all index data for')} {project_name}? This cannot be undone.", abort=True)

    backend = LocalBackend(base_path=str(storage_dir))
    asyncio.run(backend.clear())

    # Reset manifest so next index starts fresh
    manifest_path = storage_dir / "manifest.json"
    if manifest_path.exists():
        manifest_path.write_text(json.dumps({"__schema_version": 2, "files": {}}))

    # Reset stats
    stats_path = storage_dir / "stats.json"
    stats_path.write_text(json.dumps({"queries": 0, "raw_tokens": 0, "served_tokens": 0, "full_file_tokens": 0}))

    click.echo(f"  {CHECK} {success('Cleared')} index data for {project_name}. Run {dim('cce index')} to re-index.")


@main.command()
@click.option("--dry-run", is_flag=True, help="Show what would be removed without deleting")
@click.pass_context
def prune(ctx: click.Context, dry_run: bool) -> None:
    """Remove index data for projects whose directories no longer exist."""
    import shutil
    config = ctx.obj["config"]
    storage_root = Path(config.storage_path)
    if not storage_root.exists():
        click.echo("No indexed projects found.")
        return

    removed = []
    kept = []
    for project_dir in sorted(storage_root.iterdir()):
        if not project_dir.is_dir():
            continue
        meta_path = project_dir / "meta.json"
        if not meta_path.exists():
            kept.append((project_dir.name, "(no meta.json — skipping)"))
            continue
        try:
            meta = json.loads(meta_path.read_text())
            source_path = Path(meta.get("project_dir", ""))
        except (json.JSONDecodeError, OSError):
            kept.append((project_dir.name, "(unreadable meta.json — skipping)"))
            continue

        if source_path and source_path.exists():
            kept.append((project_dir.name, str(source_path)))
        else:
            removed.append((project_dir.name, str(source_path), project_dir))

    from context_engine.cli_style import success, warn, dim, CHECK, CROSS, DOT

    if not removed:
        click.echo(f"  {CHECK} {success('Nothing to prune')} — all indexed projects still exist.")
        for name, path in kept:
            click.echo(f"    {CHECK} {name}  {dim(f'({path})')}")
        return

    for name, path, storage_dir in removed:
        if dry_run:
            click.echo(f"    {DOT} {warn('[dry-run] would remove')}  {name}  {dim(f'(source: {path})')}")
        else:
            shutil.rmtree(storage_dir)
            click.echo(f"    {CROSS} {warn('removed')}  {name}  {dim(f'(source: {path})')}")

    for name, path in kept:
        click.echo(f"    {CHECK} {dim('kept')}  {name}  {dim(f'({path})')}")


def savings_shortcut() -> None:
    """Entry point for the `cce-savings` shortcut command."""
    import sys as _sys

    @click.command()
    @click.option("--json", "as_json", is_flag=True, help="Output as JSON")
    @click.option("--all", "all_projects", is_flag=True, help="Show all projects")
    def _cmd(as_json: bool, all_projects: bool) -> None:
        """Show CCE token savings — how much context compression is saving you."""
        project_path = Path.cwd() / PROJECT_CONFIG_NAME
        config = load_config(project_path=project_path if project_path.exists() else None)
        _run_savings_report(config, as_json=as_json, all_projects=all_projects)

    _cmd()


def _find_free_port() -> int:
    """Return an available TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@main.command()
@click.option("--http", "as_http", is_flag=True, help="Start HTTP REST server instead of stdio MCP")
@click.option("--host", default="127.0.0.1", show_default=True, help="HTTP bind host (requires CCE_API_TOKEN for non-loopback)")
@click.option("--port", default=8765, show_default=True, help="HTTP port")
@click.option("--project-dir", default=None, help="Project directory (defaults to cwd)")
@click.pass_context
def serve(ctx: click.Context, as_http: bool, host: str, port: int, project_dir: str | None) -> None:
    """Start the MCP server (used by Claude Code).

    With --http, starts a REST server exposing the storage backend for remote
    backend clients. Binds loopback by default; exposing on other interfaces
    requires CCE_API_TOKEN to be set.
    """
    if project_dir:
        import os
        os.chdir(project_dir)
    if as_http:
        from context_engine.serve_http import run_http_server
        run_http_server(ctx.obj["config"], host=host, port=port)
        return
    from importlib.metadata import version as pkg_version
    try:
        ver = pkg_version("claude-context-engine")
    except Exception:
        ver = "unknown"
    click.echo(f"CCE v{ver} · Starting context engine MCP server...", err=True)
    asyncio.run(_run_serve(ctx.obj["config"]))


@main.command()
@click.option("--port", default=0, type=int, help="Port to listen on (0 = random free port)")
@click.option("--no-browser", is_flag=True, help="Don't open browser automatically")
@click.pass_context
def dashboard(ctx: click.Context, port: int, no_browser: bool) -> None:
    """Start the web dashboard for index inspection."""
    import webbrowser
    import uvicorn
    from context_engine.dashboard.server import create_app

    config = ctx.obj["config"]
    project_dir = Path.cwd()

    if port == 0:
        port = _find_free_port()

    from context_engine.cli_style import header, value, dim
    url = f"http://localhost:{port}"
    click.echo(f"  {header('CCE Dashboard')} at {value(url)}")
    click.echo(f"  {dim('Press Ctrl+C to stop.')}")

    if not no_browser:
        webbrowser.open(url)

    app = create_app(config, project_dir)
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="error")


# ── services command group ────────────────────────────────────────────────────

@main.group(invoke_without_command=True)
@click.pass_context
def services(ctx: click.Context) -> None:
    """Show status of CCE services (Ollama, Dashboard)."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(services_status)


@services.command(name="status")
def services_status() -> None:
    """Show status of all CCE services."""
    from context_engine.services import get_ollama_status, get_dashboard_status, get_mcp_status

    rows = [
        get_ollama_status(),
        get_dashboard_status(),
        get_mcp_status(),
    ]

    from context_engine.cli_style import header, dim
    click.echo(f"  {header('SERVICE'):<24}{header('STATUS'):<22}{header('DETAIL')}")
    click.echo(f"  {dim('─' * 50)}")

    for row in rows:
        running = row["running"]
        status_text = "running" if running else "stopped"
        status_col = click.style(f"{status_text:<10}", fg="green" if running else "red")
        detail = row.get("detail", "")
        click.echo(f"  {row['name']:<12}{status_col}  {dim(detail)}")


@services.command(name="start")
@click.argument("service", required=False, type=click.Choice(["ollama", "dashboard", "all"]), default="all")
@click.option("--port", default=8080, show_default=True, help="Dashboard port (only used when starting dashboard)")
def services_start(service: str, port: int) -> None:
    """Start CCE services. SERVICE: ollama | dashboard | all (default)."""
    from context_engine.services import start_ollama, start_dashboard

    targets = ["ollama", "dashboard"] if service == "all" else [service]

    for target in targets:
        if target == "ollama":
            ok, msg = start_ollama()
        else:
            ok, msg = start_dashboard(port=port)
        prefix = click.style("✓", fg="green") if ok else click.style("·", fg="yellow")
        click.echo(f"  {prefix} {msg}")


@services.command(name="stop")
@click.argument("service", required=False, type=click.Choice(["ollama", "dashboard", "all"]), default="all")
def services_stop(service: str) -> None:
    """Stop CCE services. SERVICE: ollama | dashboard | all (default)."""
    from context_engine.services import stop_ollama, stop_dashboard

    targets = ["ollama", "dashboard"] if service == "all" else [service]

    for target in targets:
        if target == "ollama":
            ok, msg = stop_ollama()
        else:
            ok, msg = stop_dashboard()
        prefix = click.style("✓", fg="green") if ok else click.style("·", fg="yellow")
        click.echo(f"  {prefix} {msg}")


async def _run_index(
    config,
    project_dir: str,
    full: bool = False,
    target_path: str | None = None,
    verbose: bool = False,
) -> None:
    """Run indexing pipeline (thin wrapper over `indexer.pipeline.run_indexing`)."""
    from context_engine.indexer.pipeline import run_indexing

    log_fn = (lambda msg: click.echo(msg)) if verbose else None
    from context_engine.cli_style import success, warn, dim, value, CHECK, CROSS

    _showed_progress = False
    _bar_width = 30

    def progress_fn(current: int, total: int) -> None:
        nonlocal _showed_progress
        if not verbose and sys.stdout.isatty():
            filled = int(_bar_width * current / total) if total else 0
            bar = (
                click.style("█" * filled, fg="cyan") +
                click.style("░" * (_bar_width - filled), fg="bright_black")
            )
            pct = click.style(f"{int(100 * current / total) if total else 0}%", fg="bright_black")
            count = click.style(f"{current}/{total}", fg="white", bold=True)
            click.echo(f"\r    {bar}  {count} files  {pct}", nl=False)
            _showed_progress = True

    result = await run_indexing(
        config, project_dir, full=full, target_path=target_path,
        log_fn=log_fn, progress_fn=progress_fn,
    )

    if _showed_progress:
        click.echo()  # newline after progress bar

    for err in result.errors:
        click.echo(f"  {CROSS} {warn(f'Error: {err}')}", err=True)

    n_files = len(result.indexed_files)
    detail_parts = []
    if result.deleted_files:
        detail_parts.append(f", pruned {warn(str(len(result.deleted_files)))} deleted")
    if result.skipped_files:
        detail_parts.append(f", skipped {dim(str(len(result.skipped_files)))} non-text")

    click.echo(
        f"  {CHECK} " +
        value(f"Indexed {result.total_chunks:,} chunks") +
        click.style(f" from {n_files:,} file{'s' if n_files != 1 else ''}", fg="white") +
        "".join(detail_parts)
    )


async def _run_serve(config) -> None:
    """Start MCP server."""
    from context_engine.storage.local_backend import LocalBackend
    from context_engine.indexer.embedder import Embedder
    from context_engine.retrieval.retriever import HybridRetriever
    from context_engine.compression.compressor import Compressor
    from context_engine.integration.mcp_server import ContextEngineMCP

    project_name = Path.cwd().name
    storage_base = Path(config.storage_path) / project_name
    backend = LocalBackend(base_path=str(storage_base))
    embedder = Embedder(model_name=config.embedding_model)
    retriever = HybridRetriever(backend=backend, embedder=embedder)
    compressor = Compressor(model=config.compression_model)
    mcp = ContextEngineMCP(
        retriever=retriever, backend=backend, compressor=compressor,
        embedder=embedder, config=config,
    )
    chunk_count = backend._vector_store.count()
    import sys
    print(f"CCE ready · {project_name} · {chunk_count} chunks indexed", file=sys.stderr)
    await mcp.run_stdio()
