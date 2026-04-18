"""Local storage backend — LanceDB vector store."""
from pathlib import Path

from context_engine.models import Chunk, GraphNode, GraphEdge, EdgeType
from context_engine.storage.vector_store import VectorStore


class LocalBackend:
    def __init__(self, base_path: str) -> None:
        self._vector_store = VectorStore(db_path=str(Path(base_path) / "vectors"))

    async def ingest(
        self,
        chunks: list[Chunk],
        nodes: list[GraphNode],
        edges: list[GraphEdge],
    ) -> None:
        await self._vector_store.ingest(chunks)

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
        return []

    async def get_chunk_by_id(self, chunk_id: str) -> Chunk | None:
        return await self._vector_store.get_by_id(chunk_id)

    async def delete_by_file(self, file_path: str) -> None:
        await self._vector_store.delete_by_file(file_path)

    def count_chunks(self) -> int:
        return self._vector_store.count()

    def file_chunk_counts(self) -> dict[str, int]:
        return self._vector_store.file_chunk_counts()

    async def clear(self) -> None:
        self._vector_store.clear()
