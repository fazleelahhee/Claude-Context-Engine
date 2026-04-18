"""HTTP API server for remote context engine — exposes storage + compression endpoints."""
import asyncio
import json
from pathlib import Path

from context_engine.config import load_config, PROJECT_CONFIG_NAME
from context_engine.storage.local_backend import LocalBackend
from context_engine.indexer.embedder import Embedder
from context_engine.retrieval.retriever import HybridRetriever
from context_engine.compression.compressor import Compressor
from context_engine.models import Chunk, ChunkType, GraphNode, GraphEdge, NodeType, EdgeType

try:
    from aiohttp import web
except ImportError:
    raise ImportError("aiohttp is required for HTTP serve mode: pip install aiohttp")


class ContextEngineHTTP:
    def __init__(self, backend: LocalBackend, embedder: Embedder, compressor: Compressor):
        self.backend = backend
        self.embedder = embedder
        self.compressor = compressor

    async def handle_vector_search(self, request: web.Request) -> web.Response:
        data = await request.json()
        embedding = data["embedding"]
        top_k = data.get("top_k", 10)
        results = await self.backend.vector_search(embedding, top_k=top_k)
        return web.json_response({"results": [self._chunk_to_dict(c) for c in results]})

    async def handle_graph_neighbors(self, request: web.Request) -> web.Response:
        data = await request.json()
        node_id = data["node_id"]
        edge_type = EdgeType(data["edge_type"]) if data.get("edge_type") else None
        results = await self.backend.graph_neighbors(node_id, edge_type=edge_type)
        return web.json_response({"results": [self._node_to_dict(n) for n in results]})

    async def handle_ingest(self, request: web.Request) -> web.Response:
        data = await request.json()
        chunks = [self._dict_to_chunk(d) for d in data.get("chunks", [])]
        nodes = [self._dict_to_node(d) for d in data.get("nodes", [])]
        edges = [self._dict_to_edge(d) for d in data.get("edges", [])]
        await self.backend.ingest(chunks, nodes, edges)
        return web.json_response({"ok": True})

    async def handle_get_chunk(self, request: web.Request) -> web.Response:
        chunk_id = request.match_info["chunk_id"]
        chunk = await self.backend.get_chunk_by_id(chunk_id)
        if chunk is None:
            return web.json_response({"error": "not found"}, status=404)
        return web.json_response(self._chunk_to_dict(chunk))

    async def handle_delete_file(self, request: web.Request) -> web.Response:
        file_path = request.match_info["file_path"]
        await self.backend.delete_by_file(file_path)
        return web.json_response({"ok": True})

    async def handle_health(self, request: web.Request) -> web.Response:
        return web.json_response({"status": "ok"})

    def _chunk_to_dict(self, chunk):
        return {"id": chunk.id, "content": chunk.content, "chunk_type": chunk.chunk_type.value,
                "file_path": chunk.file_path, "start_line": chunk.start_line, "end_line": chunk.end_line,
                "language": chunk.language, "embedding": chunk.embedding, "metadata": chunk.metadata}

    def _dict_to_chunk(self, d):
        return Chunk(id=d["id"], content=d["content"], chunk_type=ChunkType(d["chunk_type"]),
                     file_path=d["file_path"], start_line=d["start_line"], end_line=d["end_line"],
                     language=d["language"], embedding=d.get("embedding"), metadata=d.get("metadata", {}))

    def _node_to_dict(self, node):
        return {"id": node.id, "node_type": node.node_type.value, "name": node.name, "file_path": node.file_path}

    def _dict_to_node(self, d):
        return GraphNode(id=d["id"], node_type=NodeType(d["node_type"]), name=d["name"], file_path=d["file_path"])

    def _dict_to_edge(self, d):
        return GraphEdge(source_id=d["source_id"], target_id=d["target_id"], edge_type=EdgeType(d["edge_type"]))


def create_app(backend, embedder, compressor) -> web.Application:
    handler = ContextEngineHTTP(backend, embedder, compressor)
    app = web.Application()
    app.router.add_get("/health", handler.handle_health)
    app.router.add_post("/vector_search", handler.handle_vector_search)
    app.router.add_post("/graph_neighbors", handler.handle_graph_neighbors)
    app.router.add_post("/ingest", handler.handle_ingest)
    app.router.add_get("/chunk/{chunk_id}", handler.handle_get_chunk)
    app.router.add_delete("/file/{file_path:.*}", handler.handle_delete_file)
    return app


def run_http_server(config=None, host="0.0.0.0", port=8765):
    if config is None:
        project_path = Path.cwd() / PROJECT_CONFIG_NAME
        config = load_config(project_path=project_path if project_path.exists() else None)

    project_name = Path.cwd().name
    storage_base = Path(config.storage_path) / project_name
    storage_base.mkdir(parents=True, exist_ok=True)

    backend = LocalBackend(base_path=str(storage_base))
    embedder = Embedder(model_name=config.embedding_model)
    compressor = Compressor(model=config.compression_model)
    app = create_app(backend, embedder, compressor)
    print(f"Context engine HTTP server starting on {host}:{port}")
    web.run_app(app, host=host, port=port)
