# src/context_engine/cli.py
"""CLI entry point for claude-context-engine."""
import asyncio
from pathlib import Path

import click

from context_engine.config import load_config, PROJECT_CONFIG_NAME


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable detailed logging output")
@click.pass_context
def main(ctx, verbose):
    """claude-context-engine — Local context engine for Claude Code."""
    ctx.ensure_object(dict)
    project_path = Path.cwd() / PROJECT_CONFIG_NAME
    ctx.obj["config"] = load_config(project_path=project_path if project_path.exists() else None)
    ctx.obj["verbose"] = verbose


@main.command()
@click.pass_context
def init(ctx):
    """Initialize context engine for the current project."""
    from context_engine.indexer.git_hooks import install_hooks
    config = ctx.obj["config"]
    project_dir = str(Path.cwd())
    try:
        installed = install_hooks(project_dir)
        click.echo(f"Git hooks installed: {len(installed)} hooks")
    except FileNotFoundError:
        click.echo("No .git directory found — skipping git hooks")
    project_name = Path.cwd().name
    storage_dir = Path(config.storage_path) / project_name
    storage_dir.mkdir(parents=True, exist_ok=True)
    click.echo(f"Storage directory: {storage_dir}")
    click.echo("Running initial index...")
    asyncio.run(_run_index(config, project_dir, full=True))
    click.echo("Initialization complete.")


@main.command()
@click.option("--full", is_flag=True, help="Force full re-index")
@click.option("--path", type=str, default=None, help="Index specific file/directory")
@click.option("--changed-only", is_flag=True, help="Only index changed files")
@click.pass_context
def index(ctx, full, path, changed_only):
    """Index or re-index project files."""
    config = ctx.obj["config"]
    verbose = ctx.obj["verbose"]
    project_dir = path or str(Path.cwd())
    asyncio.run(_run_index(config, project_dir, full=full, verbose=verbose))
    click.echo("Indexing complete.")


@main.command()
@click.pass_context
def status(ctx):
    """Show index status, DB stats, and remote server status."""
    config = ctx.obj["config"]
    verbose = ctx.obj["verbose"]
    click.echo(f"Storage path: {config.storage_path}")
    click.echo(f"Remote enabled: {config.remote_enabled}")
    if config.remote_enabled:
        click.echo(f"Remote host: {config.remote_host}")
    click.echo(f"Compression level: {config.compression_level}")
    click.echo(f"Resource profile: {config.detect_resource_profile()}")
    if verbose:
        storage_path = Path(config.storage_path)
        if storage_path.exists():
            projects = [d for d in storage_path.iterdir() if d.is_dir()]
            click.echo(f"Projects indexed: {len(projects)}")
            for project in projects:
                chunks = list(project.glob("**/*.json"))
                click.echo(f"  {project.name}: {len(chunks)} stored files")
        else:
            click.echo("Storage directory does not exist yet.")


@main.command()
@click.pass_context
def serve(ctx):
    """Start the MCP server + daemon."""
    click.echo("Starting context engine daemon + MCP server...", err=True)
    asyncio.run(_run_serve(ctx.obj["config"]))


@main.command(name="serve-http")
@click.option("--host", default="0.0.0.0", help="Bind address")
@click.option("--port", default=8765, type=int, help="Port to listen on")
@click.pass_context
def serve_http(ctx, host, port):
    """Start the HTTP API server (for remote mode)."""
    from context_engine.serve_http import run_http_server
    run_http_server(config=ctx.obj["config"], host=host, port=port)


@main.command(name="remote-setup")
@click.pass_context
def remote_setup(ctx):
    """Set up context engine on remote server."""
    config = ctx.obj["config"]
    if not config.remote_enabled:
        click.echo("Remote is not enabled in config.")
        return
    click.echo(f"Setting up remote server: {config.remote_host}")
    click.echo("Remote setup not yet implemented.")


async def _run_index(config, project_dir: str, full: bool = False, verbose: bool = False) -> None:
    """Run indexing pipeline."""
    import hashlib
    from context_engine.indexer.chunker import Chunker
    from context_engine.indexer.embedder import Embedder
    from context_engine.indexer.manifest import Manifest
    from context_engine.storage.local_backend import LocalBackend
    from context_engine.storage.remote_backend import RemoteBackend
    from context_engine.models import GraphNode, GraphEdge, NodeType, EdgeType

    project_name = Path(project_dir).name
    storage_base = Path(config.storage_path) / project_name
    storage_base.mkdir(parents=True, exist_ok=True)

    if config.remote_enabled:
        remote = RemoteBackend(host=config.remote_host, fallback_to_local=config.remote_fallback_to_local)
        if await remote.is_reachable():
            backend = remote
            click.echo(f"Using remote backend: {config.remote_host}")
        elif config.remote_fallback_to_local:
            backend = LocalBackend(base_path=str(storage_base))
            click.echo("Remote unreachable, falling back to local")
        else:
            raise ConnectionError(f"Remote {config.remote_host} unreachable and fallback disabled")
    else:
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
    all_nodes = []
    all_edges = []
    ignore_set = set(config.indexer_ignore)

    def _walk_files(root: Path):
        """Walk directory tree, skipping ignored directories early."""
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

    import time
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
    """Start daemon with MCP server."""
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
