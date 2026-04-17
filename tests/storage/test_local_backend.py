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
