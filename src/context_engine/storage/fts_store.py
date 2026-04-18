"""SQLite FTS5 full-text search store."""
import asyncio
import logging
import os
import sqlite3

from context_engine.models import Chunk

log = logging.getLogger(__name__)


def _escape_fts5(query: str) -> str:
    """Wrap user input as an FTS5 phrase to avoid operator injection."""
    return '"' + query.replace('"', '""') + '"'


class FTSStore:
    def __init__(self, db_path: str) -> None:
        os.makedirs(db_path, exist_ok=True)
        self._conn = sqlite3.connect(
            os.path.join(db_path, "fts.db"), check_same_thread=False
        )
        self._conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts "
            "USING fts5(id UNINDEXED, content, file_path, language, chunk_type)"
        )
        self._conn.commit()

    def _ingest_sync(self, chunks: list[Chunk]) -> None:
        cursor = self._conn.cursor()
        for chunk in chunks:
            cursor.execute(
                "INSERT OR REPLACE INTO chunks_fts(id, content, file_path, language, chunk_type) "
                "VALUES (?, ?, ?, ?, ?)",
                (chunk.id, chunk.content, chunk.file_path, chunk.language, chunk.chunk_type.value),
            )
        self._conn.commit()

    def _search_sync(self, escaped_query: str, top_k: int) -> list[tuple[str, float]]:
        cursor = self._conn.execute(
            "SELECT id, rank FROM chunks_fts WHERE chunks_fts MATCH ? "
            "ORDER BY rank LIMIT ?",
            (escaped_query, top_k),
        )
        return [(row[0], float(row[1])) for row in cursor.fetchall()]

    def _delete_sync(self, file_path: str) -> None:
        self._conn.execute(
            "DELETE FROM chunks_fts WHERE file_path = ?", (file_path,)
        )
        self._conn.commit()

    async def ingest(self, chunks: list[Chunk]) -> None:
        if not chunks:
            return
        await asyncio.to_thread(self._ingest_sync, chunks)

    async def search(self, query: str, top_k: int = 30) -> list[tuple[str, float]]:
        if not query.strip():
            return []
        return await asyncio.to_thread(self._search_sync, _escape_fts5(query), top_k)

    async def delete_by_file(self, file_path: str) -> None:
        await asyncio.to_thread(self._delete_sync, file_path)
