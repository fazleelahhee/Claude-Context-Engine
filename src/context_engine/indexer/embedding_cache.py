"""SQLite-backed embedding cache keyed by (content hash, model name).

Avoids recomputing embeddings for unchanged code chunks across re-index runs.
Inspired by Cursor's approach of caching embeddings by chunk content hash so
identical code is never re-embedded.

The cache key includes the embedding model name so a switch from e.g.
BAAI/bge-small-en-v1.5 (384-dim) to all-MiniLM-L6-v2 (384-dim, different
training) can't silently reuse the wrong vectors. Without this, a model
swap would either return semantically-wrong embeddings or — when the new
model has a different dim — surface as a sqlite-vec ingest failure.

Vectors are stored via `struct.pack` (binary float32) rather than JSON —
same encoding the sqlite-vec store uses elsewhere in the codebase. JSON
would be ~4× larger on disk for typical 384-dim embeddings.
"""
import hashlib
import logging
import sqlite3
import struct
from pathlib import Path
from threading import RLock

from context_engine.utils import SQLITE_PARAM_BATCH, chunked

log = logging.getLogger(__name__)

# Schema v2 — adds `model` to the primary key. v1 (content_hash-only) is
# detected by the absence of the `model` column and dropped on open.
_SCHEMA_V2 = """
CREATE TABLE IF NOT EXISTS embedding_cache (
    content_hash TEXT NOT NULL,
    model        TEXT NOT NULL,
    dim          INTEGER NOT NULL,
    embedding    BLOB NOT NULL,
    PRIMARY KEY (content_hash, model)
);
"""

# Used when a caller doesn't pass a model name (only legacy paths). Anything
# new should pass an explicit model.
_DEFAULT_MODEL = "unspecified"


class EmbeddingCache:
    """Maps (content SHA-256, model) → embedding vector, persisted in SQLite.

    Thread-safe: a single sqlite3 connection is shared across `to_thread`
    workers and serialised with an RLock, mirroring the rest of the storage
    layer (VectorStore, FTSStore, GraphStore).
    """

    def __init__(self, cache_path: Path, model_name: str | None = None) -> None:
        self._path = cache_path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._model = model_name or _DEFAULT_MODEL
        # check_same_thread=False so the cache can be used from any thread —
        # `_lock` provides the actual concurrency guarantee. Embedder runs
        # the cache lookups from the asyncio event loop AND from worker
        # threads via asyncio.to_thread; both paths must be safe.
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._migrate_if_needed()
            self._conn.execute(_SCHEMA_V2)
            self._conn.commit()
        self._hits = 0
        self._misses = 0

    def _migrate_if_needed(self) -> None:
        """Drop a v1 (content_hash-only) table if found.

        v1 cached vectors with no model attribution, so reusing them after a
        model swap could return wrong-dimension or wrong-meaning embeddings.
        Dropping is safe — vectors are recomputable; the cache is purely a
        speed-up, not authoritative storage.
        """
        cur = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='embedding_cache'"
        ).fetchone()
        if cur is None:
            return
        cols = {row[1] for row in self._conn.execute("PRAGMA table_info(embedding_cache)")}
        if "model" not in cols:
            log.info(
                "Dropping pre-v2 embedding_cache (no model column) — vectors will "
                "be regenerated on next index, keyed by model going forward"
            )
            self._conn.execute("DROP TABLE embedding_cache")

    @staticmethod
    def content_hash(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @staticmethod
    def _pack(vec) -> bytes:
        v = list(vec) if not isinstance(vec, list) else vec
        return struct.pack(f"{len(v)}f", *v)

    @staticmethod
    def _unpack(blob: bytes, dim: int) -> list[float]:
        return list(struct.unpack(f"{dim}f", blob))

    def get(self, content_hash: str) -> list[float] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT dim, embedding FROM embedding_cache "
                "WHERE content_hash = ? AND model = ?",
                (content_hash, self._model),
            ).fetchone()
        if row is None:
            self._misses += 1
            return None
        self._hits += 1
        return self._unpack(row[1], row[0])

    def put(self, content_hash: str, embedding) -> None:
        v = list(embedding) if not isinstance(embedding, list) else embedding
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO embedding_cache "
                "(content_hash, model, dim, embedding) VALUES (?, ?, ?, ?)",
                (content_hash, self._model, len(v), self._pack(v)),
            )
            self._conn.commit()

    def put_batch(self, items: list[tuple[str, list[float]]]) -> None:
        rows = [(h, self._model, len(e), self._pack(e)) for h, e in items]
        with self._lock:
            self._conn.executemany(
                "INSERT OR REPLACE INTO embedding_cache "
                "(content_hash, model, dim, embedding) VALUES (?, ?, ?, ?)",
                rows,
            )
            self._conn.commit()

    def get_batch(self, content_hashes: list[str]) -> dict[str, list[float]]:
        """Retrieve multiple embeddings at once. Returns hash → embedding for hits."""
        if not content_hashes:
            return {}
        results: dict[str, list[float]] = {}
        with self._lock:
            for batch in chunked(content_hashes, SQLITE_PARAM_BATCH):
                placeholders = ",".join("?" * len(batch))
                rows = self._conn.execute(
                    f"SELECT content_hash, dim, embedding FROM embedding_cache "
                    f"WHERE model = ? AND content_hash IN ({placeholders})",
                    [self._model, *batch],
                ).fetchall()
                for h, dim, blob in rows:
                    results[h] = self._unpack(blob, dim)
        self._hits += len(results)
        self._misses += len(content_hashes) - len(results)
        return results

    def prune_orphans(self, known_hashes: set[str]) -> int:
        """Drop cached entries whose content_hash is not in `known_hashes`.

        Cache grows monotonically without this — every chunk content variant
        ever seen accumulates forever even after the source files change or
        get deleted. Call this after a `cce index --full` with the set of
        hashes still present in the live index. Returns the count removed.

        Only entries for the current model are considered: an explicit
        per-model prune avoids accidentally wiping cached vectors for other
        models that share the cache file.
        """
        if not known_hashes:
            # Refuse to wipe everything on an empty set — almost certainly a
            # caller bug (e.g. forgetting to populate the set). Explicit
            # `clear()` should be added if a real wipe is wanted.
            return 0
        with self._lock:
            cur = self._conn.execute(
                "SELECT content_hash FROM embedding_cache WHERE model = ?",
                (self._model,),
            )
            current = {row[0] for row in cur.fetchall()}
            orphans = current - known_hashes
            if not orphans:
                return 0
            removed = 0
            for batch in chunked(orphans, SQLITE_PARAM_BATCH):
                placeholders = ",".join("?" * len(batch))
                self._conn.execute(
                    f"DELETE FROM embedding_cache "
                    f"WHERE model = ? AND content_hash IN ({placeholders})",
                    [self._model, *batch],
                )
                removed += len(batch)
            self._conn.commit()
        return removed

    @property
    def hits(self) -> int:
        return self._hits

    @property
    def misses(self) -> int:
        return self._misses

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    def size(self) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM embedding_cache WHERE model = ?",
                (self._model,),
            ).fetchone()
        return row[0] if row else 0

    def close(self) -> None:
        with self._lock:
            self._conn.close()
