"""Reusable indexing pipeline — shared by the CLI (`cce index`) and MCP (`reindex`).

This module owns the full index-a-project flow so the CLI and MCP server don't
duplicate logic and can't drift. Callers pass a structured `IndexResult` back so
they can format their own output (click.echo, MCP text response, logs).
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import subprocess

from context_engine.indexer.chunker import Chunker
from context_engine.indexer.embedder import Embedder
from context_engine.indexer.git_indexer import index_commits
from context_engine.indexer.manifest import Manifest
from context_engine.models import GraphNode, GraphEdge, NodeType, EdgeType
from context_engine.storage.local_backend import LocalBackend

log = logging.getLogger(__name__)

# Serialise indexing runs so a watcher-triggered re-index can't race a manual
# `cce index` or MCP `reindex` tool call on the same LanceDB table.
_PIPELINE_LOCKS: dict[str, asyncio.Lock] = {}


def _pipeline_lock(storage_key: str) -> asyncio.Lock:
    lock = _PIPELINE_LOCKS.get(storage_key)
    if lock is None:
        lock = asyncio.Lock()
        _PIPELINE_LOCKS[storage_key] = lock
    return lock

_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx", ".md", ".php"}
_LANGUAGE_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "javascript",
    ".tsx": "typescript",
    ".md": "markdown",
    ".php": "php",
}


@dataclass
class IndexResult:
    indexed_files: list[str] = field(default_factory=list)
    skipped_files: list[str] = field(default_factory=list)
    deleted_files: list[str] = field(default_factory=list)
    total_chunks: int = 0
    errors: list[str] = field(default_factory=list)


def _iter_project_files(
    root: Path, ignore_set: set[str], extensions: set[str]
) -> Iterable[Path]:
    """Yield files under `root` respecting ignore list, skipping symlinks.

    Symlinks are skipped outright to avoid loops; callers who need symlink
    following can resolve them before calling the pipeline.
    """
    seen: set[Path] = set()

    def walk(directory: Path) -> Iterable[Path]:
        try:
            entries = sorted(directory.iterdir())
        except (PermissionError, OSError):
            return
        for entry in entries:
            if entry.name in ignore_set:
                continue
            if entry.is_symlink():
                continue
            try:
                resolved = entry.resolve()
            except (OSError, RuntimeError):
                continue
            if resolved in seen:
                continue
            seen.add(resolved)
            if entry.is_dir():
                yield from walk(entry)
            elif entry.is_file() and entry.suffix in extensions:
                yield entry

    yield from walk(root)


def _safe_read(file_path: Path) -> str | None:
    """Read file as UTF-8 text; return None for binary or unreadable files."""
    try:
        return file_path.read_text(encoding="utf-8", errors="strict")
    except (UnicodeDecodeError, OSError):
        return None


async def run_indexing(
    config,
    project_dir: str | Path,
    *,
    full: bool = False,
    target_path: str | None = None,
    log_fn=None,
) -> IndexResult:
    """Run the indexing pipeline. Returns a structured `IndexResult`.

    `target_path` (optional) restricts indexing to a single file or subtree.
    `full=True` ignores the manifest and re-indexes everything visible.
    `log_fn(msg)` is called for verbose progress output if provided.
    """
    project_dir = Path(project_dir)
    project_name = project_dir.name
    storage_base = Path(config.storage_path) / project_name
    storage_base.mkdir(parents=True, exist_ok=True)

    async with _pipeline_lock(str(storage_base)):
        return await _run_indexing_locked(
            config,
            project_dir,
            storage_base,
            full=full,
            target_path=target_path,
            log_fn=log_fn,
        )


async def _run_indexing_locked(
    config,
    project_dir: Path,
    storage_base: Path,
    *,
    full: bool,
    target_path: str | None,
    log_fn,
) -> IndexResult:
    backend = LocalBackend(base_path=str(storage_base))
    chunker = Chunker()
    manifest = Manifest(manifest_path=storage_base / "manifest.json")
    ignore_set = set(config.indexer_ignore)
    result = IndexResult()

    # Determine the set of files to scan.
    if target_path:
        target = Path(target_path)
        if not target.is_absolute():
            target = project_dir / target
        if target.is_file():
            file_iter = [target] if target.suffix in _EXTENSIONS else []
        elif target.is_dir():
            file_iter = list(_iter_project_files(target, ignore_set, _EXTENSIONS))
        else:
            result.errors.append(f"Target path not found: {target_path}")
            return result
    else:
        file_iter = list(_iter_project_files(project_dir, ignore_set, _EXTENSIONS))

    current_rel_paths: set[str] = set()
    all_chunks: list = []
    all_nodes: list[GraphNode] = []
    all_edges: list[GraphEdge] = []

    for file_path in file_iter:
        rel_path = str(file_path.relative_to(project_dir))
        current_rel_paths.add(rel_path)

        content = _safe_read(file_path)
        if content is None:
            result.skipped_files.append(rel_path)
            if log_fn:
                log_fn(f"  [skip] {rel_path} (binary or unreadable)")
            continue

        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if not full and not manifest.has_changed(rel_path, content_hash):
            if log_fn:
                log_fn(f"  [skip] {rel_path} (unchanged)")
            continue

        language = _LANGUAGE_MAP.get(file_path.suffix, "plaintext")
        t0 = time.monotonic()
        try:
            chunks, imported_modules = chunker.chunk_with_imports(content, file_path=rel_path, language=language)
        except Exception as exc:  # pragma: no cover - defensive
            result.errors.append(f"Chunking failed for {rel_path}: {exc}")
            log.warning("Chunking failed for %s", rel_path, exc_info=exc)
            continue
        elapsed = time.monotonic() - t0
        if log_fn:
            log_fn(f"  [index] {rel_path} — {len(chunks)} chunks ({elapsed:.3f}s)")

        # Deleting a file's old chunks before re-ingesting keeps the vector store
        # consistent when chunk boundaries move between runs.
        await backend.delete_by_file(rel_path)

        file_node = GraphNode(
            id=f"file_{rel_path}",
            node_type=NodeType.FILE,
            name=file_path.name,
            file_path=rel_path,
        )
        all_nodes.append(file_node)

        # Add IMPORTS edges for detected import statements
        for module in imported_modules:
            all_edges.append(
                GraphEdge(
                    source_id=file_node.id,
                    target_id=f"module_{module}",
                    edge_type=EdgeType.IMPORTS,
                )
            )

        for chunk in chunks:
            node_type = (
                NodeType.FUNCTION
                if chunk.chunk_type.value == "function"
                else NodeType.CLASS
            )
            node_name = (
                chunk.content.split("(")[0].split(":")[-1].strip()
                if "(" in chunk.content
                else chunk.id
            )
            all_nodes.append(
                GraphNode(
                    id=chunk.id,
                    node_type=node_type,
                    name=node_name,
                    file_path=rel_path,
                )
            )
            all_edges.append(
                GraphEdge(
                    source_id=file_node.id,
                    target_id=chunk.id,
                    edge_type=EdgeType.DEFINES,
                )
            )
        all_chunks.extend(chunks)
        manifest.update(rel_path, content_hash)
        result.indexed_files.append(rel_path)

    # Index git history on full runs
    if full and not target_path:
        try:
            git_chunks, git_nodes, git_edges = await index_commits(
                project_dir, since_sha=manifest.last_git_sha
            )
            all_chunks.extend(git_chunks)
            all_nodes.extend(git_nodes)
            all_edges.extend(git_edges)
            if git_chunks:
                head_result = await asyncio.to_thread(
                    subprocess.run,
                    ["git", "rev-parse", "HEAD"],
                    cwd=project_dir, capture_output=True, text=True, check=False,
                )
                if head_result.returncode == 0:
                    manifest.last_git_sha = head_result.stdout.strip()
                if log_fn:
                    log_fn(f"  [git] {len(git_chunks)} commit(s) indexed")
        except Exception as exc:
            log.warning("Git history indexing failed: %s", exc)

    if all_chunks:
        # Embedding is where first-run model downloads happen; isolate failures
        # here so we don't write an index with empty vectors.
        embedder = Embedder(model_name=config.embedding_model)
        try:
            embedder.embed(all_chunks)
        except Exception as exc:
            msg = f"Embedding failed: {exc}"
            result.errors.append(msg)
            log.warning(msg, exc_info=exc)
            # Don't ingest; the manifest was already updated in the loop but
            # re-running with `full=True` will fix it.
            return result

        try:
            await backend.ingest(all_chunks, all_nodes, all_edges)
        except Exception as exc:
            msg = f"Backend ingest failed: {exc}"
            result.errors.append(msg)
            log.warning(msg, exc_info=exc)
            return result

        result.total_chunks = len(all_chunks)

    # Prune chunks for files that were in the manifest but no longer on disk.
    # Only meaningful for project-wide runs; skip when a single path was targeted.
    if not target_path:
        previous_rel_paths = set(manifest._entries.keys())  # noqa: SLF001
        removed = previous_rel_paths - current_rel_paths
        for deleted in removed:
            try:
                await backend.delete_by_file(deleted)
                manifest.remove(deleted)
                result.deleted_files.append(deleted)
                if log_fn:
                    log_fn(f"  [delete] {deleted} (no longer on disk)")
            except Exception as exc:  # pragma: no cover - defensive
                result.errors.append(f"Failed to prune {deleted}: {exc}")

    manifest.save()
    return result
