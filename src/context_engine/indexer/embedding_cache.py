"""SQLite-backed embedding cache keyed by content hash.

Avoids recomputing embeddings for unchanged code chunks across re-index runs.
Inspired by Cursor's approach of caching embeddings by chunk content hash so
identical code is never re-embedded.
"""
import hashlib
import json
import logging
import sqlite3
from pathlib import Path

log = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS embedding_cache (
    content_hash TEXT PRIMARY KEY,
    embedding    TEXT NOT NULL
);
"""


class EmbeddingCache:
    """Maps content SHA-256 → embedding vector, persisted in SQLite."""

    def __init__(self, cache_path: Path) -> None:
        self._path = cache_path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(_SCHEMA)
        self._conn.commit()
        self._hits = 0
        self._misses = 0

    @staticmethod
    def content_hash(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def get(self, content_hash: str) -> list[float] | None:
        row = self._conn.execute(
            "SELECT embedding FROM embedding_cache WHERE content_hash = ?",
            (content_hash,),
        ).fetchone()
        if row is None:
            self._misses += 1
            return None
        self._hits += 1
        return json.loads(row[0])

    def put(self, content_hash: str, embedding: list[float]) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO embedding_cache (content_hash, embedding) VALUES (?, ?)",
            (content_hash, json.dumps(embedding)),
        )
        self._conn.commit()

    def put_batch(self, items: list[tuple[str, list[float]]]) -> None:
        self._conn.executemany(
            "INSERT OR REPLACE INTO embedding_cache (content_hash, embedding) VALUES (?, ?)",
            [(h, json.dumps(e)) for h, e in items],
        )
        self._conn.commit()

    def get_batch(self, content_hashes: list[str]) -> dict[str, list[float]]:
        """Retrieve multiple embeddings at once. Returns hash → embedding for hits."""
        if not content_hashes:
            return {}
        results: dict[str, list[float]] = {}
        # SQLite has a limit on query variables; batch in chunks of 500
        for i in range(0, len(content_hashes), 500):
            batch = content_hashes[i : i + 500]
            placeholders = ",".join("?" * len(batch))
            rows = self._conn.execute(
                f"SELECT content_hash, embedding FROM embedding_cache WHERE content_hash IN ({placeholders})",
                batch,
            ).fetchall()
            for h, emb in rows:
                results[h] = json.loads(emb)
        self._hits += len(results)
        self._misses += len(content_hashes) - len(results)
        return results

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
        row = self._conn.execute("SELECT COUNT(*) FROM embedding_cache").fetchone()
        return row[0] if row else 0

    def close(self) -> None:
        self._conn.close()
