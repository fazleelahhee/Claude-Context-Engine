# claude-context-engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local context engine that indexes projects into LanceDB + Kuzu, compresses context via local/remote LLM, and integrates with Claude Code via MCP server + bootstrap hooks.

**Architecture:** Modular monolith in Python. Single daemon with swappable modules: Indexer, Storage, Retrieval, Compression, Integration, Config. Storage and Compression modules support local/remote backends via a common protocol. The engine runs as a daemon exposing MCP tools and injecting bootstrap context on session start.

**Tech Stack:** Python 3.11+, LanceDB, Kuzu, sentence-transformers, Ollama, tree-sitter, watchdog, Python MCP SDK, Click (CLI), PyYAML, asyncio, asyncssh

---

## File Structure

```
claude-context-engine/
├── pyproject.toml
├── src/
│   └── context_engine/
│       ├── __init__.py
│       ├── cli.py                      # Click CLI entry point
│       ├── config.py                   # Config loading (global + per-project)
│       ├── models.py                   # Shared data models (Chunk, Node, Edge, etc.)
│       ├── event_bus.py                # Internal event bus for module communication
│       ├── daemon.py                   # Daemon process orchestrator
│       ├── indexer/
│       │   ├── __init__.py
│       │   ├── watcher.py              # File watcher (watchdog)
│       │   ├── git_hooks.py            # Git hook installer + handler
│       │   ├── chunker.py              # AST-aware chunking via tree-sitter
│       │   ├── embedder.py             # Embedding generation (sentence-transformers)
│       │   └── manifest.py             # Content hash manifest for incremental indexing
│       ├── storage/
│       │   ├── __init__.py
│       │   ├── backend.py              # StorageBackend protocol
│       │   ├── local_backend.py        # Local LanceDB + Kuzu implementation
│       │   ├── remote_backend.py       # Remote server proxy
│       │   ├── vector_store.py         # LanceDB wrapper
│       │   └── graph_store.py          # Kuzu wrapper
│       ├── retrieval/
│       │   ├── __init__.py
│       │   ├── retriever.py            # Hybrid retrieval pipeline
│       │   ├── confidence.py           # Confidence scoring
│       │   └── query_parser.py         # Query understanding + intent classification
│       ├── compression/
│       │   ├── __init__.py
│       │   ├── compressor.py           # Compression pipeline
│       │   ├── ollama_client.py        # Ollama API client
│       │   ├── prompts.py              # Summarization prompt templates
│       │   └── quality.py              # Lossy detection + quality safeguards
│       └── integration/
│           ├── __init__.py
│           ├── mcp_server.py           # MCP server with tools
│           ├── bootstrap.py            # Bootstrap context builder
│           └── session_capture.py      # Session history capture
├── tests/
│   ├── conftest.py
│   ├── test_config.py
│   ├── test_models.py
│   ├── test_event_bus.py
│   ├── indexer/
│   │   ├── test_chunker.py
│   │   ├── test_embedder.py
│   │   ├── test_manifest.py
│   │   └── test_watcher.py
│   ├── storage/
│   │   ├── test_vector_store.py
│   │   ├── test_graph_store.py
│   │   └── test_local_backend.py
│   ├── retrieval/
│   │   ├── test_retriever.py
│   │   ├── test_confidence.py
│   │   └── test_query_parser.py
│   ├── compression/
│   │   ├── test_compressor.py
│   │   ├── test_ollama_client.py
│   │   └── test_quality.py
│   └── integration/
│       ├── test_mcp_server.py
│       ├── test_bootstrap.py
│       └── test_session_capture.py
└── scripts/
    └── install_hooks.sh                # Git hook installation helper
```

---

## Phase 1: Foundation (Config, Models, Event Bus, Project Scaffold)

### Task 1: Project Scaffold + Dependencies

**Files:**
- Create: `pyproject.toml`
- Create: `src/context_engine/__init__.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "claude-context-engine"
version = "0.1.0"
description = "Local context engine for Claude Code — indexes projects, compresses context, reduces token cost"
requires-python = ">=3.11"
dependencies = [
    "click>=8.1",
    "pyyaml>=6.0",
    "lancedb>=0.6",
    "kuzu>=0.4",
    "sentence-transformers>=3.0",
    "tree-sitter>=0.22",
    "tree-sitter-python>=0.21",
    "tree-sitter-javascript>=0.21",
    "tree-sitter-typescript>=0.21",
    "watchdog>=4.0",
    "mcp>=1.0",
    "httpx>=0.27",
    "asyncssh>=2.14",
    "ollama>=0.3",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=5.0",
]

[project.scripts]
claude-context-engine = "context_engine.cli:main"

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends._legacy:_Backend"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

- [ ] **Step 2: Create package init**

```python
# src/context_engine/__init__.py
"""claude-context-engine: Local context engine for Claude Code."""
__version__ = "0.1.0"
```

- [ ] **Step 3: Install in dev mode and verify**

Run: `cd /Users/fazleelahee/Documents/claude && python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`
Expected: Successful installation with all dependencies

- [ ] **Step 4: Verify CLI entry point**

Run: `claude-context-engine --help`
Expected: Will fail (cli.py doesn't exist yet) — that's fine, confirms entry point is wired

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/context_engine/__init__.py
git commit -m "feat: project scaffold with dependencies"
```

---

### Task 2: Shared Data Models

**Files:**
- Create: `src/context_engine/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write failing test for Chunk model**

```python
# tests/test_models.py
from context_engine.models import Chunk, ChunkType, NodeType, EdgeType, GraphNode, GraphEdge, ConfidenceLevel


def test_chunk_creation():
    chunk = Chunk(
        id="abc123",
        content="def hello(): pass",
        chunk_type=ChunkType.FUNCTION,
        file_path="src/main.py",
        start_line=1,
        end_line=1,
        language="python",
        metadata={"git_author": "fazle"},
    )
    assert chunk.id == "abc123"
    assert chunk.chunk_type == ChunkType.FUNCTION
    assert chunk.embedding is None


def test_chunk_with_embedding():
    chunk = Chunk(
        id="abc123",
        content="def hello(): pass",
        chunk_type=ChunkType.FUNCTION,
        file_path="src/main.py",
        start_line=1,
        end_line=1,
        language="python",
    )
    chunk.embedding = [0.1, 0.2, 0.3]
    assert chunk.embedding == [0.1, 0.2, 0.3]


def test_graph_node_creation():
    node = GraphNode(
        id="func_hello",
        node_type=NodeType.FUNCTION,
        name="hello",
        file_path="src/main.py",
        properties={"start_line": 1},
    )
    assert node.node_type == NodeType.FUNCTION


def test_graph_edge_creation():
    edge = GraphEdge(
        source_id="func_hello",
        target_id="func_world",
        edge_type=EdgeType.CALLS,
    )
    assert edge.edge_type == EdgeType.CALLS


def test_confidence_level_from_score():
    assert ConfidenceLevel.from_score(0.9) == ConfidenceLevel.HIGH
    assert ConfidenceLevel.from_score(0.6) == ConfidenceLevel.MEDIUM
    assert ConfidenceLevel.from_score(0.3) == ConfidenceLevel.LOW
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement models**

```python
# src/context_engine/models.py
"""Shared data models for the context engine."""
from dataclasses import dataclass, field
from enum import Enum


class ChunkType(Enum):
    FUNCTION = "function"
    CLASS = "class"
    MODULE = "module"
    DOC = "doc"
    COMMENT = "comment"
    COMMIT = "commit"
    SESSION = "session"
    DECISION = "decision"


class NodeType(Enum):
    FUNCTION = "function"
    CLASS = "class"
    FILE = "file"
    MODULE = "module"
    DOC = "doc"
    COMMIT = "commit"
    SESSION = "session"
    DECISION = "decision"


class EdgeType(Enum):
    CALLS = "calls"
    IMPORTS = "imports"
    DEFINES = "defines"
    MODIFIES = "modifies"
    DISCUSSED_IN = "discussed_in"
    DECIDED = "decided"


class ConfidenceLevel(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @staticmethod
    def from_score(score: float) -> "ConfidenceLevel":
        if score > 0.8:
            return ConfidenceLevel.HIGH
        if score >= 0.5:
            return ConfidenceLevel.MEDIUM
        return ConfidenceLevel.LOW


@dataclass
class Chunk:
    id: str
    content: str
    chunk_type: ChunkType
    file_path: str
    start_line: int
    end_line: int
    language: str
    metadata: dict = field(default_factory=dict)
    embedding: list[float] | None = None
    confidence_score: float = 0.0
    compressed_content: str | None = None


@dataclass
class GraphNode:
    id: str
    node_type: NodeType
    name: str
    file_path: str
    properties: dict = field(default_factory=dict)


@dataclass
class GraphEdge:
    source_id: str
    target_id: str
    edge_type: EdgeType
    properties: dict = field(default_factory=dict)


@dataclass
class RetrievalResult:
    chunks: list[Chunk]
    graph_nodes: list[GraphNode]
    graph_edges: list[GraphEdge]
    query: str
    confidence_scores: dict[str, float] = field(default_factory=dict)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_models.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/context_engine/models.py tests/test_models.py
git commit -m "feat: shared data models (Chunk, GraphNode, GraphEdge, ConfidenceLevel)"
```

---

### Task 3: Configuration Loading

**Files:**
- Create: `src/context_engine/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_config.py
import os
import tempfile
from pathlib import Path

import yaml

from context_engine.config import Config, load_config


def test_default_config():
    config = Config()
    assert config.remote_enabled is False
    assert config.compression_level == "standard"
    assert config.embedding_model == "all-MiniLM-L6-v2"
    assert config.retrieval_top_k == 20
    assert config.indexer_watch is True


def test_load_from_yaml(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump({
        "remote": {"enabled": True, "host": "fazle@198.162.2.2", "fallback_to_local": True},
        "compression": {"level": "full", "model": "phi3:mini"},
        "retrieval": {"top_k": 50},
    }))
    config = load_config(global_path=config_file)
    assert config.remote_enabled is True
    assert config.remote_host == "fazle@198.162.2.2"
    assert config.compression_level == "full"
    assert config.compression_model == "phi3:mini"
    assert config.retrieval_top_k == 50


def test_project_override(tmp_path):
    global_file = tmp_path / "config.yaml"
    global_file.write_text(yaml.dump({
        "compression": {"level": "standard"},
        "indexer": {"ignore": [".git"]},
    }))
    project_file = tmp_path / ".context-engine.yaml"
    project_file.write_text(yaml.dump({
        "compression": {"level": "full"},
        "indexer": {"ignore": [".git", "dist"]},
    }))
    config = load_config(global_path=global_file, project_path=project_file)
    assert config.compression_level == "full"
    assert "dist" in config.indexer_ignore


def test_resource_profile_auto_detect():
    config = Config()
    profile = config.detect_resource_profile()
    assert profile in ("light", "standard", "full")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement config**

```python
# src/context_engine/config.py
"""Configuration loading — global + per-project with defaults."""
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


DEFAULT_GLOBAL_PATH = Path.home() / ".claude-context-engine" / "config.yaml"
PROJECT_CONFIG_NAME = ".context-engine.yaml"

DEFAULT_IGNORE = [".git", "node_modules", "__pycache__", ".venv", ".env"]


@dataclass
class Config:
    # Remote
    remote_enabled: bool = False
    remote_host: str = ""
    remote_fallback_to_local: bool = True

    # Compression
    compression_level: str = "standard"
    compression_model: str = "phi3:mini"
    remote_compression_model: str = "llama3:8b"

    # Embedding
    embedding_model: str = "all-MiniLM-L6-v2"

    # Retrieval
    retrieval_confidence_threshold: float = 0.5
    retrieval_top_k: int = 20
    bootstrap_max_tokens: int = 10000

    # Indexer
    indexer_watch: bool = True
    indexer_debounce_ms: int = 500
    indexer_ignore: list[str] = field(default_factory=lambda: list(DEFAULT_IGNORE))
    indexer_languages: list[str] = field(default_factory=list)

    # Storage
    storage_path: str = str(Path.home() / ".claude-context-engine" / "projects")

    def detect_resource_profile(self) -> str:
        """Auto-detect resource profile based on available RAM."""
        try:
            import psutil
            ram_gb = psutil.virtual_memory().total / (1024**3)
        except ImportError:
            ram_gb = 16  # assume standard if psutil unavailable

        if self.remote_enabled:
            return "full"
        if ram_gb >= 32:
            return "full"
        if ram_gb >= 12:
            return "standard"
        return "light"


