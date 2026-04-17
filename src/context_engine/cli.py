# src/context_engine/cli.py
"""CLI entry point for claude-context-engine."""
import asyncio
import json
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

    entry = {"command": command, "args": ["serve"]}

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
    config = ctx.obj["config"]
    project_dir = Path.cwd()

    try:
        installed = install_hooks(str(project_dir))
        click.echo(f"Git hooks installed: {len(installed)} hooks")
    except FileNotFoundError:
        click.echo("No .git directory found — skipping git hooks")

    project_name = project_dir.name
    storage_dir = Path(config.storage_path) / project_name
    storage_dir.mkdir(parents=True, exist_ok=True)
    click.echo(f"Storage directory: {storage_dir}")

    configured = _configure_mcp(project_dir)
    if configured:
        click.echo("MCP server registered in .mcp.json — restart Claude Code to activate.")
    else:
        click.echo("MCP server already in .mcp.json.")

    click.echo("Running initial index...")
    asyncio.run(_run_index(config, str(project_dir), full=True))
    click.echo("Done. Restart Claude Code if this is your first time running init.")


@main.command()
@click.option("--full", is_flag=True, help="Force full re-index")
@click.option("--path", type=str, default=None, help="Index specific file/directory")
@click.option("--changed-only", is_flag=True, help="Only index changed files")
@click.pass_context
def index(ctx: click.Context, full: bool, path: str | None, changed_only: bool) -> None:
    """Index or re-index project files."""
    config = ctx.obj["config"]
    verbose = ctx.obj["verbose"]
    project_dir = path or str(Path.cwd())
    asyncio.run(_run_index(config, project_dir, full=full, verbose=verbose))
    click.echo("Indexing complete.")


@main.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show index status and config."""
    import json as _json
    config = ctx.obj["config"]
    verbose = ctx.obj["verbose"]
    click.echo(f"Storage path: {config.storage_path}")
    click.echo(f"Compression level: {config.compression_level}")
    click.echo(f"Resource profile: {config.detect_resource_profile()}")

    # Token savings
    project_name = Path.cwd().name
    stats_path = Path(config.storage_path) / project_name / "stats.json"
    if stats_path.exists():
        try:
            stats = _json.loads(stats_path.read_text())
            raw = stats.get("raw_tokens", 0)
            served = stats.get("served_tokens", 0)
            queries = stats.get("queries", 0)
            saved = raw - served
            pct = int(saved / raw * 100) if raw > 0 else 0
            click.echo(f"\nToken savings ({queries} queries):")
            click.echo(f"  Raw tokens:    {raw:,}")
            click.echo(f"  Served tokens: {served:,}")
            click.echo(f"  Saved:         {saved:,} ({pct}%)")
        except (KeyError, _json.JSONDecodeError):
            pass
    else:
        click.echo("\nToken savings: no usage recorded yet (run context_search via MCP)")

    if verbose:
        storage_path = Path(config.storage_path)
        if storage_path.exists():
            projects = [d for d in storage_path.iterdir() if d.is_dir()]
            click.echo(f"\nProjects indexed: {len(projects)}")
            for project in projects:
                chunks = list(project.glob("**/*.json"))
                click.echo(f"  {project.name}: {len(chunks)} stored files")
        else:
            click.echo("Storage directory does not exist yet.")


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

    def _cost_str(tokens: int, price_per_m: float) -> str:
        return f"${tokens / 1_000_000 * price_per_m:.4f}"

    def _print_project(name: str, stats: dict) -> None:
        full_file = stats.get("full_file_tokens", 0)
        served = stats.get("served_tokens", 0)
        queries = stats.get("queries", 0)

        # Primary comparison: full files vs CCE served
        raw = stats.get("raw_tokens", 0)
        # Use full_file_tokens when available, fall back to raw_tokens for old stats
        baseline_val = full_file if full_file > 0 else raw
        saved = baseline_val - served
        pct = int(saved / baseline_val * 100) if baseline_val > 0 else 0

        click.echo(f"  Project:        {name}")
        click.echo(f"  Queries:        {queries:,}")
        click.echo(f"  {'Without CCE:':18s}{baseline_val:>10,} tokens  (full file reads)")
        click.echo(f"  {'With CCE:':18s}{served:>10,} tokens  (chunked + compressed)")
        click.echo(f"  {'Tokens saved:':18s}{saved:>10,} tokens  ({pct}%)")
        click.echo()
        click.echo(f"  Cost impact (input tokens):")
        click.echo(f"    {'Model':<18} {'Without CCE':>12} {'With CCE':>12} {'Saved':>12}")
        click.echo(f"    {'-' * 56}")
        for model, price in [("Haiku", 0.80), ("Sonnet", 3.00), ("Opus", 15.00)]:
            click.echo(
                f"    {model:<18} "
                f"{_cost_str(baseline_val, price):>12} "
                f"{_cost_str(served, price):>12} "
                f"{_cost_str(saved, price):>12}"
            )

    def _json_entry(name: str, stats: dict) -> dict:
        full_file = stats.get("full_file_tokens", 0)
        raw = stats.get("raw_tokens", 0)
        served = stats.get("served_tokens", 0)
        baseline = full_file if full_file > 0 else raw
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
            click.echo("No usage recorded yet.")
            click.echo("Run context_search queries via MCP to start tracking savings.")
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
    total_raw = sum(s.get("raw_tokens", 0) for _, s in reports)
    total_served = sum(s.get("served_tokens", 0) for _, s in reports)
    total_queries = sum(s.get("queries", 0) for _, s in reports)
    total_saved = total_raw - total_served
    total_pct = int(total_saved / total_raw * 100) if total_raw > 0 else 0

    click.echo()
    click.echo("  CCE Token Savings Report")
    click.echo("  " + "=" * 50)
    click.echo()

    for name, stats in reports:
        _print_project(name, stats)
        if len(reports) > 1:
            click.echo("  " + "-" * 50)
            click.echo()

    if len(reports) > 1:
        click.echo(f"  TOTAL across {len(reports)} projects:")
        click.echo(f"    Queries:  {total_queries:,}")
        click.echo(f"    Saved:    {total_saved:,} tokens ({total_pct}%)")
        click.echo()


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


@main.command()
@click.pass_context
def serve(ctx: click.Context) -> None:
    """Start the MCP server (used by Claude Code)."""
    click.echo("Starting context engine MCP server...", err=True)
    asyncio.run(_run_serve(ctx.obj["config"]))


async def _run_index(config, project_dir: str, full: bool = False, verbose: bool = False) -> None:
    """Run indexing pipeline (thin wrapper over `indexer.pipeline.run_indexing`)."""
    from context_engine.indexer.pipeline import run_indexing

    log_fn = (lambda msg: click.echo(msg)) if verbose else None
    result = await run_indexing(config, project_dir, full=full, log_fn=log_fn)
    for err in result.errors:
        click.echo(f"Error: {err}", err=True)
    click.echo(
        f"Indexed {result.total_chunks} chunks from {len(result.indexed_files)} files"
        + (f", pruned {len(result.deleted_files)} deleted" if result.deleted_files else "")
        + (f", skipped {len(result.skipped_files)} non-text" if result.skipped_files else "")
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
    await mcp.run_stdio()
