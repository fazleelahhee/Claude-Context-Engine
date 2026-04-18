"""LanceDB-backed vector store for chunk embeddings."""
import asyncio
import logging
import math
from pathlib import Path
from threading import RLock

import lancedb
import pyarrow as pa

from context_engine.models import Chunk, ChunkType

log = logging.getLogger(__name__)

TABLE_NAME = "chunks"
_INDEX_THRESHOLD = 10_000


def _escape_sql_literal(value) -> str:
    """Quote a value for inline use in a LanceDB `where` filter.

    LanceDB doesn't expose a positional-parameter API everywhere, so we build
    strings — but every inline value must be escaped to prevent both breakage on
    apostrophes in file paths and any filter-injection shenanigans.
    """
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


class VectorStore:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._db = lancedb.connect(db_path)
        self._lock = RLock()
        try:
            self._table = self._db.open_table(TABLE_NAME)
        except Exception:
            self._table = None

    def _ensure_table(self, vector_dim: int) -> None:
        with self._lock:
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
        chunk = Chunk(
            id=row["id"],
            content=row["content"],
            chunk_type=ChunkType(row["chunk_type"]),
            file_path=row["file_path"],
            start_line=row["start_line"],
            end_line=row["end_line"],
            language=row["language"],
            embedding=row.get("vector"),
        )
        # LanceDB returns the similarity distance as `_distance` on search rows.
        # Surface it in metadata so the retriever can use the real value instead
        # of reconstructing one from the result rank.
        if "_distance" in row and row["_distance"] is not None:
            chunk.metadata["_distance"] = float(row["_distance"])
        return chunk

    async def _maybe_create_index(self) -> None:
        """Create an IVF_PQ index once the table exceeds the threshold."""
        with self._lock:
            if self._table is None:
                return
            try:
                count = self._table.count_rows()
            except Exception:
                return
            if count < _INDEX_THRESHOLD:
                return
        try:
            num_partitions = max(256, int(math.sqrt(count)))
            await asyncio.to_thread(
                self._table.create_index,
                metric="cosine",
                num_partitions=num_partitions,
                num_sub_vectors=16,
            )
            log.info("Created ANN index on %d chunks", count)
        except Exception as exc:
            log.debug("ANN index creation skipped: %s", exc)

    async def ingest(self, chunks: list[Chunk]) -> None:
        if not chunks:
            return
        vector_dim = len(chunks[0].embedding)
        self._ensure_table(vector_dim)
        rows = [self._chunk_to_row(c) for c in chunks if c.embedding]
        with self._lock:
            self._table.add(rows)
        await self._maybe_create_index()

    async def search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        filters: dict | None = None,
    ) -> list[Chunk]:
        with self._lock:
            if self._table is None:
                try:
                    self._table = self._db.open_table(TABLE_NAME)
                except Exception:
                    return []
            query = self._table.search(query_embedding).limit(top_k)
            if filters:
                where_clauses = [
                    f"{key} = {_escape_sql_literal(value)}"
                    for key, value in filters.items()
                ]
                query = query.where(" AND ".join(where_clauses))
            results = query.to_list()
        return [self._row_to_chunk(row) for row in results]

    async def delete_by_file(self, file_path: str) -> None:
        with self._lock:
            if self._table is None:
                return
            self._table.delete(f"file_path = {_escape_sql_literal(file_path)}")

    def count(self) -> int:
        """Return total number of chunks in the table."""
        with self._lock:
            if self._table is None:
                try:
                    self._table = self._db.open_table(TABLE_NAME)
                except Exception:
                    return 0
            try:
                return self._table.count_rows()
            except Exception:
                return 0

    def file_chunk_counts(self) -> dict[str, int]:
        """Return {file_path: chunk_count} for all indexed files."""
        with self._lock:
            if self._table is None:
                try:
                    self._table = self._db.open_table(TABLE_NAME)
                except Exception:
                    return {}
            try:
                rows = self._table.to_arrow().to_pydict()
                counts: dict[str, int] = {}
                for fp in rows.get("file_path", []):
                    counts[fp] = counts.get(fp, 0) + 1
                return counts
            except Exception:
                return {}

    def clear(self) -> None:
        """Drop the chunks table, resetting the vector store."""
        with self._lock:
            if self._table is not None:
                try:
                    self._db.drop_table(TABLE_NAME)
                except Exception:
                    pass
                self._table = None

    async def get_by_id(self, chunk_id: str) -> Chunk | None:
        with self._lock:
            if self._table is None:
                try:
                    self._table = self._db.open_table(TABLE_NAME)
                except Exception:
                    return None
            results = (
                self._table.search()
                .where(f"id = {_escape_sql_literal(chunk_id)}")
                .limit(1)
                .to_list()
            )
        if not results:
            return None
        return self._row_to_chunk(results[0])

    async def get_chunks_by_ids(self, chunk_ids: list[str]) -> list[Chunk]:
        if not chunk_ids:
            return []
        with self._lock:
            if self._table is None:
                try:
                    self._table = self._db.open_table(TABLE_NAME)
                except Exception:
                    return []
            quoted = ", ".join(_escape_sql_literal(i) for i in chunk_ids)
            results = (
                self._table.search()
                .where(f"id IN ({quoted})")
                .limit(len(chunk_ids))
                .to_list()
            )
        return [self._row_to_chunk(r) for r in results]