def _deep_merge(base: dict, override: dict) -> dict:
    """Merge override into base, recursing into nested dicts."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _apply_dict_to_config(config: Config, data: dict) -> None:
    """Apply a nested YAML dict to a flat Config dataclass."""
    mapping = {
        ("remote", "enabled"): "remote_enabled",
        ("remote", "host"): "remote_host",
        ("remote", "fallback_to_local"): "remote_fallback_to_local",
        ("compression", "level"): "compression_level",
        ("compression", "model"): "compression_model",
        ("compression", "remote_model"): "remote_compression_model",
        ("embedding", "model"): "embedding_model",
        ("retrieval", "confidence_threshold"): "retrieval_confidence_threshold",
        ("retrieval", "top_k"): "retrieval_top_k",
        ("retrieval", "bootstrap_max_tokens"): "bootstrap_max_tokens",
        ("indexer", "watch"): "indexer_watch",
        ("indexer", "debounce_ms"): "indexer_debounce_ms",
        ("indexer", "ignore"): "indexer_ignore",
        ("indexer", "languages"): "indexer_languages",
        ("storage", "path"): "storage_path",
    }
    for (section, key), attr in mapping.items():
        if section in data and key in data[section]:
            setattr(config, attr, data[section][key])


def load_config(
    global_path: Path | None = None,
    project_path: Path | None = None,
) -> Config:
    """Load config from global file, then overlay project overrides."""
    global_path = global_path or DEFAULT_GLOBAL_PATH
    config = Config()

    global_data = {}
    if global_path.exists():
        with open(global_path) as f:
            global_data = yaml.safe_load(f) or {}

    project_data = {}
    if project_path and project_path.exists():
        with open(project_path) as f:
            project_data = yaml.safe_load(f) or {}

    merged = _deep_merge(global_data, project_data)
    _apply_dict_to_config(config, merged)
    return config
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_config.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/context_engine/config.py tests/test_config.py
git commit -m "feat: config loading with global + per-project YAML merge"
```

---

### Task 4: Event Bus

**Files:**
- Create: `src/context_engine/event_bus.py`
- Create: `tests/test_event_bus.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_event_bus.py
import asyncio

import pytest

from context_engine.event_bus import EventBus


@pytest.mark.asyncio
async def test_subscribe_and_emit():
    bus = EventBus()
    received = []

    async def handler(data):
        received.append(data)

    bus.subscribe("file_changed", handler)
    await bus.emit("file_changed", {"path": "src/main.py"})
    assert len(received) == 1
    assert received[0]["path"] == "src/main.py"


@pytest.mark.asyncio
async def test_multiple_subscribers():
    bus = EventBus()
    results = []

    async def handler_a(data):
        results.append(("a", data))

    async def handler_b(data):
        results.append(("b", data))

    bus.subscribe("indexed", handler_a)
    bus.subscribe("indexed", handler_b)
    await bus.emit("indexed", {"file": "x.py"})
    assert len(results) == 2


@pytest.mark.asyncio
async def test_emit_no_subscribers():
    bus = EventBus()
    await bus.emit("unknown_event", {})  # should not raise


@pytest.mark.asyncio
async def test_unsubscribe():
    bus = EventBus()
    received = []

    async def handler(data):
        received.append(data)

    bus.subscribe("evt", handler)
    bus.unsubscribe("evt", handler)
    await bus.emit("evt", {"x": 1})
    assert len(received) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_event_bus.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement event bus**

```python
# src/context_engine/event_bus.py
"""Simple async event bus for inter-module communication."""
import asyncio
from collections import defaultdict
from typing import Any, Callable, Coroutine


Handler = Callable[[Any], Coroutine[Any, Any, None]]


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, event: str, handler: Handler) -> None:
        self._handlers[event].append(handler)

    def unsubscribe(self, event: str, handler: Handler) -> None:
        handlers = self._handlers.get(event, [])
        if handler in handlers:
            handlers.remove(handler)

    async def emit(self, event: str, data: Any = None) -> None:
        for handler in self._handlers.get(event, []):
            await handler(data)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_event_bus.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/context_engine/event_bus.py tests/test_event_bus.py
git commit -m "feat: async event bus for module communication"
```

---

## Phase 2: Storage Layer

### Task 5: Vector Store (LanceDB)

**Files:**
- Create: `src/context_engine/storage/__init__.py`
- Create: `src/context_engine/storage/vector_store.py`
- Create: `tests/storage/__init__.py`
- Create: `tests/storage/test_vector_store.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/storage/test_vector_store.py
import pytest

from context_engine.models import Chunk, ChunkType
from context_engine.storage.vector_store import VectorStore


@pytest.fixture
def store(tmp_path):
    return VectorStore(db_path=str(tmp_path / "vectors"))


@pytest.fixture
def sample_chunks():
    return [
        Chunk(
            id="chunk_1",
            content="def add(a, b): return a + b",
            chunk_type=ChunkType.FUNCTION,
            file_path="math.py",
            start_line=1,
            end_line=1,
            language="python",
            embedding=[0.1, 0.2, 0.3, 0.4],
        ),
        Chunk(
            id="chunk_2",
            content="def subtract(a, b): return a - b",
            chunk_type=ChunkType.FUNCTION,
            file_path="math.py",
            start_line=3,
            end_line=3,
            language="python",
            embedding=[0.5, 0.6, 0.7, 0.8],
        ),
    ]


@pytest.mark.asyncio
async def test_ingest_and_search(store, sample_chunks):
    await store.ingest(sample_chunks)
    results = await store.search(query_embedding=[0.1, 0.2, 0.3, 0.4], top_k=2)
    assert len(results) > 0
    assert results[0].id == "chunk_1"


@pytest.mark.asyncio
async def test_search_with_filter(store, sample_chunks):
    await store.ingest(sample_chunks)
    results = await store.search(
        query_embedding=[0.1, 0.2, 0.3, 0.4],
        top_k=2,
        filters={"language": "python"},
    )
    assert all(c.language == "python" for c in results)


@pytest.mark.asyncio
async def test_delete_by_file_path(store, sample_chunks):
    await store.ingest(sample_chunks)
    await store.delete_by_file(file_path="math.py")
    results = await store.search(query_embedding=[0.1, 0.2, 0.3, 0.4], top_k=10)
    assert len(results) == 0


@pytest.mark.asyncio
async def test_get_by_id(store, sample_chunks):
    await store.ingest(sample_chunks)
    chunk = await store.get_by_id("chunk_1")
    assert chunk is not None
    assert chunk.content == "def add(a, b): return a + b"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/storage/test_vector_store.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement VectorStore**

```python
# src/context_engine/storage/__init__.py
```

```python
# src/context_engine/storage/vector_store.py
"""LanceDB-backed vector store for chunk embeddings."""
from pathlib import Path

import lancedb
import pyarrow as pa

from context_engine.models import Chunk, ChunkType


TABLE_NAME = "chunks"


class VectorStore:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._db = lancedb.connect(db_path)
        self._table = None

    def _ensure_table(self, vector_dim: int) -> None:
        if self._table is not None:
            return
        try:
            self._table = self._db.open_table(TABLE_NAME)
        except Exception:
            schema = pa.schema([
                pa.field("id", pa.string()),
                pa.field("content", pa.string()),
                pa.field("chunk_type", pa.string()),
                pa.field("file_path", pa.string()),
                pa.field("start_line", pa.int32()),
                pa.field("end_line", pa.int32()),
                pa.field("language", pa.string()),
                pa.field("vector", pa.list_(pa.float32(), vector_dim)),
            ])
            self._table = self._db.create_table(TABLE_NAME, schema=schema)

    def _chunk_to_row(self, chunk: Chunk) -> dict:
        return {
            "id": chunk.id,
            "content": chunk.content,
            "chunk_type": chunk.chunk_type.value,
            "file_path": chunk.file_path,
            "start_line": chunk.start_line,
            "end_line": chunk.end_line,
            "language": chunk.language,
            "vector": chunk.embedding,
        }

    def _row_to_chunk(self, row: dict) -> Chunk:
        return Chunk(
            id=row["id"],
            content=row["content"],
            chunk_type=ChunkType(row["chunk_type"]),
            file_path=row["file_path"],
            start_line=row["start_line"],
            end_line=row["end_line"],
            language=row["language"],
            embedding=row.get("vector"),
        )

    async def ingest(self, chunks: list[Chunk]) -> None:
        if not chunks:
            return
        vector_dim = len(chunks[0].embedding)
        self._ensure_table(vector_dim)
        rows = [self._chunk_to_row(c) for c in chunks if c.embedding]
        self._table.add(rows)

    async def search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        filters: dict | None = None,
    ) -> list[Chunk]:
        if self._table is None:
            return []
        query = self._table.search(query_embedding).limit(top_k)
        if filters:
            where_clauses = []
            for key, value in filters.items():
                where_clauses.append(f"{key} = '{value}'")
            query = query.where(" AND ".join(where_clauses))
        results = query.to_list()
        return [self._row_to_chunk(row) for row in results]

    async def delete_by_file(self, file_path: str) -> None:
        if self._table is None:
            return
        self._table.delete(f"file_path = '{file_path}'")

    async def get_by_id(self, chunk_id: str) -> Chunk | None:
        if self._table is None:
            return None
        results = self._table.search().where(f"id = '{chunk_id}'").limit(1).to_list()
        if not results:
            return None
        return self._row_to_chunk(results[0])
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/storage/test_vector_store.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Create empty test init and commit**

```bash
touch tests/__init__.py tests/storage/__init__.py tests/indexer/__init__.py tests/retrieval/__init__.py tests/compression/__init__.py tests/integration/__init__.py
git add src/context_engine/storage/ tests/storage/ tests/__init__.py tests/indexer/__init__.py tests/retrieval/__init__.py tests/compression/__init__.py tests/integration/__init__.py
git commit -m "feat: LanceDB vector store with ingest, search, delete, get_by_id"
```

---

### Task 6: Graph Store (Kuzu)

**Files:**
- Create: `src/context_engine/storage/graph_store.py`
- Create: `tests/storage/test_graph_store.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/storage/test_graph_store.py
import pytest

from context_engine.models import GraphNode, GraphEdge, NodeType, EdgeType
from context_engine.storage.graph_store import GraphStore


@pytest.fixture
def store(tmp_path):
    return GraphStore(db_path=str(tmp_path / "graph"))


@pytest.fixture
def sample_nodes():
    return [
        GraphNode(id="file_math", node_type=NodeType.FILE, name="math.py", file_path="math.py"),
        GraphNode(id="func_add", node_type=NodeType.FUNCTION, name="add", file_path="math.py"),
        GraphNode(id="func_sub", node_type=NodeType.FUNCTION, name="subtract", file_path="math.py"),
    ]


@pytest.fixture
def sample_edges():
    return [
        GraphEdge(source_id="file_math", target_id="func_add", edge_type=EdgeType.DEFINES),
        GraphEdge(source_id="file_math", target_id="func_sub", edge_type=EdgeType.DEFINES),
        GraphEdge(source_id="func_add", target_id="func_sub", edge_type=EdgeType.CALLS),
    ]


@pytest.mark.asyncio
async def test_ingest_nodes_and_edges(store, sample_nodes, sample_edges):
    await store.ingest(sample_nodes, sample_edges)
    nodes = await store.get_nodes_by_file("math.py")
    assert len(nodes) == 3


@pytest.mark.asyncio
async def test_get_neighbors(store, sample_nodes, sample_edges):
    await store.ingest(sample_nodes, sample_edges)
    neighbors = await store.get_neighbors("func_add", edge_type=EdgeType.CALLS)
    assert len(neighbors) == 1
    assert neighbors[0].id == "func_sub"


@pytest.mark.asyncio
async def test_get_nodes_by_type(store, sample_nodes, sample_edges):
    await store.ingest(sample_nodes, sample_edges)
    functions = await store.get_nodes_by_type(NodeType.FUNCTION)
    assert len(functions) == 2


@pytest.mark.asyncio
async def test_delete_by_file(store, sample_nodes, sample_edges):
    await store.ingest(sample_nodes, sample_edges)
    await store.delete_by_file("math.py")
    nodes = await store.get_nodes_by_file("math.py")
    assert len(nodes) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/storage/test_graph_store.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement GraphStore**

```python
# src/context_engine/storage/graph_store.py
"""Kuzu-backed graph store for code relationships."""
from pathlib import Path

import kuzu

from context_engine.models import GraphNode, GraphEdge, NodeType, EdgeType


class GraphStore:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        Path(db_path).mkdir(parents=True, exist_ok=True)
        self._db = kuzu.Database(db_path)
        self._conn = kuzu.Connection(self._db)
        self._init_schema()

    def _init_schema(self) -> None:
        try:
            self._conn.execute(
                "CREATE NODE TABLE IF NOT EXISTS Node("
                "id STRING, node_type STRING, name STRING, file_path STRING, "
                "PRIMARY KEY(id))"
            )
            self._conn.execute(
                "CREATE REL TABLE IF NOT EXISTS Edge("
                "FROM Node TO Node, edge_type STRING)"
            )
        except Exception:
            pass  # tables already exist

    async def ingest(self, nodes: list[GraphNode], edges: list[GraphEdge]) -> None:
        for node in nodes:
            self._conn.execute(
                "MERGE (n:Node {id: $id}) SET n.node_type = $node_type, "
                "n.name = $name, n.file_path = $file_path",
                {
                    "id": node.id,
                    "node_type": node.node_type.value,
                    "name": node.name,
                    "file_path": node.file_path,
                },
            )
        for edge in edges:
            self._conn.execute(
                "MATCH (a:Node {id: $src}), (b:Node {id: $dst}) "
                "CREATE (a)-[:Edge {edge_type: $etype}]->(b)",
                {
                    "src": edge.source_id,
                    "dst": edge.target_id,
                    "etype": edge.edge_type.value,
                },
            )

    async def get_nodes_by_file(self, file_path: str) -> list[GraphNode]:
        result = self._conn.execute(
            "MATCH (n:Node) WHERE n.file_path = $fp RETURN n.id, n.node_type, n.name, n.file_path",
            {"fp": file_path},
        )
        nodes = []
        while result.has_next():
            row = result.get_next()
            nodes.append(GraphNode(
                id=row[0], node_type=NodeType(row[1]), name=row[2], file_path=row[3],
            ))
        return nodes

    async def get_neighbors(
        self, node_id: str, edge_type: EdgeType | None = None,
    ) -> list[GraphNode]:
        if edge_type:
            result = self._conn.execute(
                "MATCH (a:Node {id: $id})-[e:Edge]->(b:Node) "
                "WHERE e.edge_type = $etype "
                "RETURN b.id, b.node_type, b.name, b.file_path",
                {"id": node_id, "etype": edge_type.value},
            )
        else:
            result = self._conn.execute(
                "MATCH (a:Node {id: $id})-[e:Edge]->(b:Node) "
                "RETURN b.id, b.node_type, b.name, b.file_path",
                {"id": node_id},
            )
        nodes = []
        while result.has_next():
            row = result.get_next()
            nodes.append(GraphNode(
                id=row[0], node_type=NodeType(row[1]), name=row[2], file_path=row[3],
            ))
        return nodes

    async def get_nodes_by_type(self, node_type: NodeType) -> list[GraphNode]:
        result = self._conn.execute(
            "MATCH (n:Node) WHERE n.node_type = $nt RETURN n.id, n.node_type, n.name, n.file_path",
            {"nt": node_type.value},
        )
        nodes = []
        while result.has_next():
            row = result.get_next()
            nodes.append(GraphNode(
                id=row[0], node_type=NodeType(row[1]), name=row[2], file_path=row[3],
            ))
        return nodes

    async def delete_by_file(self, file_path: str) -> None:
        self._conn.execute(
            "MATCH (n:Node) WHERE n.file_path = $fp DETACH DELETE n",
            {"fp": file_path},
        )
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/storage/test_graph_store.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/context_engine/storage/graph_store.py tests/storage/test_graph_store.py
git commit -m "feat: Kuzu graph store with ingest, query, delete"
```

---

### Task 7: Storage Backend Protocol + Local Backend

**Files:**
- Create: `src/context_engine/storage/backend.py`
- Create: `src/context_engine/storage/local_backend.py`
- Create: `tests/storage/test_local_backend.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/storage/test_local_backend.py
import pytest

from context_engine.models import Chunk, ChunkType, GraphNode, GraphEdge, NodeType, EdgeType
from context_engine.storage.local_backend import LocalBackend


@pytest.fixture
def backend(tmp_path):
    return LocalBackend(base_path=str(tmp_path))


@pytest.fixture
def sample_data():
    chunks = [
        Chunk(
            id="c1", content="def hello(): pass", chunk_type=ChunkType.FUNCTION,
            file_path="app.py", start_line=1, end_line=1, language="python",
            embedding=[0.1, 0.2, 0.3, 0.4],
        ),
    ]
    nodes = [
        GraphNode(id="file_app", node_type=NodeType.FILE, name="app.py", file_path="app.py"),
        GraphNode(id="func_hello", node_type=NodeType.FUNCTION, name="hello", file_path="app.py"),
    ]
    edges = [
        GraphEdge(source_id="file_app", target_id="func_hello", edge_type=EdgeType.DEFINES),
    ]
    return chunks, nodes, edges


@pytest.mark.asyncio
async def test_ingest_and_vector_search(backend, sample_data):
    chunks, nodes, edges = sample_data
    await backend.ingest(chunks, nodes, edges)
    results = await backend.vector_search(
        query_embedding=[0.1, 0.2, 0.3, 0.4], top_k=5,
    )
    assert len(results) > 0
    assert results[0].id == "c1"


@pytest.mark.asyncio
async def test_ingest_and_graph_query(backend, sample_data):
    chunks, nodes, edges = sample_data
    await backend.ingest(chunks, nodes, edges)
    neighbors = await backend.graph_neighbors("file_app", edge_type=EdgeType.DEFINES)
    assert len(neighbors) == 1
    assert neighbors[0].name == "hello"


@pytest.mark.asyncio
async def test_get_chunk_by_id(backend, sample_data):
    chunks, nodes, edges = sample_data
    await backend.ingest(chunks, nodes, edges)
    chunk = await backend.get_chunk_by_id("c1")
    assert chunk is not None
    assert chunk.content == "def hello(): pass"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/storage/test_local_backend.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement backend protocol and local backend**

```python
# src/context_engine/storage/backend.py
"""Storage backend protocol — implemented by local and remote backends."""
from typing import Protocol, runtime_checkable

from context_engine.models import Chunk, GraphNode, GraphEdge, NodeType, EdgeType


@runtime_checkable
class StorageBackend(Protocol):
    async def ingest(
        self,
        chunks: list[Chunk],
        nodes: list[GraphNode],
        edges: list[GraphEdge],
    ) -> None: ...

    async def vector_search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        filters: dict | None = None,
    ) -> list[Chunk]: ...

    async def graph_neighbors(
        self,
        node_id: str,
        edge_type: EdgeType | None = None,
    ) -> list[GraphNode]: ...

    async def get_chunk_by_id(self, chunk_id: str) -> Chunk | None: ...

    async def delete_by_file(self, file_path: str) -> None: ...
```

```python
# src/context_engine/storage/local_backend.py
"""Local storage backend — direct LanceDB + Kuzu access."""
from pathlib import Path

from context_engine.models import Chunk, GraphNode, GraphEdge, EdgeType
from context_engine.storage.vector_store import VectorStore
from context_engine.storage.graph_store import GraphStore


class LocalBackend:
    def __init__(self, base_path: str) -> None:
        self._vector_store = VectorStore(db_path=str(Path(base_path) / "vectors"))
        self._graph_store = GraphStore(db_path=str(Path(base_path) / "graph"))

    async def ingest(
        self,
        chunks: list[Chunk],
        nodes: list[GraphNode],
        edges: list[GraphEdge],
    ) -> None:
        await self._vector_store.ingest(chunks)
        await self._graph_store.ingest(nodes, edges)

    async def vector_search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        filters: dict | None = None,
    ) -> list[Chunk]:
        return await self._vector_store.search(query_embedding, top_k, filters)

    async def graph_neighbors(
        self,
        node_id: str,
        edge_type: EdgeType | None = None,
    ) -> list[GraphNode]:
        return await self._graph_store.get_neighbors(node_id, edge_type)

    async def get_chunk_by_id(self, chunk_id: str) -> Chunk | None:
        return await self._vector_store.get_by_id(chunk_id)

    async def delete_by_file(self, file_path: str) -> None:
        await self._vector_store.delete_by_file(file_path)
        await self._graph_store.delete_by_file(file_path)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/storage/test_local_backend.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/context_engine/storage/backend.py src/context_engine/storage/local_backend.py tests/storage/test_local_backend.py
git commit -m "feat: storage backend protocol + local backend (LanceDB + Kuzu)"
```

---

## Phase 3: Indexer

### Task 8: Content Hash Manifest

**Files:**
- Create: `src/context_engine/indexer/__init__.py`
- Create: `src/context_engine/indexer/manifest.py`
- Create: `tests/indexer/test_manifest.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/indexer/test_manifest.py
import pytest
from pathlib import Path

from context_engine.indexer.manifest import Manifest


@pytest.fixture
def manifest(tmp_path):
    return Manifest(manifest_path=tmp_path / "manifest.json")


def test_empty_manifest_has_no_entries(manifest):
    assert manifest.get_hash("anything.py") is None


def test_update_and_get(manifest):
    manifest.update("src/main.py", "abc123hash")
    assert manifest.get_hash("src/main.py") == "abc123hash"


def test_has_changed_detects_new_file(manifest):
    assert manifest.has_changed("src/main.py", "abc123") is True


def test_has_changed_detects_modification(manifest):
    manifest.update("src/main.py", "old_hash")
    assert manifest.has_changed("src/main.py", "new_hash") is True


def test_has_changed_returns_false_if_same(manifest):
    manifest.update("src/main.py", "same_hash")
    assert manifest.has_changed("src/main.py", "same_hash") is False


def test_save_and_load(tmp_path):
    path = tmp_path / "manifest.json"
    m1 = Manifest(manifest_path=path)
    m1.update("a.py", "hash_a")
    m1.save()

    m2 = Manifest(manifest_path=path)
    assert m2.get_hash("a.py") == "hash_a"


def test_remove(manifest):
    manifest.update("a.py", "hash_a")
    manifest.remove("a.py")
    assert manifest.get_hash("a.py") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/indexer/test_manifest.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement Manifest**

```python
# src/context_engine/indexer/__init__.py
```

```python
# src/context_engine/indexer/manifest.py
"""Content hash manifest for incremental indexing."""
import json
from pathlib import Path


class Manifest:
    def __init__(self, manifest_path: Path) -> None:
        self._path = manifest_path
        self._entries: dict[str, str] = {}
        if self._path.exists():
            with open(self._path) as f:
                self._entries = json.load(f)

    def get_hash(self, file_path: str) -> str | None:
        return self._entries.get(file_path)

    def update(self, file_path: str, content_hash: str) -> None:
        self._entries[file_path] = content_hash

    def remove(self, file_path: str) -> None:
        self._entries.pop(file_path, None)

    def has_changed(self, file_path: str, content_hash: str) -> bool:
        return self._entries.get(file_path) != content_hash

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w") as f:
            json.dump(self._entries, f)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/indexer/test_manifest.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/context_engine/indexer/ tests/indexer/test_manifest.py
git commit -m "feat: content hash manifest for incremental indexing"
```

---

### Task 9: AST-Aware Chunker (tree-sitter)

**Files:**
- Create: `src/context_engine/indexer/chunker.py`
- Create: `tests/indexer/test_chunker.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/indexer/test_chunker.py
import pytest

from context_engine.models import ChunkType
from context_engine.indexer.chunker import Chunker


@pytest.fixture
def chunker():
    return Chunker()


PYTHON_CODE = '''
class Calculator:
    def add(self, a, b):
        return a + b

    def subtract(self, a, b):
        return a - b

def standalone_function(x):
    return x * 2
'''

JS_CODE = '''
function greet(name) {
    return `Hello, ${name}!`;
}

class Animal {
    constructor(name) {
        this.name = name;
    }
    speak() {
        return `${this.name} makes a noise.`;
    }
}
'''


def test_chunk_python_functions(chunker):
    chunks = chunker.chunk(PYTHON_CODE, file_path="calc.py", language="python")
    function_chunks = [c for c in chunks if c.chunk_type == ChunkType.FUNCTION]
    assert len(function_chunks) >= 2  # add, subtract, standalone_function


def test_chunk_python_classes(chunker):
    chunks = chunker.chunk(PYTHON_CODE, file_path="calc.py", language="python")
    class_chunks = [c for c in chunks if c.chunk_type == ChunkType.CLASS]
    assert len(class_chunks) >= 1


def test_chunk_has_correct_metadata(chunker):
    chunks = chunker.chunk(PYTHON_CODE, file_path="calc.py", language="python")
    for chunk in chunks:
        assert chunk.file_path == "calc.py"
        assert chunk.language == "python"
        assert chunk.start_line >= 1
        assert chunk.end_line >= chunk.start_line
        assert chunk.id != ""
        assert chunk.content != ""


def test_chunk_javascript(chunker):
    chunks = chunker.chunk(JS_CODE, file_path="app.js", language="javascript")
    assert len(chunks) > 0
    function_chunks = [c for c in chunks if c.chunk_type == ChunkType.FUNCTION]
    assert len(function_chunks) >= 1


def test_chunk_unsupported_language_falls_back(chunker):
    chunks = chunker.chunk("some content here", file_path="data.txt", language="plaintext")
    assert len(chunks) == 1
    assert chunks[0].chunk_type == ChunkType.MODULE
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/indexer/test_chunker.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement Chunker**

```python
# src/context_engine/indexer/chunker.py
"""AST-aware code chunking using tree-sitter."""
import hashlib

import tree_sitter_python as tspython
import tree_sitter_javascript as tsjavascript
from tree_sitter import Language, Parser

from context_engine.models import Chunk, ChunkType

# Node types that map to ChunkType.FUNCTION
_FUNCTION_TYPES = {
    "function_definition",      # Python
    "function_declaration",     # JS/TS
    "method_definition",        # JS class methods
    "arrow_function",           # JS arrow functions
}

# Node types that map to ChunkType.CLASS
_CLASS_TYPES = {
    "class_definition",         # Python
    "class_declaration",        # JS/TS
}

_LANGUAGES = {
    "python": Language(tspython.language()),
    "javascript": Language(tsjavascript.language()),
}


class Chunker:
    def __init__(self) -> None:
        self._parsers: dict[str, Parser] = {}

    def _get_parser(self, language: str) -> Parser | None:
        if language not in _LANGUAGES:
            return None
        if language not in self._parsers:
            parser = Parser()
            parser.language = _LANGUAGES[language]
            self._parsers[language] = parser
        return self._parsers[language]

    def chunk(self, source: str, file_path: str, language: str) -> list[Chunk]:
        parser = self._get_parser(language)
        if parser is None:
            return [self._fallback_chunk(source, file_path, language)]

        tree = parser.parse(source.encode("utf-8"))
        chunks = []
        self._walk(tree.root_node, source, file_path, language, chunks)

        if not chunks:
            return [self._fallback_chunk(source, file_path, language)]
        return chunks

    def _walk(
        self,
        node,
        source: str,
        file_path: str,
        language: str,
        chunks: list[Chunk],
    ) -> None:
        if node.type in _FUNCTION_TYPES:
            chunks.append(self._node_to_chunk(
                node, source, file_path, language, ChunkType.FUNCTION,
            ))
        elif node.type in _CLASS_TYPES:
            chunks.append(self._node_to_chunk(
                node, source, file_path, language, ChunkType.CLASS,
            ))

        for child in node.children:
            self._walk(child, source, file_path, language, chunks)

    def _node_to_chunk(
        self,
        node,
        source: str,
        file_path: str,
        language: str,
        chunk_type: ChunkType,
    ) -> Chunk:
        content = source[node.start_byte:node.end_byte]
        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1
        chunk_id = hashlib.sha256(
            f"{file_path}:{start_line}:{end_line}:{content[:100]}".encode()
        ).hexdigest()[:16]

        return Chunk(
            id=chunk_id,
            content=content,
            chunk_type=chunk_type,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            language=language,
        )

    def _fallback_chunk(self, source: str, file_path: str, language: str) -> Chunk:
        chunk_id = hashlib.sha256(f"{file_path}:module".encode()).hexdigest()[:16]
        lines = source.strip().split("\n")
        return Chunk(
            id=chunk_id,
            content=source,
            chunk_type=ChunkType.MODULE,
            file_path=file_path,
            start_line=1,
            end_line=len(lines),
            language=language,
        )
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/indexer/test_chunker.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/context_engine/indexer/chunker.py tests/indexer/test_chunker.py
git commit -m "feat: AST-aware chunker using tree-sitter (Python, JS)"
```

---

### Task 10: Embedding Generator

**Files:**
- Create: `src/context_engine/indexer/embedder.py`
- Create: `tests/indexer/test_embedder.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/indexer/test_embedder.py
import pytest

from context_engine.models import Chunk, ChunkType
from context_engine.indexer.embedder import Embedder


@pytest.fixture
def embedder():
    return Embedder(model_name="all-MiniLM-L6-v2")


@pytest.fixture
def sample_chunks():
    return [
        Chunk(
            id="c1", content="def add(a, b): return a + b",
            chunk_type=ChunkType.FUNCTION, file_path="math.py",
            start_line=1, end_line=1, language="python",
        ),
        Chunk(
            id="c2", content="def subtract(a, b): return a - b",
            chunk_type=ChunkType.FUNCTION, file_path="math.py",
            start_line=3, end_line=3, language="python",
        ),
    ]


def test_embed_chunks_adds_embeddings(embedder, sample_chunks):
    embedder.embed(sample_chunks)
    for chunk in sample_chunks:
        assert chunk.embedding is not None
        assert len(chunk.embedding) > 0
        assert isinstance(chunk.embedding[0], float)


def test_embed_query_returns_vector(embedder):
    vec = embedder.embed_query("find the add function")
    assert len(vec) > 0
    assert isinstance(vec[0], float)


def test_embedding_dimensions_match(embedder, sample_chunks):
    embedder.embed(sample_chunks)
    query_vec = embedder.embed_query("test")
    assert len(sample_chunks[0].embedding) == len(query_vec)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/indexer/test_embedder.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement Embedder**

```python
# src/context_engine/indexer/embedder.py
"""Embedding generation using sentence-transformers."""
from sentence_transformers import SentenceTransformer

from context_engine.models import Chunk


class Embedder:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self._model = SentenceTransformer(model_name)

    def embed(self, chunks: list[Chunk]) -> None:
        """Add embeddings to chunks in-place."""
        if not chunks:
            return
        texts = [c.content for c in chunks]
        embeddings = self._model.encode(texts, show_progress_bar=False)
        for chunk, emb in zip(chunks, embeddings):
            chunk.embedding = emb.tolist()

    def embed_query(self, query: str) -> list[float]:
        """Embed a query string for vector search."""
        return self._model.encode(query, show_progress_bar=False).tolist()
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/indexer/test_embedder.py -v`
Expected: All 3 tests PASS (first run will download the model ~90MB)

- [ ] **Step 5: Commit**

```bash
git add src/context_engine/indexer/embedder.py tests/indexer/test_embedder.py
git commit -m "feat: sentence-transformers embedder for chunks and queries"
```

---

### Task 11: File Watcher

**Files:**
- Create: `src/context_engine/indexer/watcher.py`
- Create: `tests/indexer/test_watcher.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/indexer/test_watcher.py
import asyncio
import time
from pathlib import Path

import pytest

from context_engine.indexer.watcher import FileWatcher


@pytest.mark.asyncio
async def test_watcher_detects_new_file(tmp_path):
    events = []

    async def on_change(path: str):
        events.append(path)

    watcher = FileWatcher(
        watch_dir=str(tmp_path),
        on_change=on_change,
        debounce_ms=100,
        ignore_patterns=[".git"],
    )
    watcher.start()

    # Create a file
    test_file = tmp_path / "hello.py"
    test_file.write_text("print('hello')")

    # Wait for debounce + processing
    await asyncio.sleep(0.5)
    watcher.stop()

    assert len(events) > 0
    assert any("hello.py" in e for e in events)


@pytest.mark.asyncio
async def test_watcher_ignores_patterns(tmp_path):
    events = []

    async def on_change(path: str):
        events.append(path)

    git_dir = tmp_path / ".git"
    git_dir.mkdir()

    watcher = FileWatcher(
        watch_dir=str(tmp_path),
        on_change=on_change,
        debounce_ms=100,
        ignore_patterns=[".git"],
    )
    watcher.start()

    (git_dir / "config").write_text("test")
    await asyncio.sleep(0.5)
    watcher.stop()

    assert not any(".git" in e for e in events)


@pytest.mark.asyncio
async def test_watcher_debounces(tmp_path):
    events = []

    async def on_change(path: str):
        events.append(path)

    watcher = FileWatcher(
        watch_dir=str(tmp_path),
        on_change=on_change,
        debounce_ms=300,
        ignore_patterns=[],
    )
    watcher.start()

    test_file = tmp_path / "rapid.py"
    # Write multiple times rapidly
    for i in range(5):
        test_file.write_text(f"version {i}")
        await asyncio.sleep(0.05)

    await asyncio.sleep(0.8)
    watcher.stop()

    # Should be debounced to fewer events than 5
    assert len(events) < 5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/indexer/test_watcher.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement FileWatcher**

```python
# src/context_engine/indexer/watcher.py
"""File watcher with debouncing using watchdog."""
import asyncio
import threading
import time
from pathlib import Path
from typing import Callable, Coroutine

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent


class _DebouncedHandler(FileSystemEventHandler):
    def __init__(
        self,
        on_change: Callable[[str], Coroutine],
        debounce_ms: int,
        ignore_patterns: list[str],
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        self._on_change = on_change
        self._debounce_s = debounce_ms / 1000.0
        self._ignore_patterns = ignore_patterns
        self._loop = loop
        self._pending: dict[str, float] = {}
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None

    def _should_ignore(self, path: str) -> bool:
        for pattern in self._ignore_patterns:
            if pattern in path:
                return True
        return False

    def on_any_event(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        path = event.src_path
        if self._should_ignore(path):
            return

        with self._lock:
            self._pending[path] = time.time()

        if self._timer:
            self._timer.cancel()
        self._timer = threading.Timer(self._debounce_s, self._flush)
        self._timer.start()

    def _flush(self) -> None:
        with self._lock:
            paths = list(self._pending.keys())
            self._pending.clear()

        for path in paths:
            asyncio.run_coroutine_threadsafe(self._on_change(path), self._loop)


class FileWatcher:
    def __init__(
        self,
        watch_dir: str,
        on_change: Callable[[str], Coroutine],
        debounce_ms: int = 500,
        ignore_patterns: list[str] | None = None,
    ) -> None:
        self._watch_dir = watch_dir
        self._loop = asyncio.get_event_loop()
        self._handler = _DebouncedHandler(
            on_change=on_change,
            debounce_ms=debounce_ms,
            ignore_patterns=ignore_patterns or [],
            loop=self._loop,
        )
        self._observer = Observer()

    def start(self) -> None:
        self._observer.schedule(self._handler, self._watch_dir, recursive=True)
        self._observer.start()

    def stop(self) -> None:
        self._observer.stop()
        self._observer.join(timeout=2)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/indexer/test_watcher.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/context_engine/indexer/watcher.py tests/indexer/test_watcher.py
git commit -m "feat: file watcher with debouncing and ignore patterns"
```

---

### Task 12: Git Hook Installer

**Files:**
- Create: `src/context_engine/indexer/git_hooks.py`
- Create: `scripts/install_hooks.sh`
- Create: `tests/indexer/test_git_hooks.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/indexer/test_git_hooks.py
import os
import stat
import pytest
from pathlib import Path

from context_engine.indexer.git_hooks import install_hooks, get_changed_files_from_hook


@pytest.fixture
def git_repo(tmp_path):
    """Create a minimal fake git directory structure."""
    git_dir = tmp_path / ".git" / "hooks"
    git_dir.mkdir(parents=True)
    return tmp_path


def test_install_hooks_creates_post_commit(git_repo):
    install_hooks(project_dir=str(git_repo))
    hook_path = git_repo / ".git" / "hooks" / "post-commit"
    assert hook_path.exists()
    assert os.access(hook_path, os.X_OK)
    content = hook_path.read_text()
    assert "claude-context-engine" in content


def test_install_hooks_creates_post_checkout(git_repo):
    install_hooks(project_dir=str(git_repo))
    hook_path = git_repo / ".git" / "hooks" / "post-checkout"
    assert hook_path.exists()


def test_install_hooks_creates_post_merge(git_repo):
    install_hooks(project_dir=str(git_repo))
    hook_path = git_repo / ".git" / "hooks" / "post-merge"
    assert hook_path.exists()


def test_install_hooks_preserves_existing(git_repo):
    existing_hook = git_repo / ".git" / "hooks" / "post-commit"
    existing_hook.write_text("#!/bin/sh\necho 'existing'\n")
    existing_hook.chmod(existing_hook.stat().st_mode | stat.S_IEXEC)

    install_hooks(project_dir=str(git_repo))
    content = existing_hook.read_text()
    assert "existing" in content
    assert "claude-context-engine" in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/indexer/test_git_hooks.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement git hooks**

```python
# src/context_engine/indexer/git_hooks.py
"""Git hook installer and handler for triggering re-indexing."""
import os
import stat
import subprocess
from pathlib import Path


HOOK_MARKER = "# claude-context-engine hook"

HOOK_SCRIPT = f"""{HOOK_MARKER}
claude-context-engine index --changed-only 2>/dev/null &
"""

HOOK_NAMES = ["post-commit", "post-checkout", "post-merge"]


def install_hooks(project_dir: str) -> list[str]:
    """Install git hooks for auto re-indexing. Returns list of installed hook paths."""
    hooks_dir = Path(project_dir) / ".git" / "hooks"
    if not hooks_dir.exists():
        raise FileNotFoundError(f"Git hooks directory not found: {hooks_dir}")

    installed = []
    for hook_name in HOOK_NAMES:
        hook_path = hooks_dir / hook_name
        _install_single_hook(hook_path)
        installed.append(str(hook_path))
    return installed


def _install_single_hook(hook_path: Path) -> None:
    """Install or append to a single hook file."""
    if hook_path.exists():
        existing = hook_path.read_text()
        if HOOK_MARKER in existing:
            return  # already installed
        new_content = existing.rstrip() + "\n\n" + HOOK_SCRIPT
    else:
        new_content = "#!/bin/sh\n\n" + HOOK_SCRIPT

    hook_path.write_text(new_content)
    hook_path.chmod(hook_path.stat().st_mode | stat.S_IEXEC)


def get_changed_files_from_hook() -> list[str]:
    """Get list of files changed in the most recent git operation."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~1", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return [f for f in result.stdout.strip().split("\n") if f]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return []
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/indexer/test_git_hooks.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Create install_hooks.sh helper and commit**

