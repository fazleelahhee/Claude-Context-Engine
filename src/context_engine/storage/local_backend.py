"""Local storage backend — LanceDB vectors + SQLite FTS + SQLite graph."""
import asyncio
from pathlib import Path

from context_engine.models import Chunk, GraphNode, GraphEdge, EdgeType
from context_engine.storage.vector_store import VectorStore
from context_engine.storage.fts_store import FTSStore
from context_engine.storage.graph_store import GraphStore


class LocalBackend:
    def __init__(self, base_path: str) -> None:
        self._vector_store = VectorStore(db_path=str(Path(base_path) / "vectors"))
        self._fts_store = FTSStore(db_path=str(Path(base_path) / "fts"))
        self._graph_store = GraphStore(db_path=str(Path(base_path) / "graph"))

    async def ingest(
        self,
        chunks: list[Chunk],
        nodes: list[GraphNode],
        edges: list[GraphEdge],
    ) -> None:
        await asyncio.gather(
            self._vector_store.ingest(chunks),
            self._fts_store.ingest(chunks),
            self._graph_store.ingest(nodes, edges),
        )

    async def vector_search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        filters: dict | None = None,
    ) -> list[Chunk]:
        return await self._vector_store.search(query_embedding, top_k, filters)

    async def fts_search(
        self,
        query: str,
        top_k: int = 30,
    ) -> list[tuple[str, float]]:
        return await self._fts_store.search(query, top_k)

    async def graph_neighbors(
        self,
        node_id: str,
        edge_type: EdgeType | None = None,
    ) -> list[GraphNode]:
        return await self._graph_store.get_neighbors(node_id, edge_type)

    async def get_chunk_by_id(self, chunk_id: str) -> Chunk | None:
        return await self._vector_store.get_by_id(chunk_id)

    async def get_chunks_by_ids(self, chunk_ids: list[str]) -> list[Chunk]:
        return await self._vector_store.get_chunks_by_ids(chunk_ids)

    async def delete_by_file(self, file_path: str) -> None:
        await asyncio.gather(
            self._vector_store.delete_by_file(file_path),
            self._fts_store.delete_by_file(file_path),
            self._graph_store.delete_by_file(file_path),
        )
