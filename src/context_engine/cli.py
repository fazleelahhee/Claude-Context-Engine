# src/context_engine/cli.py
"""CLI entry point for claude-context-engine."""
import asyncio
import json
import sys
from pathlib import Path

import click

from context_engine.config import load_config, PROJECT_CONFIG_NAME


def _configure_mcp(project_dir: Path) -> bool:
    """Write MCP server config to .mcp.json in the project directory. Returns True if written."""
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
    mcp_path.write_text(json.dumps(data, indent=2) + "\n")
    return True


@click.group()
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
@click.pass_context
def serve(ctx: click.Context) -> None:
    """Start the MCP server (used by Claude Code)."""
    click.echo("Starting context engine MCP server...", err=True)
    asyncio.run(_run_serve(ctx.obj["config"]))


async def _run_index(config, project_dir: str, full: bool = False, verbose: bool = False) -> None:
    """Run indexing pipeline."""
    import hashlib
    import time
    from context_engine.indexer.chunker import Chunker
    from context_engine.indexer.embedder import Embedder
    from context_engine.indexer.manifest import Manifest
    from context_engine.storage.local_backend import LocalBackend
    from context_engine.models import GraphNode, GraphEdge, NodeType, EdgeType

    project_name = Path(project_dir).name
    storage_base = Path(config.storage_path) / project_name
    storage_base.mkdir(parents=True, exist_ok=True)
    backend = LocalBackend(base_path=str(storage_base))

    chunker = Chunker()
    embedder = Embedder(model_name=config.embedding_model)
    manifest = Manifest(manifest_path=storage_base / "manifest.json")

    extensions = {".py", ".js", ".ts", ".jsx", ".tsx", ".md"}
    language_map = {
        ".py": "python", ".js": "javascript", ".ts": "typescript",
        ".jsx": "javascript", ".tsx": "typescript", ".md": "markdown",
    }

    project_path = Path(project_dir)
    all_chunks = []
    all_nodes: list[GraphNode] = []
    all_edges: list[GraphEdge] = []
    ignore_set = set(config.indexer_ignore)

    def _walk_files(root: Path):
        try:
            entries = sorted(root.iterdir())
        except PermissionError:
            return
        for entry in entries:
            if entry.name in ignore_set:
                continue
            if entry.is_dir():
                yield from _walk_files(entry)
            elif entry.is_file() and entry.suffix in extensions:
                yield entry

    for file_path in _walk_files(project_path):
        rel_path = str(file_path.relative_to(project_path))
        content = file_path.read_text(errors="ignore")
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        if not full and not manifest.has_changed(rel_path, content_hash):
            if verbose:
                click.echo(f"  [skip] {rel_path} (unchanged)")
            continue
        language = language_map.get(file_path.suffix, "plaintext")
        t0 = time.monotonic()
        chunks = chunker.chunk(content, file_path=rel_path, language=language)
        elapsed = time.monotonic() - t0
        if verbose:
            click.echo(f"  [index] {rel_path} — {len(chunks)} chunks ({elapsed:.3f}s)")
        file_node = GraphNode(
            id=f"file_{rel_path}", node_type=NodeType.FILE,
            name=file_path.name, file_path=rel_path,
        )
        all_nodes.append(file_node)
        for chunk in chunks:
            node = GraphNode(
                id=chunk.id,
                node_type=NodeType.FUNCTION if chunk.chunk_type.value == "function" else NodeType.CLASS,
                name=chunk.content.split("(")[0].split(":")[-1].strip() if "(" in chunk.content else chunk.id,
                file_path=rel_path,
            )
            all_nodes.append(node)
            all_edges.append(GraphEdge(
                source_id=file_node.id, target_id=chunk.id, edge_type=EdgeType.DEFINES,
            ))
        all_chunks.extend(chunks)
        manifest.update(rel_path, content_hash)

    if all_chunks:
        embedder.embed(all_chunks)
        await backend.ingest(all_chunks, all_nodes, all_edges)
    manifest.save()
    click.echo(f"Indexed {len(all_chunks)} chunks from {len(set(c.file_path for c in all_chunks))} files")


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