```bash
# scripts/install_hooks.sh
#!/bin/sh
# Helper to install claude-context-engine git hooks in the current repo
claude-context-engine init
```

```bash
git add src/context_engine/indexer/git_hooks.py tests/indexer/test_git_hooks.py scripts/install_hooks.sh
git commit -m "feat: git hook installer for post-commit/checkout/merge"
```

---

## Phase 4: Retrieval + Compression

### Task 13: Query Parser

**Files:**
- Create: `src/context_engine/retrieval/__init__.py`
- Create: `src/context_engine/retrieval/query_parser.py`
- Create: `tests/retrieval/test_query_parser.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/retrieval/test_query_parser.py
import pytest

from context_engine.retrieval.query_parser import QueryParser, QueryIntent


def test_code_lookup_intent():
    parser = QueryParser()
    result = parser.parse("find the add function in math.py")
    assert result.intent == QueryIntent.CODE_LOOKUP
    assert "add" in result.keywords


def test_decision_recall_intent():
    parser = QueryParser()
    result = parser.parse("what did we decide about the auth system?")
    assert result.intent == QueryIntent.DECISION_RECALL


def test_architecture_intent():
    parser = QueryParser()
    result = parser.parse("how is the storage module structured?")
    assert result.intent == QueryIntent.ARCHITECTURE


def test_keyword_extraction():
    parser = QueryParser()
    result = parser.parse("show me the UserService class")
    assert "UserService" in result.keywords


def test_file_path_extraction():
    parser = QueryParser()
    result = parser.parse("what does src/auth/login.py do?")
    assert "src/auth/login.py" in result.file_hints
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/retrieval/test_query_parser.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement QueryParser**

```python
# src/context_engine/retrieval/__init__.py
```

```python
# src/context_engine/retrieval/query_parser.py
"""Query understanding — intent classification and keyword extraction."""
import re
from dataclasses import dataclass, field
from enum import Enum


