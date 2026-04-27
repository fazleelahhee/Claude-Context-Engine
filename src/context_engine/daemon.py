"""Daemon process — orchestrates all modules, manages lifecycle."""
import asyncio
import subprocess
from pathlib import Path

from context_engine.config import Config
from context_engine.event_bus import EventBus
from context_engine.storage.local_backend import LocalBackend
from context_engine.storage.remote_backend import RemoteBackend
from context_engine.indexer.embedder import Embedder
from context_engine.indexer.watcher import FileWatcher
from context_engine.retrieval.retriever import HybridRetriever
from context_engine.compression.compressor import Compressor
from context_engine.integration.mcp_server import ContextEngineMCP
from context_engine.integration.bootstrap import BootstrapBuilder
from context_engine.integration.session_capture import SessionCapture


class Daemon:
    def __init__(self, config: Config, project_dir: str) -> None:
        self._config = config
        self._project_dir = project_dir
        self._project_name = Path(project_dir).name
        self._event_bus = EventBus()
        self._backend = None
        self._watcher = None
        self._mcp = None

    async def start(self) -> None:
        self._backend = await self._create_backend()
        embedder = Embedder(model_name=self._config.embedding_model)
        retriever = HybridRetriever(backend=self._backend, embedder=embedder)
        compressor = Compressor(
            ollama_url="http://localhost:11434",
            model=self._config.compression_model,
            cache=self._backend,
        )
        if self._config.indexer_watch:
            self._watcher = FileWatcher(
                watch_dir=self._project_dir, on_change=self._on_file_change,
                debounce_ms=self._config.indexer_debounce_ms,
                ignore_patterns=self._config.indexer_ignore,
            )
            self._watcher.start()
        self._mcp = ContextEngineMCP(
            retriever=retriever, backend=self._backend, compressor=compressor,
            embedder=embedder, config=self._config,
        )
        await self._mcp.run_stdio()

    async def stop(self) -> None:
        if self._watcher:
            self._watcher.stop()

    async def _create_backend(self):
        if self._config.remote_enabled:
            remote = RemoteBackend(
                host=self._config.remote_host,
                fallback_to_local=self._config.remote_fallback_to_local,
            )
            if await remote.is_reachable():
                return remote
            if not self._config.remote_fallback_to_local:
                raise ConnectionError(f"Remote server {self._config.remote_host} is not reachable")
        storage_base = str(Path(self._config.storage_path) / self._project_name)
        return LocalBackend(base_path=storage_base)

    async def _on_file_change(self, file_path: str) -> None:
        await self._event_bus.emit("file_changed", {"path": file_path})

    async def generate_bootstrap(self) -> str:
        embedder = Embedder(model_name=self._config.embedding_model)
        retriever = HybridRetriever(backend=self._backend, embedder=embedder)
        compressor = Compressor(model=self._config.compression_model, cache=self._backend)
        bootstrap = BootstrapBuilder(max_tokens=self._config.bootstrap_max_tokens)
        chunks = await retriever.retrieve("project overview architecture", top_k=30)
        await compressor.compress(chunks, level=self._config.compression_level)
        try:
            result = subprocess.run(
                ["git", "-C", self._project_dir, "log", "--oneline", "-10"],
                capture_output=True, text=True, timeout=5,
            )
            commits = result.stdout.strip().split("\n") if result.returncode == 0 else []
        except (subprocess.TimeoutExpired, FileNotFoundError):
            commits = []
        return bootstrap.build(project_name=self._project_name, chunks=chunks, recent_commits=commits)
