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


def test_count_empty(tmp_path):
    vs = VectorStore(db_path=str(tmp_path / "db"))
    assert vs.count() == 0


def test_file_chunk_counts_empty(tmp_path):
    vs = VectorStore(db_path=str(tmp_path / "db"))
    assert vs.file_chunk_counts() == {}


def test_clear_resets_table(tmp_path):
    from context_engine.models import Chunk, ChunkType
    vs = VectorStore(db_path=str(tmp_path / "db"))
    chunk = Chunk(
        id="c1", content="def foo(): pass", chunk_type=ChunkType.FUNCTION,
        file_path="foo.py", start_line=1, end_line=1, language="python",
        embedding=[0.1] * 384,
    )
    import asyncio
    asyncio.run(vs.ingest([chunk]))
    assert vs.count() == 1
    vs.clear()
    assert vs.count() == 0


def test_file_chunk_counts_after_ingest(tmp_path):
    from context_engine.models import Chunk, ChunkType
    import asyncio
    vs = VectorStore(db_path=str(tmp_path / "db"))
    chunks = [
        Chunk(id="c1", content="a", chunk_type=ChunkType.FUNCTION,
              file_path="a.py", start_line=1, end_line=1, language="python",
              embedding=[0.1] * 384),
        Chunk(id="c2", content="b", chunk_type=ChunkType.FUNCTION,
              file_path="a.py", start_line=2, end_line=2, language="python",
              embedding=[0.2] * 384),
        Chunk(id="c3", content="c", chunk_type=ChunkType.FUNCTION,
              file_path="b.py", start_line=1, end_line=1, language="python",
              embedding=[0.3] * 384),
    ]
    asyncio.run(vs.ingest(chunks))
    counts = vs.file_chunk_counts()
    assert counts["a.py"] == 2
    assert counts["b.py"] == 1