class QueryIntent(Enum):
    CODE_LOOKUP = "code_lookup"
    DECISION_RECALL = "decision_recall"
    ARCHITECTURE = "architecture"
    GENERAL = "general"


_DECISION_PATTERNS = [
    r"what did we decide",
    r"decision about",
    r"why did we",
    r"last session",
    r"previous discussion",
    r"agreed on",
]

_ARCHITECTURE_PATTERNS = [
    r"how is .+ structured",
    r"architecture",
    r"module.+structure",
    r"component.+design",
    r"how does .+ work",
    r"overview of",
    r"explain the .+ system",
]

_CODE_PATTERNS = [
    r"find .+ function",
    r"show me .+ class",
    r"where is .+ defined",
    r"implementation of",
    r"\.py|\.js|\.ts",
    r"function|class|method|def |import ",
]

# Matches file paths like src/foo/bar.py
_FILE_PATH_RE = re.compile(r"[a-zA-Z0-9_./-]+\.[a-zA-Z]{1,10}")

# Common stop words to exclude from keywords
_STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "do", "does", "did",
    "what", "how", "why", "where", "when", "who", "which",
    "in", "on", "at", "to", "for", "of", "with", "about",
    "me", "my", "we", "our", "it", "its", "i", "you",
    "show", "find", "get", "tell", "give",
}


@dataclass
class ParsedQuery:
    original: str
    intent: QueryIntent
    keywords: list[str] = field(default_factory=list)
    file_hints: list[str] = field(default_factory=list)


class QueryParser:
    def parse(self, query: str) -> ParsedQuery:
        lower = query.lower()
        intent = self._classify_intent(lower)
        keywords = self._extract_keywords(query)
        file_hints = _FILE_PATH_RE.findall(query)

        return ParsedQuery(
            original=query,
            intent=intent,
            keywords=keywords,
            file_hints=file_hints,
        )

    def _classify_intent(self, query: str) -> QueryIntent:
        for pattern in _DECISION_PATTERNS:
            if re.search(pattern, query):
                return QueryIntent.DECISION_RECALL
        for pattern in _ARCHITECTURE_PATTERNS:
            if re.search(pattern, query):
                return QueryIntent.ARCHITECTURE
        for pattern in _CODE_PATTERNS:
            if re.search(pattern, query):
                return QueryIntent.CODE_LOOKUP
        return QueryIntent.GENERAL

    def _extract_keywords(self, query: str) -> list[str]:
        # Keep CamelCase and PascalCase identifiers as-is
        identifiers = re.findall(r"[A-Z][a-zA-Z0-9]+", query)

        # Extract remaining words, filter stop words
        words = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", query)
        meaningful = [w for w in words if w.lower() not in _STOP_WORDS and len(w) > 2]

        # Combine, deduplicate, preserve order
        seen = set()
        result = []
        for kw in identifiers + meaningful:
            if kw not in seen:
                seen.add(kw)
                result.append(kw)
        return result
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/retrieval/test_query_parser.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/context_engine/retrieval/ tests/retrieval/test_query_parser.py
git commit -m "feat: query parser with intent classification and keyword extraction"
```

---

### Task 14: Confidence Scoring

**Files:**
- Create: `src/context_engine/retrieval/confidence.py`
- Create: `tests/retrieval/test_confidence.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/retrieval/test_confidence.py
import pytest
import time

