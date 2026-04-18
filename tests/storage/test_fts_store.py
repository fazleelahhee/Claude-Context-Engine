import pytest
from context_engine.models import Chunk, ChunkType
from context_engine.storage.fts_store import FTSStore


@pytest.fixture
def fts(tmp_path):
    return FTSStore(db_path=str(tmp_path / "fts"))


@pytest.fixture
def sample_chunks():
    return [
        Chunk(id="c1", content="def calculate_tax(amount, rate): return amount * rate",
              chunk_type=ChunkType.FUNCTION, file_path="finance.py",
              start_line=1, end_line=1, language="python"),
        Chunk(id="c2", content="def process_payment(card, amount): charge the card",
              chunk_type=ChunkType.FUNCTION, file_path="payment.py",
              start_line=1, end_line=1, language="python"),
        Chunk(id="c3", content="class ShippingCalculator: calculates shipping costs",
              chunk_type=ChunkType.CLASS, file_path="shipping.py",
              start_line=1, end_line=5, language="python"),
    ]


@pytest.mark.asyncio
async def test_ingest_and_search(fts, sample_chunks):
    await fts.ingest(sample_chunks)
    results = await fts.search("calculate_tax", top_k=5)
    assert len(results) > 0
    ids = [r[0] for r in results]
    assert "c1" in ids


@pytest.mark.asyncio
async def test_search_returns_scores(fts, sample_chunks):
    await fts.ingest(sample_chunks)
    results = await fts.search("payment", top_k=5)
    assert all(isinstance(score, float) for _, score in results)


@pytest.mark.asyncio
async def test_delete_by_file(fts, sample_chunks):
    await fts.ingest(sample_chunks)
    await fts.delete_by_file("finance.py")
    results = await fts.search("calculate_tax", top_k=5)
    ids = [r[0] for r in results]
    assert "c1" not in ids


@pytest.mark.asyncio
async def test_search_empty_store(fts):
    results = await fts.search("anything", top_k=5)
    assert results == []


@pytest.mark.asyncio
async def test_special_chars_in_query(fts, sample_chunks):
    await fts.ingest(sample_chunks)
    for q in ['"quoted"', "a-b", "fn(x)", "col:val", "wild*card"]:
        results = await fts.search(q, top_k=5)
        assert isinstance(results, list)
