import pytest
from pathlib import Path

from context_engine.indexer.embedding_cache import EmbeddingCache
from context_engine.indexer.embedder import Embedder
from context_engine.models import Chunk, ChunkType


@pytest.fixture
def cache_path(tmp_path):
    return tmp_path / "embedding_cache.db"


@pytest.fixture
def cache(cache_path):
    c = EmbeddingCache(cache_path)
    yield c
    c.close()


def _make_chunk(content: str, chunk_id: str = "c1") -> Chunk:
    return Chunk(
        id=chunk_id, content=content,
        chunk_type=ChunkType.FUNCTION, file_path="test.py",
        start_line=1, end_line=1, language="python",
    )


def test_put_and_get(cache):
    h = EmbeddingCache.content_hash("hello world")
    emb = [0.1, 0.2, 0.3]
    cache.put(h, emb)
    result = cache.get(h)
    assert result == emb


def test_get_miss_returns_none(cache):
    result = cache.get("nonexistent_hash")
    assert result is None


def test_put_batch_and_get_batch(cache):
    items = [
        (EmbeddingCache.content_hash(f"text_{i}"), [float(i)] * 3)
        for i in range(5)
    ]
    cache.put_batch(items)
    hashes = [h for h, _ in items]
    results = cache.get_batch(hashes)
    assert len(results) == 5
    for h, emb in items:
        assert results[h] == emb


def test_get_batch_partial(cache):
    h1 = EmbeddingCache.content_hash("exists")
    cache.put(h1, [1.0, 2.0])
    h2 = EmbeddingCache.content_hash("missing")
    results = cache.get_batch([h1, h2])
    assert h1 in results
    assert h2 not in results


def test_hit_miss_counters(cache):
    h = EmbeddingCache.content_hash("tracked")
    cache.put(h, [1.0])
    cache.get(h)  # hit
    cache.get("missing")  # miss
    assert cache.hits == 1
    assert cache.misses == 1
    assert cache.hit_rate == 0.5


def test_size(cache):
    assert cache.size() == 0
    cache.put(EmbeddingCache.content_hash("a"), [1.0])
    cache.put(EmbeddingCache.content_hash("b"), [2.0])
    assert cache.size() == 2


def test_content_hash_deterministic():
    h1 = EmbeddingCache.content_hash("same content")
    h2 = EmbeddingCache.content_hash("same content")
    assert h1 == h2


def test_content_hash_different_for_different_content():
    h1 = EmbeddingCache.content_hash("content A")
    h2 = EmbeddingCache.content_hash("content B")
    assert h1 != h2


def test_embedder_with_cache_uses_cached_values(cache_path):
    """Embed the same chunks twice; second run should use cache."""
    cache = EmbeddingCache(cache_path)
    embedder = Embedder(model_name="all-MiniLM-L6-v2", cache=cache)

    chunks = [_make_chunk("def add(a, b): return a + b")]
    embedder.embed(chunks)
    first_embedding = chunks[0].embedding[:]
    assert cache.misses == 1
    assert cache.hits == 0
    cache.close()

    # Second run with fresh cache instance (simulating re-index)
    cache2 = EmbeddingCache(cache_path)
    embedder2 = Embedder(model_name="all-MiniLM-L6-v2", cache=cache2)
    chunks2 = [_make_chunk("def add(a, b): return a + b")]
    embedder2.embed(chunks2)
    assert cache2.hits == 1
    assert cache2.misses == 0
    assert chunks2[0].embedding == first_embedding
    cache2.close()


def test_embedder_without_cache_still_works():
    """Embedder with no cache should work as before."""
    embedder = Embedder(model_name="all-MiniLM-L6-v2", cache=None)
    chunks = [_make_chunk("def foo(): pass")]
    embedder.embed(chunks)
    assert chunks[0].embedding is not None
    assert len(chunks[0].embedding) > 0


def test_embedder_mixed_hits_and_misses(cache_path):
    """Cache some chunks, then embed a mix of cached and new."""
    cache = EmbeddingCache(cache_path)
    embedder = Embedder(model_name="all-MiniLM-L6-v2", cache=cache)

    # First: embed one chunk to populate cache
    chunks1 = [_make_chunk("def cached(): pass", "c1")]
    embedder.embed(chunks1)
    cache.close()

    # Second: embed two chunks, one cached and one new
    cache2 = EmbeddingCache(cache_path)
    embedder2 = Embedder(model_name="all-MiniLM-L6-v2", cache=cache2)
    chunks2 = [
        _make_chunk("def cached(): pass", "c1"),
        _make_chunk("def brand_new(): return 42", "c2"),
    ]
    embedder2.embed(chunks2)
    assert cache2.hits == 1
    assert cache2.misses == 1
    assert chunks2[0].embedding is not None
    assert chunks2[1].embedding is not None
    cache2.close()