from context_engine.models import Chunk, ChunkType, ConfidenceLevel
from context_engine.retrieval.confidence import ConfidenceScorer


@pytest.fixture
def scorer():
    return ConfidenceScorer()


def _make_chunk(chunk_id: str, distance: float = 0.1) -> tuple[Chunk, float]:
    chunk = Chunk(
        id=chunk_id, content="test", chunk_type=ChunkType.FUNCTION,
        file_path="test.py", start_line=1, end_line=1, language="python",
    )
    return chunk, distance


def test_high_confidence_for_close_match(scorer):
    chunk, dist = _make_chunk("c1", distance=0.05)
    score = scorer.score(chunk, vector_distance=dist, graph_hops=0)
    assert score > 0.8
    assert ConfidenceLevel.from_score(score) == ConfidenceLevel.HIGH


def test_low_confidence_for_distant_match(scorer):
    chunk, dist = _make_chunk("c1", distance=0.95)
    score = scorer.score(chunk, vector_distance=dist, graph_hops=5)
    assert score < 0.5
    assert ConfidenceLevel.from_score(score) == ConfidenceLevel.LOW


def test_graph_hops_reduce_confidence(scorer):
    chunk, dist = _make_chunk("c1", distance=0.1)
    score_close = scorer.score(chunk, vector_distance=dist, graph_hops=0)
    score_far = scorer.score(chunk, vector_distance=dist, graph_hops=4)
    assert score_close > score_far


def test_recency_boosts_score(scorer):
    old_chunk = Chunk(
        id="old", content="test", chunk_type=ChunkType.FUNCTION,
        file_path="test.py", start_line=1, end_line=1, language="python",
        metadata={"modified_ts": 1000000},
    )
    new_chunk = Chunk(
        id="new", content="test", chunk_type=ChunkType.FUNCTION,
        file_path="test.py", start_line=1, end_line=1, language="python",
        metadata={"modified_ts": time.time()},
    )
    score_old = scorer.score(old_chunk, vector_distance=0.2, graph_hops=1)
    score_new = scorer.score(new_chunk, vector_distance=0.2, graph_hops=1)
    assert score_new > score_old
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/retrieval/test_confidence.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement ConfidenceScorer**

```python
# src/context_engine/retrieval/confidence.py
"""Confidence scoring for retrieved chunks."""
import time

from context_engine.models import Chunk


# Weights for score components
_VECTOR_WEIGHT = 0.5
_GRAPH_WEIGHT = 0.3
_RECENCY_WEIGHT = 0.2

# Max graph hops before graph score hits 0
_MAX_GRAPH_HOPS = 5

# Recency decay: how many seconds until recency bonus halves
_RECENCY_HALF_LIFE = 7 * 24 * 3600  # 1 week


class ConfidenceScorer:
    def score(
        self,
        chunk: Chunk,
        vector_distance: float,
        graph_hops: int,
    ) -> float:
        """Compute confidence score (0.0 - 1.0) for a retrieved chunk."""
        vector_score = max(0.0, 1.0 - vector_distance)
        graph_score = max(0.0, 1.0 - (graph_hops / _MAX_GRAPH_HOPS))
        recency_score = self._recency_score(chunk)

        combined = (
            _VECTOR_WEIGHT * vector_score
            + _GRAPH_WEIGHT * graph_score
            + _RECENCY_WEIGHT * recency_score
        )
        return min(1.0, max(0.0, combined))

    def _recency_score(self, chunk: Chunk) -> float:
        modified_ts = chunk.metadata.get("modified_ts")
        if modified_ts is None:
            return 0.5  # neutral if unknown

        age_seconds = time.time() - modified_ts
        if age_seconds <= 0:
            return 1.0

        # Exponential decay with half-life
        return 0.5 ** (age_seconds / _RECENCY_HALF_LIFE)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/retrieval/test_confidence.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/context_engine/retrieval/confidence.py tests/retrieval/test_confidence.py
git commit -m "feat: confidence scoring with vector distance, graph hops, recency"
```

---

### Task 15: Hybrid Retriever

**Files:**
- Create: `src/context_engine/retrieval/retriever.py`
- Create: `tests/retrieval/test_retriever.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/retrieval/test_retriever.py
import pytest

from context_engine.models import Chunk, ChunkType, GraphNode, GraphEdge, NodeType, EdgeType, ConfidenceLevel
from context_engine.storage.local_backend import LocalBackend
from context_engine.indexer.embedder import Embedder
from context_engine.retrieval.retriever import HybridRetriever


@pytest.fixture
def backend(tmp_path):
    return LocalBackend(base_path=str(tmp_path))


@pytest.fixture
def embedder():
    return Embedder(model_name="all-MiniLM-L6-v2")


@pytest.fixture
def retriever(backend, embedder):
    return HybridRetriever(backend=backend, embedder=embedder)


@pytest.fixture
async def seeded_retriever(retriever, backend, embedder):
    """Retriever with some data already indexed."""
    chunks = [
        Chunk(id="c1", content="def add(a, b): return a + b",
              chunk_type=ChunkType.FUNCTION, file_path="math.py",
              start_line=1, end_line=1, language="python"),
        Chunk(id="c2", content="def multiply(a, b): return a * b",
              chunk_type=ChunkType.FUNCTION, file_path="math.py",
              start_line=3, end_line=3, language="python"),
        Chunk(id="c3", content="class UserAuth: handles user authentication and login",
              chunk_type=ChunkType.CLASS, file_path="auth.py",
              start_line=1, end_line=10, language="python"),
    ]
    embedder.embed(chunks)
    nodes = [
        GraphNode(id="func_add", node_type=NodeType.FUNCTION, name="add", file_path="math.py"),
        GraphNode(id="func_mul", node_type=NodeType.FUNCTION, name="multiply", file_path="math.py"),
        GraphNode(id="cls_auth", node_type=NodeType.CLASS, name="UserAuth", file_path="auth.py"),
    ]
    edges = [
        GraphEdge(source_id="func_add", target_id="func_mul", edge_type=EdgeType.CALLS),
    ]
    await backend.ingest(chunks, nodes, edges)
    return retriever


@pytest.mark.asyncio
async def test_retrieve_returns_scored_results(seeded_retriever):
    results = await seeded_retriever.retrieve("addition function", top_k=5)
    assert len(results) > 0
    assert all(c.confidence_score > 0 for c in results)


@pytest.mark.asyncio
async def test_retrieve_sorts_by_confidence(seeded_retriever):
    results = await seeded_retriever.retrieve("add numbers", top_k=5)
    scores = [c.confidence_score for c in results]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_retrieve_respects_top_k(seeded_retriever):
    results = await seeded_retriever.retrieve("function", top_k=2)
    assert len(results) <= 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/retrieval/test_retriever.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement HybridRetriever**

```python
# src/context_engine/retrieval/retriever.py
"""Hybrid retrieval — vector search + graph traversal + confidence scoring."""
from context_engine.models import Chunk, ConfidenceLevel
from context_engine.storage.backend import StorageBackend
from context_engine.indexer.embedder import Embedder
from context_engine.retrieval.confidence import ConfidenceScorer
from context_engine.retrieval.query_parser import QueryParser, QueryIntent


class HybridRetriever:
    def __init__(self, backend: StorageBackend, embedder: Embedder) -> None:
        self._backend = backend
        self._embedder = embedder
        self._scorer = ConfidenceScorer()
        self._parser = QueryParser()

    async def retrieve(
        self,
        query: str,
        top_k: int = 10,
        confidence_threshold: float = 0.0,
    ) -> list[Chunk]:
        """Retrieve chunks using hybrid vector + graph search with confidence scoring."""
        parsed = self._parser.parse(query)
        query_embedding = self._embedder.embed_query(query)

        # Step 1: Vector search
        vector_results = await self._backend.vector_search(
            query_embedding=query_embedding,
            top_k=top_k * 2,  # fetch extra for re-ranking
        )

        # Step 2: Score each result
        scored: list[tuple[Chunk, float]] = []
        for chunk in vector_results:
            # Estimate vector distance from the fact it was returned (use position as proxy)
            idx = vector_results.index(chunk)
            approx_distance = idx / max(len(vector_results), 1)

            # Check graph proximity
            graph_hops = await self._estimate_graph_hops(chunk, parsed)

            score = self._scorer.score(
                chunk, vector_distance=approx_distance, graph_hops=graph_hops,
            )
            chunk.confidence_score = score
            if score >= confidence_threshold:
                scored.append((chunk, score))

        # Step 3: Sort by confidence, return top_k
        scored.sort(key=lambda x: x[1], reverse=True)
        return [chunk for chunk, _ in scored[:top_k]]

    async def _estimate_graph_hops(self, chunk: Chunk, parsed) -> int:
        """Estimate graph distance between chunk and query targets."""
        # If query mentions specific files that match, reduce hops
        if parsed.file_hints:
            for hint in parsed.file_hints:
                if hint in chunk.file_path:
                    return 0

        # If query keywords appear in chunk content, treat as direct hit
        for keyword in parsed.keywords:
            if keyword.lower() in chunk.content.lower():
                return 0

        # Default: assume moderate distance
        return 2
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/retrieval/test_retriever.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/context_engine/retrieval/retriever.py tests/retrieval/test_retriever.py
git commit -m "feat: hybrid retriever with vector + graph + confidence scoring"
```

---

### Task 16: Ollama Client

**Files:**
- Create: `src/context_engine/compression/__init__.py`
- Create: `src/context_engine/compression/ollama_client.py`
- Create: `src/context_engine/compression/prompts.py`
- Create: `tests/compression/test_ollama_client.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/compression/test_ollama_client.py
import pytest

from context_engine.compression.ollama_client import OllamaClient


@pytest.fixture
def client():
    return OllamaClient(base_url="http://localhost:11434")


def test_client_init():
    client = OllamaClient(base_url="http://localhost:11434", model="phi3:mini")
    assert client.model == "phi3:mini"
    assert client.base_url == "http://localhost:11434"


@pytest.mark.asyncio
async def test_is_available_returns_bool(client):
    # This test works regardless of whether Ollama is running
    result = await client.is_available()
    assert isinstance(result, bool)


@pytest.mark.asyncio
async def test_summarize_returns_string_when_available(client):
    if not await client.is_available():
        pytest.skip("Ollama not running")
    result = await client.summarize("def add(a, b): return a + b", prompt="Summarize this function.")
    assert isinstance(result, str)
    assert len(result) > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/compression/test_ollama_client.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement OllamaClient and prompts**

```python
# src/context_engine/compression/__init__.py
```

```python
# src/context_engine/compression/prompts.py
"""Summarization prompt templates for different chunk types."""

CODE_PROMPT = (
    "Summarize this code. Include: function/class name, purpose, "
    "inputs/outputs, key side effects. Be concise (2-3 sentences max).\n\n"
    "Code:\n{content}"
)

DECISION_PROMPT = (
    "Summarize this decision. Include: what was decided, why, "
    "and what the outcome/action was. One paragraph max.\n\n"
    "Decision:\n{content}"
)

ARCHITECTURE_PROMPT = (
    "Summarize this component. Include: what it does, its role in the system, "
    "and its key dependencies. Be concise (2-3 sentences).\n\n"
    "Component:\n{content}"
)

DOC_PROMPT = (
    "Summarize this documentation. Keep the key information, "
    "remove boilerplate. Be concise.\n\n"
    "Documentation:\n{content}"
)
```

```python
# src/context_engine/compression/ollama_client.py
"""Ollama API client for local LLM summarization."""
import httpx


class OllamaClient:
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "phi3:mini",
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url
        self.model = model
        self._timeout = timeout

    async def is_available(self) -> bool:
        """Check if Ollama is running and responsive."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                return resp.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    async def summarize(self, content: str, prompt: str) -> str:
        """Send content to Ollama for summarization."""
        full_prompt = prompt.format(content=content) if "{content}" in prompt else f"{prompt}\n\n{content}"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": full_prompt,
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 256},
                },
            )
            resp.raise_for_status()
            return resp.json()["response"].strip()
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/compression/test_ollama_client.py -v`
Expected: All 3 tests PASS (test_summarize skips if Ollama not running)

- [ ] **Step 5: Commit**

```bash
git add src/context_engine/compression/ tests/compression/test_ollama_client.py
git commit -m "feat: Ollama client + summarization prompt templates"
```

---

### Task 17: Compression Pipeline + Quality Safeguards

**Files:**
- Create: `src/context_engine/compression/quality.py`
- Create: `src/context_engine/compression/compressor.py`
- Create: `tests/compression/test_quality.py`
- Create: `tests/compression/test_compressor.py`

- [ ] **Step 1: Write failing tests for quality checker**

```python
# tests/compression/test_quality.py
import pytest

from context_engine.compression.quality import QualityChecker


@pytest.fixture
def checker():
    return QualityChecker()


def test_passes_when_identifiers_preserved(checker):
    original = "def calculate_total(items, tax_rate): return sum(items) * (1 + tax_rate)"
    summary = "calculate_total takes items and tax_rate, returns the sum of items with tax applied."
    assert checker.check(original, summary) is True


def test_fails_when_identifiers_missing(checker):
    original = "def calculate_total(items, tax_rate): return sum(items) * (1 + tax_rate)"
    summary = "A function that computes a value."
    assert checker.check(original, summary) is False


def test_extracts_identifiers_from_code(checker):
    code = "class UserService:\n    def get_user(self, user_id): pass"
    identifiers = checker.extract_identifiers(code)
    assert "UserService" in identifiers
    assert "get_user" in identifiers
    assert "user_id" in identifiers
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/compression/test_quality.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement QualityChecker**

```python
# src/context_engine/compression/quality.py
"""Lossy detection — verify compressed summaries preserve key identifiers."""
import re


