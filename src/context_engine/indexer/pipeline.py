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

# Binary / non-text extensions to skip (images, compiled, archives, etc.)
_SKIP_EXTENSIONS = {
    # Images
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".tiff", ".svg",
    # Compiled / bytecode
    ".pyc", ".pyo", ".class", ".o", ".so", ".dylib", ".dll", ".exe", ".wasm",
    # Archives
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar", ".jar", ".war",
    # Data / binary
    ".db", ".sqlite", ".sqlite3", ".bin", ".dat", ".pkl", ".pickle",
    ".parquet", ".arrow", ".lance",
    # Media
    ".mp3", ".mp4", ".wav", ".avi", ".mov", ".flv", ".ogg", ".webm",
    # Fonts
    ".ttf", ".otf", ".woff", ".woff2", ".eot",
    # Documents (non-text)
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    # Package locks (huge, not useful for context)
    ".lock",
    # Source maps
    ".map",
}

# Known extension → language mapping for tree-sitter and chunk metadata.
# Files with unlisted extensions are still indexed as "plaintext".
_LANGUAGE_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "javascript",
    ".tsx": "typescript",
    ".md": "markdown",
    ".php": "php",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "css",
    ".less": "css",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "bash",
    ".rb": "ruby",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".swift": "swift",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".sql": "sql",
    ".graphql": "graphql",
    ".gql": "graphql",
    ".proto": "protobuf",
    ".xml": "xml",
    ".r": "r",
    ".R": "r",
    ".lua": "lua",
    ".ex": "elixir",
    ".exs": "elixir",
    ".erl": "erlang",
    ".hs": "haskell",
    ".scala": "scala",
    ".clj": "clojure",
    ".dart": "dart",
    ".vue": "vue",
    ".svelte": "svelte",
    ".pl": "perl",
    ".pm": "perl",
    ".cs": "csharp",
    ".fs": "fsharp",
    ".zig": "zig",
    ".nim": "nim",
    ".v": "vlang",
    ".tf": "terraform",
    ".hcl": "hcl",
    ".dockerfile": "dockerfile",
}


@dataclass
class IndexResult:
    indexed_files: list[str] = field(default_factory=list)
    skipped_files: list[str] = field(default_factory=list)
    deleted_files: list[str] = field(default_factory=list)
    total_chunks: int = 0
    errors: list[str] = field(default_factory=list)


def _iter_project_files(
    root: Path, ignore_set: set[str], skip_extensions: set[str]
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
            elif entry.is_file() and entry.suffix not in skip_extensions:
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
    progress_fn=None,
) -> IndexResult:
    """Run the indexing pipeline. Returns a structured `IndexResult`.

    `target_path` (optional) restricts indexing to a single file or subtree.
    `full=True` ignores the manifest and re-indexes everything visible.
    `log_fn(msg)` is called for verbose progress output if provided.
    `progress_fn(current, total)` is called after each batch with file counts.
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
            progress_fn=progress_fn,
        )


async def _run_indexing_locked(
    config,
    project_dir: Path,
    storage_base: Path,
    *,
    full: bool,
    target_path: str | None,
    log_fn,
    progress_fn=None,
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
            file_iter = [target] if target.suffix not in _SKIP_EXTENSIONS else []
        elif target.is_dir():
            file_iter = list(_iter_project_files(target, ignore_set, _SKIP_EXTENSIONS))
        else:
            result.errors.append(f"Target path not found: {target_path}")
            return result
    else:
        file_iter = list(_iter_project_files(project_dir, ignore_set, _SKIP_EXTENSIONS))

    current_rel_paths: set[str] = set()
    all_chunks: list = []
    all_nodes: list[GraphNode] = []
    all_edges: list[GraphEdge] = []

    # Read files asynchronously — overlap I/O with processing.
    async def _read_file(fp: Path) -> tuple[Path, str | None]:
        return fp, await asyncio.to_thread(_safe_read, fp)

    # Process files in batches to pipeline I/O with chunking.
    _BATCH = 50
    for batch_start in range(0, len(file_iter), _BATCH):
        batch_paths = file_iter[batch_start:batch_start + _BATCH]

        # Async read all files in this batch concurrently
        read_tasks = [_read_file(fp) for fp in batch_paths]
        read_results = await asyncio.gather(*read_tasks)

        for file_path, content in read_results:
            rel_path = str(file_path.relative_to(project_dir))
            current_rel_paths.add(rel_path)

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
            try:
                chunks, imported_modules = chunker.chunk_with_imports(
                    content, file_path=rel_path, language=language
                )
            except Exception as exc:  # pragma: no cover - defensive
                result.errors.append(f"Chunking failed for {rel_path}: {exc}")
                log.warning("Chunking failed for %s", rel_path, exc_info=exc)
                continue

            await backend.delete_by_file(rel_path)

            file_node = GraphNode(
                id=f"file_{rel_path}",
                node_type=NodeType.FILE,
                name=file_path.name,
                file_path=rel_path,
            )
            all_nodes.append(file_node)

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

        if progress_fn:
            progress_fn(min(batch_start + len(batch_paths), len(file_iter)), len(file_iter))

    # Index git history on full runs (skip for non-git projects)
    _is_git = (Path(project_dir) / ".git").is_dir()
    if full and not target_path and _is_git:
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