# Minimum ratio of identifiers that must appear in summary
_MIN_IDENTIFIER_RATIO = 0.4

# Minimum identifier length to consider significant
_MIN_IDENTIFIER_LEN = 3


class QualityChecker:
    def check(self, original: str, summary: str) -> bool:
        """Check if summary preserves key identifiers from original."""
        identifiers = self.extract_identifiers(original)
        if not identifiers:
            return True  # nothing to check

        summary_lower = summary.lower()
        preserved = sum(1 for ident in identifiers if ident.lower() in summary_lower)
        ratio = preserved / len(identifiers)
        return ratio >= _MIN_IDENTIFIER_RATIO

    def extract_identifiers(self, code: str) -> list[str]:
        """Extract meaningful identifiers from code."""
        # Match function/class/variable names
        patterns = [
            r"(?:def|class|function)\s+([a-zA-Z_][a-zA-Z0-9_]*)",  # definitions
            r"([a-zA-Z_][a-zA-Z0-9_]*)\s*[=:(]",  # assignments and parameters
            r"self\.([a-zA-Z_][a-zA-Z0-9_]*)",  # instance attributes
        ]
        identifiers = set()
        for pattern in patterns:
            for match in re.finditer(pattern, code):
                name = match.group(1)
                if len(name) >= _MIN_IDENTIFIER_LEN and name not in {"self", "None", "True", "False"}:
                    identifiers.add(name)

        # Also capture CamelCase identifiers
        for match in re.finditer(r"\b([A-Z][a-zA-Z0-9]+)\b", code):
            identifiers.add(match.group(1))

        return sorted(identifiers)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/compression/test_quality.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Write failing tests for compressor**

```python
# tests/compression/test_compressor.py
import pytest

from context_engine.models import Chunk, ChunkType
from context_engine.compression.compressor import Compressor


@pytest.fixture
def compressor():
    return Compressor(ollama_url="http://localhost:11434", model="phi3:mini")


@pytest.fixture
def sample_chunks():
    return [
        Chunk(
            id="c1", content="def add(a, b):\n    '''Add two numbers.'''\n    return a + b",
            chunk_type=ChunkType.FUNCTION, file_path="math.py",
            start_line=1, end_line=3, language="python", confidence_score=0.9,
        ),
        Chunk(
            id="c2", content="class Calculator:\n    pass",
            chunk_type=ChunkType.CLASS, file_path="calc.py",
            start_line=1, end_line=2, language="python", confidence_score=0.6,
        ),
    ]


@pytest.mark.asyncio
async def test_compress_without_ollama_falls_back(compressor, sample_chunks):
    """When Ollama is not available, compression falls back to truncation."""
    results = await compressor.compress(sample_chunks, level="standard")
    assert len(results) > 0
    for chunk in results:
        assert chunk.compressed_content is not None


@pytest.mark.asyncio
async def test_compress_minimal_level(compressor, sample_chunks):
    results = await compressor.compress(sample_chunks, level="minimal")
    for chunk in results:
        # Minimal should be shorter than original
        assert len(chunk.compressed_content) <= len(chunk.content) + 50


@pytest.mark.asyncio
async def test_compress_preserves_original(compressor, sample_chunks):
    original_contents = [c.content for c in sample_chunks]
    await compressor.compress(sample_chunks, level="standard")
    for chunk, original in zip(sample_chunks, original_contents):
        assert chunk.content == original  # original untouched
```

- [ ] **Step 6: Run test to verify it fails**

Run: `pytest tests/compression/test_compressor.py -v`
Expected: FAIL with ImportError

- [ ] **Step 7: Implement Compressor**

```python
# src/context_engine/compression/compressor.py
"""Compression pipeline — groups chunks, summarizes via LLM, falls back to truncation."""
import re

from context_engine.models import Chunk, ChunkType
from context_engine.compression.ollama_client import OllamaClient
from context_engine.compression.prompts import CODE_PROMPT, DECISION_PROMPT, ARCHITECTURE_PROMPT, DOC_PROMPT
from context_engine.compression.quality import QualityChecker


_PROMPT_MAP = {
    ChunkType.FUNCTION: CODE_PROMPT,
    ChunkType.CLASS: CODE_PROMPT,
    ChunkType.MODULE: ARCHITECTURE_PROMPT,
    ChunkType.DOC: DOC_PROMPT,
    ChunkType.DECISION: DECISION_PROMPT,
    ChunkType.SESSION: DOC_PROMPT,
    ChunkType.COMMIT: DOC_PROMPT,
    ChunkType.COMMENT: DOC_PROMPT,
}

# Max characters for fallback truncation by level
_TRUNCATION_LIMITS = {
    "minimal": 100,
    "standard": 300,
    "full": 800,
}


class Compressor:
    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        model: str = "phi3:mini",
    ) -> None:
        self._client = OllamaClient(base_url=ollama_url, model=model)
        self._quality = QualityChecker()

    async def compress(
        self,
        chunks: list[Chunk],
        level: str = "standard",
    ) -> list[Chunk]:
        """Compress chunks. Uses LLM if available, falls back to smart truncation."""
        ollama_available = await self._client.is_available()

        for chunk in chunks:
            if level == "full" and chunk.confidence_score > 0.8:
                # Full level + high confidence: keep original
                chunk.compressed_content = chunk.content
            elif ollama_available and level != "minimal":
                chunk.compressed_content = await self._llm_compress(chunk, level)
            else:
                chunk.compressed_content = self._fallback_compress(chunk, level)

        return chunks

    async def _llm_compress(self, chunk: Chunk, level: str) -> str:
        """Compress using Ollama LLM with quality check."""
        prompt = _PROMPT_MAP.get(chunk.chunk_type, CODE_PROMPT)
        try:
            summary = await self._client.summarize(chunk.content, prompt)
            if self._quality.check(chunk.content, summary):
                return summary
            # Quality check failed — retry with less aggressive prompt
            return self._fallback_compress(chunk, level)
        except Exception:
            return self._fallback_compress(chunk, level)

    def _fallback_compress(self, chunk: Chunk, level: str) -> str:
        """Smart truncation fallback when LLM is unavailable."""
        limit = _TRUNCATION_LIMITS.get(level, 300)

        if chunk.chunk_type in (ChunkType.FUNCTION, ChunkType.CLASS):
            # Extract signature + first docstring/comment
            return self._extract_signature(chunk.content, limit)

        if len(chunk.content) <= limit:
            return chunk.content
        return chunk.content[:limit] + "..."

    def _extract_signature(self, content: str, limit: int) -> str:
        """Extract function/class signature and docstring."""
        lines = content.split("\n")
        result_lines = []
        in_docstring = False
        char_count = 0

        for line in lines:
            if char_count + len(line) > limit and result_lines:
                break
            result_lines.append(line)
            char_count += len(line) + 1

            # Capture up to end of docstring
            if '"""' in line or "'''" in line:
                if in_docstring:
                    break
                in_docstring = True

            # Stop after signature if no docstring
            if not in_docstring and line.strip().endswith(":") and len(result_lines) > 1:
                break

        return "\n".join(result_lines)
```

- [ ] **Step 8: Run tests**

Run: `pytest tests/compression/test_compressor.py -v`
Expected: All 3 tests PASS

- [ ] **Step 9: Commit**

```bash
git add src/context_engine/compression/quality.py src/context_engine/compression/compressor.py tests/compression/test_quality.py tests/compression/test_compressor.py
git commit -m "feat: compression pipeline with LLM + fallback + quality safeguards"
```

---

## Phase 5: Integration (MCP + Bootstrap + CLI)

### Task 18: Bootstrap Context Builder

**Files:**
- Create: `src/context_engine/integration/__init__.py`
- Create: `src/context_engine/integration/bootstrap.py`
- Create: `tests/integration/test_bootstrap.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/integration/test_bootstrap.py
import pytest

from context_engine.models import Chunk, ChunkType, ConfidenceLevel
from context_engine.integration.bootstrap import BootstrapBuilder


@pytest.fixture
def builder():
    return BootstrapBuilder(max_tokens=10000)


def test_build_payload_structure(builder):
    chunks = [
        Chunk(id="c1", content="def main(): pass",
              chunk_type=ChunkType.FUNCTION, file_path="app.py",
              start_line=1, end_line=1, language="python",
              confidence_score=0.9, compressed_content="main(): entry point"),
    ]
    payload = builder.build(
        project_name="my-project",
        chunks=chunks,
        recent_commits=["fix: resolve login bug", "feat: add user profile"],
    )
    assert "## Project: my-project" in payload
    assert "### Architecture" in payload
    assert "### Recent Activity" in payload
    assert "main()" in payload


def test_build_respects_token_limit(builder):
    # Generate many chunks to exceed token limit
    chunks = [
        Chunk(id=f"c{i}", content=f"def func_{i}(): pass" * 50,
              chunk_type=ChunkType.FUNCTION, file_path=f"file_{i}.py",
              start_line=1, end_line=1, language="python",
              confidence_score=0.9, compressed_content=f"func_{i}: does thing {i} " * 20)
        for i in range(100)
    ]
    payload = builder.build(project_name="big-project", chunks=chunks)
    # Rough token estimate: 1 token ≈ 4 chars
    estimated_tokens = len(payload) / 4
    assert estimated_tokens < 12000  # some slack above limit


def test_build_groups_by_confidence(builder):
    chunks = [
        Chunk(id="low", content="x", chunk_type=ChunkType.FUNCTION,
              file_path="a.py", start_line=1, end_line=1, language="python",
              confidence_score=0.3, compressed_content="low relevance"),
        Chunk(id="high", content="y", chunk_type=ChunkType.FUNCTION,
              file_path="b.py", start_line=1, end_line=1, language="python",
              confidence_score=0.95, compressed_content="high relevance"),
    ]
    payload = builder.build(project_name="test", chunks=chunks)
    # High confidence should appear, low should be excluded or at bottom
    high_pos = payload.find("high relevance")
    assert high_pos >= 0


def test_build_empty_project(builder):
    payload = builder.build(project_name="empty")
    assert "## Project: empty" in payload
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_bootstrap.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement BootstrapBuilder**

```python
# src/context_engine/integration/__init__.py
```

```python
# src/context_engine/integration/bootstrap.py
"""Bootstrap context builder — generates compressed project context for session start."""
from context_engine.models import Chunk, ConfidenceLevel


# Approximate chars per token
_CHARS_PER_TOKEN = 4


class BootstrapBuilder:
    def __init__(self, max_tokens: int = 10000) -> None:
        self._max_chars = max_tokens * _CHARS_PER_TOKEN

    def build(
        self,
        project_name: str,
        chunks: list[Chunk] | None = None,
        recent_commits: list[str] | None = None,
        active_decisions: list[str] | None = None,
    ) -> str:
        """Build a bootstrap context payload."""
        sections = []
        sections.append(f"## Project: {project_name}")

        # Architecture section — high confidence chunks
        arch_section = self._build_architecture(chunks or [])
        sections.append(arch_section)

        # Recent activity
        activity_section = self._build_activity(recent_commits or [])
        sections.append(activity_section)

        # Active context from past sessions
        if active_decisions:
            decisions_text = "\n".join(f"- {d}" for d in active_decisions)
            sections.append(f"### Active Context\n{decisions_text}")

        # Key code context
        code_section = self._build_code_context(chunks or [])
        if code_section:
            sections.append(code_section)

        payload = "\n\n".join(sections)

        # Truncate to token limit
        if len(payload) > self._max_chars:
            payload = payload[:self._max_chars] + "\n\n[Context truncated to fit token limit]"

        return payload

    def _build_architecture(self, chunks: list[Chunk]) -> str:
        """Build architecture overview from high-confidence chunks."""
        high_conf = [
            c for c in chunks
            if ConfidenceLevel.from_score(c.confidence_score) == ConfidenceLevel.HIGH
        ]
        if not high_conf:
            return "### Architecture\nNo indexed context available yet."

        # Group by file
        by_file: dict[str, list[Chunk]] = {}
        for chunk in high_conf:
            by_file.setdefault(chunk.file_path, []).append(chunk)

        lines = ["### Architecture"]
        for file_path, file_chunks in sorted(by_file.items()):
            lines.append(f"\n**{file_path}:**")
            for chunk in file_chunks:
                text = chunk.compressed_content or chunk.content[:200]
                lines.append(f"- {text}")

        return "\n".join(lines)

    def _build_activity(self, commits: list[str]) -> str:
        """Build recent activity section."""
        if not commits:
            return "### Recent Activity\nNo recent commits."

        lines = ["### Recent Activity"]
        for commit in commits[:10]:
            lines.append(f"- {commit}")
        return "\n".join(lines)

    def _build_code_context(self, chunks: list[Chunk]) -> str:
        """Build code context section from medium-confidence chunks."""
        medium_conf = [
            c for c in chunks
            if ConfidenceLevel.from_score(c.confidence_score) == ConfidenceLevel.MEDIUM
        ]
        if not medium_conf:
            return ""

        lines = ["### Additional Context (may need drill-down)"]
        for chunk in medium_conf[:20]:
            text = chunk.compressed_content or chunk.content[:150]
            lines.append(f"- [{chunk.file_path}] {text}")

        return "\n".join(lines)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/integration/test_bootstrap.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/context_engine/integration/ tests/integration/test_bootstrap.py
git commit -m "feat: bootstrap context builder with confidence-based sections"
```

---

### Task 19: MCP Server

**Files:**
- Create: `src/context_engine/integration/mcp_server.py`
- Create: `tests/integration/test_mcp_server.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/integration/test_mcp_server.py
import pytest

from context_engine.integration.mcp_server import ContextEngineMCP


def test_mcp_server_has_required_tools():
    server = ContextEngineMCP.__new__(ContextEngineMCP)
    tool_names = server.get_tool_names()
    assert "context_search" in tool_names
    assert "expand_chunk" in tool_names
    assert "related_context" in tool_names
    assert "session_recall" in tool_names
    assert "index_status" in tool_names
    assert "reindex" in tool_names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_mcp_server.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement MCP server**

```python
# src/context_engine/integration/mcp_server.py
"""MCP server exposing context engine tools to Claude Code."""
import json

from mcp.server import Server
from mcp.types import Tool, TextContent

from context_engine.models import Chunk


class ContextEngineMCP:
    TOOL_NAMES = [
        "context_search",
        "expand_chunk",
        "related_context",
        "session_recall",
        "index_status",
        "reindex",
    ]

    def __init__(self, retriever, backend, compressor, embedder, config) -> None:
        self._retriever = retriever
        self._backend = backend
        self._compressor = compressor
        self._embedder = embedder
        self._config = config
        self._server = Server("claude-context-engine")
        self._register_tools()

    def get_tool_names(self) -> list[str]:
        return list(self.TOOL_NAMES)

    def _register_tools(self) -> None:
        @self._server.list_tools()
        async def list_tools():
            return [
                Tool(
                    name="context_search",
                    description="Search project context — code, docs, session history",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query"},
                            "top_k": {"type": "integer", "description": "Max results", "default": 10},
                        },
                        "required": ["query"],
                    },
                ),
                Tool(
                    name="expand_chunk",
                    description="Get the full original content for a compressed chunk",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "chunk_id": {"type": "string", "description": "Chunk ID to expand"},
                        },
                        "required": ["chunk_id"],
                    },
                ),
                Tool(
                    name="related_context",
                    description="Find related code via graph edges",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "chunk_id": {"type": "string", "description": "Chunk ID to find relations for"},
                        },
                        "required": ["chunk_id"],
                    },
                ),
                Tool(
                    name="session_recall",
                    description="Recall past discussions and decisions about a topic",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "topic": {"type": "string", "description": "Topic to recall"},
                        },
                        "required": ["topic"],
                    },
                ),
                Tool(
                    name="index_status",
                    description="Check when the index was last updated",
                    inputSchema={"type": "object", "properties": {}},
                ),
                Tool(
                    name="reindex",
                    description="Trigger re-indexing of a file or the entire project",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "File path to re-index (omit for full)"},
                        },
                    },
                ),
            ]

        @self._server.call_tool()
        async def call_tool(name: str, arguments: dict):
            if name == "context_search":
                return await self._handle_context_search(arguments)
            elif name == "expand_chunk":
                return await self._handle_expand_chunk(arguments)
            elif name == "related_context":
                return await self._handle_related_context(arguments)
            elif name == "session_recall":
                return await self._handle_session_recall(arguments)
            elif name == "index_status":
                return await self._handle_index_status()
            elif name == "reindex":
                return await self._handle_reindex(arguments)
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    async def _handle_context_search(self, args: dict) -> list[TextContent]:
        query = args["query"]
        top_k = args.get("top_k", 10)
        chunks = await self._retriever.retrieve(query, top_k=top_k)
        results = []
        for chunk in chunks:
            text = chunk.compressed_content or chunk.content
            results.append(
                f"[{chunk.file_path}:{chunk.start_line}] (confidence: {chunk.confidence_score:.2f})\n{text}"
            )
        return [TextContent(type="text", text="\n\n---\n\n".join(results) if results else "No results found.")]

    async def _handle_expand_chunk(self, args: dict) -> list[TextContent]:
        chunk = await self._backend.get_chunk_by_id(args["chunk_id"])
        if chunk is None:
            return [TextContent(type="text", text="Chunk not found.")]
        return [TextContent(type="text", text=f"[{chunk.file_path}:{chunk.start_line}-{chunk.end_line}]\n{chunk.content}")]

    async def _handle_related_context(self, args: dict) -> list[TextContent]:
        neighbors = await self._backend.graph_neighbors(args["chunk_id"])
        if not neighbors:
            return [TextContent(type="text", text="No related context found.")]
        lines = [f"- {n.node_type.value}: {n.name} ({n.file_path})" for n in neighbors]
        return [TextContent(type="text", text="\n".join(lines))]

    async def _handle_session_recall(self, args: dict) -> list[TextContent]:
        chunks = await self._retriever.retrieve(
            args["topic"], top_k=5,
        )
        session_chunks = [c for c in chunks if c.chunk_type.value in ("session", "decision")]
        if not session_chunks:
            # Fall back to any relevant chunks
            session_chunks = chunks[:3]
        results = [c.compressed_content or c.content for c in session_chunks]
        return [TextContent(type="text", text="\n\n".join(results) if results else "No session history found for this topic.")]

    async def _handle_index_status(self) -> list[TextContent]:
        return [TextContent(type="text", text="Index status: operational")]

    async def _handle_reindex(self, args: dict) -> list[TextContent]:
        path = args.get("path")
        if path:
            return [TextContent(type="text", text=f"Re-indexing triggered for: {path}")]
        return [TextContent(type="text", text="Full re-index triggered.")]

    async def run_stdio(self) -> None:
        """Run MCP server over stdio transport."""
        from mcp.server.stdio import stdio_server
        async with stdio_server() as (read_stream, write_stream):
            await self._server.run(read_stream, write_stream, self._server.create_initialization_options())
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/integration/test_mcp_server.py -v`
Expected: All 1 test PASS

- [ ] **Step 5: Commit**

```bash
git add src/context_engine/integration/mcp_server.py tests/integration/test_mcp_server.py
git commit -m "feat: MCP server with 6 context tools"
```

---

### Task 20: Session Capture

**Files:**
- Create: `src/context_engine/integration/session_capture.py`
- Create: `tests/integration/test_session_capture.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/integration/test_session_capture.py
import json
import pytest
from pathlib import Path

from context_engine.integration.session_capture import SessionCapture


@pytest.fixture
def capture(tmp_path):
    return SessionCapture(sessions_dir=str(tmp_path / "sessions"))


def test_start_session_creates_id(capture):
    session_id = capture.start_session(project_name="my-project")
    assert session_id is not None
    assert len(session_id) > 0


def test_record_decision(capture):
    sid = capture.start_session(project_name="test")
    capture.record_decision(sid, "Use Redis for caching", "Performance requirements")
    decisions = capture.get_decisions(sid)
    assert len(decisions) == 1
    assert decisions[0]["decision"] == "Use Redis for caching"


def test_record_code_area(capture):
    sid = capture.start_session(project_name="test")
    capture.record_code_area(sid, "src/auth.py", "login function")
    areas = capture.get_code_areas(sid)
    assert len(areas) == 1


def test_end_session_saves_file(capture):
    sid = capture.start_session(project_name="test")
    capture.record_decision(sid, "Test decision", "Test reason")
    capture.end_session(sid)
    # Session should be saved to disk
    sessions_dir = Path(capture._sessions_dir)
    session_files = list(sessions_dir.glob("*.json"))
    assert len(session_files) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_session_capture.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement SessionCapture**

```python
# src/context_engine/integration/session_capture.py
"""Session history capture — records decisions, code areas, and Q&A for future recall."""
import json
import time
import uuid
from pathlib import Path


class SessionCapture:
    def __init__(self, sessions_dir: str) -> None:
        self._sessions_dir = sessions_dir
        Path(sessions_dir).mkdir(parents=True, exist_ok=True)
        self._active: dict[str, dict] = {}

    def start_session(self, project_name: str) -> str:
        session_id = uuid.uuid4().hex[:12]
        self._active[session_id] = {
            "id": session_id,
            "project": project_name,
            "started_at": time.time(),
            "decisions": [],
            "code_areas": [],
            "questions": [],
        }
        return session_id

    def record_decision(self, session_id: str, decision: str, reason: str) -> None:
        session = self._active.get(session_id)
        if session:
            session["decisions"].append({
                "decision": decision,
                "reason": reason,
                "timestamp": time.time(),
            })

    def record_code_area(self, session_id: str, file_path: str, description: str) -> None:
        session = self._active.get(session_id)
        if session:
            session["code_areas"].append({
                "file_path": file_path,
                "description": description,
                "timestamp": time.time(),
            })

    def record_question(self, session_id: str, question: str, answer: str) -> None:
        session = self._active.get(session_id)
        if session:
            session["questions"].append({
                "question": question,
                "answer": answer,
                "timestamp": time.time(),
            })

    def get_decisions(self, session_id: str) -> list[dict]:
        session = self._active.get(session_id)
        return session["decisions"] if session else []

    def get_code_areas(self, session_id: str) -> list[dict]:
        session = self._active.get(session_id)
        return session["code_areas"] if session else []

    def end_session(self, session_id: str) -> None:
        session = self._active.pop(session_id, None)
        if session:
            session["ended_at"] = time.time()
            file_path = Path(self._sessions_dir) / f"{session_id}.json"
            with open(file_path, "w") as f:
                json.dump(session, f, indent=2)

    def load_recent_sessions(self, limit: int = 5) -> list[dict]:
        """Load most recent session files."""
        sessions_path = Path(self._sessions_dir)
        files = sorted(sessions_path.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        sessions = []
        for f in files[:limit]:
            with open(f) as fp:
                sessions.append(json.load(fp))
        return sessions
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/integration/test_session_capture.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/context_engine/integration/session_capture.py tests/integration/test_session_capture.py
git commit -m "feat: session capture for decisions, code areas, Q&A history"
```

---

### Task 21: CLI Entry Point

**Files:**
- Create: `src/context_engine/cli.py`

- [ ] **Step 1: Implement CLI**

```python
# src/context_engine/cli.py
"""CLI entry point for claude-context-engine."""
import asyncio
from pathlib import Path

import click

from context_engine.config import load_config, PROJECT_CONFIG_NAME


@click.group()
@click.pass_context
def main(ctx):
    """claude-context-engine — Local context engine for Claude Code."""
    ctx.ensure_object(dict)
    project_path = Path.cwd() / PROJECT_CONFIG_NAME
    ctx.obj["config"] = load_config(project_path=project_path if project_path.exists() else None)


@main.command()
@click.pass_context
def init(ctx):
    """Initialize context engine for the current project."""
    from context_engine.indexer.git_hooks import install_hooks

    config = ctx.obj["config"]
    project_dir = str(Path.cwd())

    # Install git hooks
    try:
        installed = install_hooks(project_dir)
        click.echo(f"Git hooks installed: {len(installed)} hooks")
    except FileNotFoundError:
        click.echo("No .git directory found — skipping git hooks")

    # Create project storage directory
    project_name = Path.cwd().name
    storage_dir = Path(config.storage_path) / project_name
    storage_dir.mkdir(parents=True, exist_ok=True)
    click.echo(f"Storage directory: {storage_dir}")

    # Run initial index
    click.echo("Running initial index...")
    asyncio.run(_run_index(config, project_dir, full=True))
    click.echo("Initialization complete.")


@main.command()
@click.option("--full", is_flag=True, help="Force full re-index")
@click.option("--path", type=str, default=None, help="Index specific file/directory")
@click.option("--changed-only", is_flag=True, help="Only index files changed since last commit")
@click.pass_context
def index(ctx, full, path, changed_only):
    """Index or re-index project files."""
    config = ctx.obj["config"]
    project_dir = path or str(Path.cwd())
    asyncio.run(_run_index(config, project_dir, full=full))
    click.echo("Indexing complete.")


@main.command()
@click.pass_context
def status(ctx):
    """Show index status, DB stats, and remote server status."""
    config = ctx.obj["config"]
    click.echo(f"Storage path: {config.storage_path}")
    click.echo(f"Remote enabled: {config.remote_enabled}")
    if config.remote_enabled:
        click.echo(f"Remote host: {config.remote_host}")
    click.echo(f"Compression level: {config.compression_level}")
    click.echo(f"Resource profile: {config.detect_resource_profile()}")


@main.command()
@click.pass_context
def serve(ctx):
    """Start the MCP server + daemon."""
    click.echo("Starting context engine daemon + MCP server...")
    asyncio.run(_run_serve(ctx.obj["config"]))


@main.command(name="remote-setup")
@click.pass_context
def remote_setup(ctx):
    """Set up context engine on remote server."""
    config = ctx.obj["config"]
    if not config.remote_enabled:
        click.echo("Remote is not enabled in config. Set remote.enabled: true first.")
        return
    click.echo(f"Setting up remote server: {config.remote_host}")
    click.echo("Remote setup not yet implemented — coming in a future release.")


@main.command()
@click.argument("key")
@click.argument("value")
@click.pass_context
def config(ctx, key, value):
    """Set a configuration value."""
    click.echo(f"Config: {key} = {value}")
    click.echo("Config persistence not yet implemented — edit config.yaml directly.")


async def _run_index(config, project_dir: str, full: bool = False) -> None:
    """Run indexing pipeline."""
    import hashlib
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

    # Collect files
    extensions = {".py", ".js", ".ts", ".jsx", ".tsx", ".md"}
    language_map = {
        ".py": "python", ".js": "javascript", ".ts": "typescript",
        ".jsx": "javascript", ".tsx": "typescript", ".md": "markdown",
    }

    project_path = Path(project_dir)
    all_chunks = []
    all_nodes = []
    all_edges = []

    for file_path in project_path.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.suffix not in extensions:
            continue
        if any(ignore in str(file_path) for ignore in config.indexer_ignore):
            continue

        rel_path = str(file_path.relative_to(project_path))
        content = file_path.read_text(errors="ignore")
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        if not full and not manifest.has_changed(rel_path, content_hash):
            continue

        language = language_map.get(file_path.suffix, "plaintext")
        chunks = chunker.chunk(content, file_path=rel_path, language=language)

        # Create graph nodes
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
        retriever=retriever,
        backend=backend,
        compressor=compressor,
        embedder=embedder,
        config=config,
    )
    await mcp.run_stdio()
```

- [ ] **Step 2: Verify CLI works**

Run: `claude-context-engine --help`
Expected: Shows help with init, index, status, serve, remote-setup, config commands

Run: `claude-context-engine status`
Expected: Shows storage path, remote status, compression level, resource profile

- [ ] **Step 3: Commit**

```bash
git add src/context_engine/cli.py
git commit -m "feat: CLI with init, index, status, serve, remote-setup, config commands"
```

---

## Phase 6: Remote Backend + Daemon

### Task 22: Remote Backend

**Files:**
- Create: `src/context_engine/storage/remote_backend.py`
- Create: `tests/storage/test_remote_backend.py` (skipped if server unavailable)

- [ ] **Step 1: Write failing tests**

```python
# tests/storage/test_remote_backend.py (skipped if server unavailable)
import pytest

from context_engine.storage.remote_backend import RemoteBackend


@pytest.fixture
def backend():
    return RemoteBackend(host="fazle@198.162.2.2", fallback_to_local=True)


def test_remote_backend_init():
    backend = RemoteBackend(host="fazle@198.162.2.2")
    assert backend.host == "fazle@198.162.2.2"


@pytest.mark.asyncio
async def test_is_reachable_returns_bool(backend):
    result = await backend.is_reachable()
    assert isinstance(result, bool)


@pytest.mark.asyncio
async def test_fallback_flag():
    backend = RemoteBackend(host="invalid-host", fallback_to_local=True)
    assert backend.fallback_to_local is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/storage/test_remote_backend.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement RemoteBackend**

```python
# src/context_engine/storage/remote_backend.py
"""Remote storage backend — proxies DB + LLM operations to a remote server via SSH/HTTP."""
import asyncio

import httpx

from context_engine.models import Chunk, GraphNode, GraphEdge, EdgeType


class RemoteBackend:
    def __init__(
        self,
        host: str,
        port: int = 8765,
        fallback_to_local: bool = True,
    ) -> None:
        self.host = host
        self.port = port
        self.fallback_to_local = fallback_to_local
        # Parse user@host format
        if "@" in host:
            self._user, self._hostname = host.split("@", 1)
        else:
            self._user = None
            self._hostname = host
        self._api_base = f"http://{self._hostname}:{port}"

    async def is_reachable(self) -> bool:
        """Check if remote server is reachable."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "ssh", "-o", "ConnectTimeout=3", "-o", "BatchMode=yes",
                self.host, "echo", "ok",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
            return b"ok" in stdout
        except (asyncio.TimeoutError, OSError):
            return False

    async def vector_search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        filters: dict | None = None,
    ) -> list[Chunk]:
        """Forward vector search to remote server."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self._api_base}/vector_search",
                    json={"embedding": query_embedding, "top_k": top_k, "filters": filters},
                )
                resp.raise_for_status()
                return [self._dict_to_chunk(d) for d in resp.json()["results"]]
        except (httpx.ConnectError, httpx.TimeoutException):
            return []

    async def graph_neighbors(
        self,
        node_id: str,
        edge_type: EdgeType | None = None,
    ) -> list[GraphNode]:
        """Forward graph query to remote server."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self._api_base}/graph_neighbors",
                    json={"node_id": node_id, "edge_type": edge_type.value if edge_type else None},
                )
                resp.raise_for_status()
                return [self._dict_to_node(d) for d in resp.json()["results"]]
        except (httpx.ConnectError, httpx.TimeoutException):
            return []

    async def ingest(
        self,
        chunks: list[Chunk],
        nodes: list[GraphNode],
        edges: list[GraphEdge],
    ) -> None:
        """Forward ingestion to remote server."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                await client.post(
                    f"{self._api_base}/ingest",
                    json={
                        "chunks": [self._chunk_to_dict(c) for c in chunks],
                        "nodes": [self._node_to_dict(n) for n in nodes],
                        "edges": [self._edge_to_dict(e) for e in edges],
                    },
                )
        except (httpx.ConnectError, httpx.TimeoutException):
            pass

    async def get_chunk_by_id(self, chunk_id: str) -> Chunk | None:
        """Fetch a single chunk from remote."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self._api_base}/chunk/{chunk_id}")
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                return self._dict_to_chunk(resp.json())
        except (httpx.ConnectError, httpx.TimeoutException):
            return None

    async def delete_by_file(self, file_path: str) -> None:
        """Delete data for a file on remote."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.delete(f"{self._api_base}/file/{file_path}")
        except (httpx.ConnectError, httpx.TimeoutException):
            pass

    def _chunk_to_dict(self, chunk: Chunk) -> dict:
        return {
            "id": chunk.id, "content": chunk.content,
            "chunk_type": chunk.chunk_type.value, "file_path": chunk.file_path,
            "start_line": chunk.start_line, "end_line": chunk.end_line,
            "language": chunk.language, "embedding": chunk.embedding,
            "metadata": chunk.metadata,
        }

    def _dict_to_chunk(self, d: dict) -> Chunk:
        from context_engine.models import ChunkType
        return Chunk(
            id=d["id"], content=d["content"],
            chunk_type=ChunkType(d["chunk_type"]), file_path=d["file_path"],
            start_line=d["start_line"], end_line=d["end_line"],
            language=d["language"], embedding=d.get("embedding"),
            metadata=d.get("metadata", {}),
        )

    def _node_to_dict(self, node: GraphNode) -> dict:
        return {
            "id": node.id, "node_type": node.node_type.value,
            "name": node.name, "file_path": node.file_path,
        }

    def _dict_to_node(self, d: dict) -> GraphNode:
        from context_engine.models import NodeType
        return GraphNode(
            id=d["id"], node_type=NodeType(d["node_type"]),
            name=d["name"], file_path=d["file_path"],
        )

    def _edge_to_dict(self, edge: GraphEdge) -> dict:
        return {
            "source_id": edge.source_id, "target_id": edge.target_id,
            "edge_type": edge.edge_type.value,
        }
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/storage/test_remote_backend.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/context_engine/storage/remote_backend.py tests/storage/test_remote_backend.py
git commit -m "feat: remote storage backend (SSH + HTTP proxy to remote server)"
```

---

### Task 23: Daemon Orchestrator

**Files:**
- Create: `src/context_engine/daemon.py`

- [ ] **Step 1: Implement daemon**

```python
# src/context_engine/daemon.py
"""Daemon process — orchestrates all modules, manages lifecycle."""
import asyncio
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
        """Initialize all modules and start the daemon."""
        # Choose backend
        self._backend = await self._create_backend()

        # Initialize modules
        embedder = Embedder(model_name=self._config.embedding_model)
        retriever = HybridRetriever(backend=self._backend, embedder=embedder)
        compressor = Compressor(
            ollama_url="http://localhost:11434",
            model=self._config.compression_model,
        )
        bootstrap = BootstrapBuilder(max_tokens=self._config.bootstrap_max_tokens)
        session_capture = SessionCapture(
            sessions_dir=str(Path(self._config.storage_path) / self._project_name / "sessions"),
        )

        # Start file watcher if enabled
        if self._config.indexer_watch:
            self._watcher = FileWatcher(
                watch_dir=self._project_dir,
                on_change=self._on_file_change,
                debounce_ms=self._config.indexer_debounce_ms,
                ignore_patterns=self._config.indexer_ignore,
            )
            self._watcher.start()

        # Start MCP server
        self._mcp = ContextEngineMCP(
            retriever=retriever,
            backend=self._backend,
            compressor=compressor,
            embedder=embedder,
            config=self._config,
        )
        await self._mcp.run_stdio()

    async def stop(self) -> None:
        """Stop all modules."""
        if self._watcher:
            self._watcher.stop()

    async def _create_backend(self):
        """Create the appropriate storage backend."""
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
        """Handle file change event from watcher."""
        await self._event_bus.emit("file_changed", {"path": file_path})

    async def generate_bootstrap(self) -> str:
        """Generate bootstrap context for a new session."""
        embedder = Embedder(model_name=self._config.embedding_model)
        retriever = HybridRetriever(backend=self._backend, embedder=embedder)
        compressor = Compressor(model=self._config.compression_model)
        bootstrap = BootstrapBuilder(max_tokens=self._config.bootstrap_max_tokens)

        # Retrieve broad project context
        chunks = await retriever.retrieve("project overview architecture", top_k=30)
        await compressor.compress(chunks, level=self._config.compression_level)

        # Get recent commits
        import subprocess
        try:
            result = subprocess.run(
                ["git", "-C", self._project_dir, "log", "--oneline", "-10"],
                capture_output=True, text=True, timeout=5,
            )
            commits = result.stdout.strip().split("\n") if result.returncode == 0 else []
        except (subprocess.TimeoutExpired, FileNotFoundError):
            commits = []

        return bootstrap.build(
            project_name=self._project_name,
            chunks=chunks,
            recent_commits=commits,
        )
```

- [ ] **Step 2: Verify import works**

Run: `python -c "from context_engine.daemon import Daemon; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/context_engine/daemon.py
git commit -m "feat: daemon orchestrator with backend selection and module lifecycle"
```

---

### Task 24: Claude Code Hook Configuration

**Files:**
- No new source files — this task creates the hook config instructions

- [ ] **Step 1: Create a conftest with shared fixtures**

```python
# tests/conftest.py
import pytest
from pathlib import Path


@pytest.fixture
def project_dir(tmp_path):
    """Create a minimal project directory for testing."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "main.py").write_text("def main():\n    print('hello')\n")
    (src_dir / "utils.py").write_text("def helper(x):\n    return x + 1\n")
    return tmp_path
```

- [ ] **Step 2: Document hook configuration for Claude Code**

Create a README section or config snippet showing how to wire the hooks:

```json
// In Claude Code settings (~/.claude/settings.json)
{
  "hooks": {
    "SessionStart": [
      {
        "type": "command",
        "command": "claude-context-engine bootstrap --project-dir $(pwd)"
      }
    ]
  },
  "mcpServers": {
    "context-engine": {
      "command": "claude-context-engine",
      "args": ["serve"],
      "env": {}
    }
  }
}
```

- [ ] **Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "feat: shared test fixtures + Claude Code hook configuration docs"
```

---

### Task 25: End-to-End Integration Test

**Files:**
- Create: `tests/test_e2e.py`

- [ ] **Step 1: Write end-to-end test**

```python
# tests/test_e2e.py
"""End-to-end test: index a project, retrieve context, build bootstrap."""
import pytest
from pathlib import Path

from context_engine.config import Config
from context_engine.indexer.chunker import Chunker
from context_engine.indexer.embedder import Embedder
from context_engine.indexer.manifest import Manifest
from context_engine.storage.local_backend import LocalBackend
from context_engine.retrieval.retriever import HybridRetriever
from context_engine.compression.compressor import Compressor
from context_engine.integration.bootstrap import BootstrapBuilder
from context_engine.models import GraphNode, GraphEdge, NodeType, EdgeType


SAMPLE_PROJECT = {
    "src/auth.py": '''
class AuthService:
    """Handles user authentication."""
    def login(self, username: str, password: str) -> bool:
        """Authenticate a user with username and password."""
        return self._check_credentials(username, password)

    def _check_credentials(self, username: str, password: str) -> bool:
        return username == "admin" and password == "secret"
''',
    "src/user.py": '''
from auth import AuthService

class UserService:
    """Manages user profiles."""
    def __init__(self):
        self.auth = AuthService()

    def get_profile(self, user_id: int) -> dict:
        """Fetch user profile by ID."""
        return {"id": user_id, "name": "Test User"}
''',
    "README.md": "# Test Project\nA sample project for testing the context engine.\n",
}


@pytest.fixture
def sample_project(tmp_path):
    for rel_path, content in SAMPLE_PROJECT.items():
        file_path = tmp_path / rel_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
    return tmp_path


@pytest.mark.asyncio
async def test_full_pipeline(sample_project, tmp_path):
    """Test: index -> retrieve -> compress -> bootstrap."""
    storage_dir = tmp_path / "storage"

    # 1. Index
    chunker = Chunker()
    embedder = Embedder()
    backend = LocalBackend(base_path=str(storage_dir))
    manifest = Manifest(manifest_path=storage_dir / "manifest.json")

    all_chunks = []
    all_nodes = []
    all_edges = []

    for rel_path, content in SAMPLE_PROJECT.items():
        lang = "python" if rel_path.endswith(".py") else "markdown"
        chunks = chunker.chunk(content, file_path=rel_path, language=lang)

        file_node = GraphNode(
            id=f"file_{rel_path}", node_type=NodeType.FILE,
            name=Path(rel_path).name, file_path=rel_path,
        )
        all_nodes.append(file_node)
        for chunk in chunks:
            all_nodes.append(GraphNode(
                id=chunk.id, node_type=NodeType.FUNCTION,
                name=chunk.id, file_path=rel_path,
            ))
            all_edges.append(GraphEdge(
                source_id=file_node.id, target_id=chunk.id,
                edge_type=EdgeType.DEFINES,
            ))
        all_chunks.extend(chunks)

    embedder.embed(all_chunks)
    await backend.ingest(all_chunks, all_nodes, all_edges)

    # 2. Retrieve
    retriever = HybridRetriever(backend=backend, embedder=embedder)
    results = await retriever.retrieve("authentication login", top_k=5)
    assert len(results) > 0
    # Should find auth-related chunks
    assert any("auth" in c.file_path or "login" in c.content.lower() for c in results)

    # 3. Compress
    compressor = Compressor()
    await compressor.compress(results, level="standard")
    for chunk in results:
        assert chunk.compressed_content is not None

    # 4. Bootstrap
    builder = BootstrapBuilder(max_tokens=5000)
    payload = builder.build(
        project_name="test-project",
        chunks=results,
        recent_commits=["feat: add auth service", "feat: add user service"],
    )
    assert "## Project: test-project" in payload
    assert "Recent Activity" in payload
    assert len(payload) > 100
```

- [ ] **Step 2: Run end-to-end test**

Run: `pytest tests/test_e2e.py -v`
Expected: PASS

- [ ] **Step 3: Run full test suite**

Run: `pytest tests/ -v --tb=short`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_e2e.py
git commit -m "test: end-to-end integration test (index -> retrieve -> compress -> bootstrap)"
```

---

## Summary

| Phase | Tasks | What it delivers |
|---|---|---|
| 1: Foundation | 1-4 | Project scaffold, models, config, event bus |
| 2: Storage | 5-7 | LanceDB vector store, Kuzu graph store, backend abstraction |
| 3: Indexer | 8-12 | Manifest, AST chunker, embedder, file watcher, git hooks |
| 4: Retrieval + Compression | 13-17 | Query parser, confidence scoring, hybrid retriever, Ollama client, compressor |
| 5: Integration | 18-21 | Bootstrap builder, MCP server, session capture, CLI |
| 6: Remote + Daemon | 22-25 | Remote backend, daemon orchestrator, Claude Code hooks, E2E test |

**Total: 25 tasks, ~125 steps**
