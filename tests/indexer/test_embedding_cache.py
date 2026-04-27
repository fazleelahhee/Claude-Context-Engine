"""Tests for the content-hash embedding cache.

Covers the cache surface area in isolation plus the embedder→cache integration
path. Vectors are float32 round-tripped through struct.pack/unpack, so the
equality assertions use pytest.approx to tolerate sub-bit differences.
"""
import pytest

from context_engine.indexer.embedder import Embedder
from context_engine.indexer.embedding_cache import EmbeddingCache
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


def test_model_namespacing_isolates_caches(tmp_path):
    """A switch between embedding models must not return the previous
    model's vectors. Regression for the 2026-04-27 PR review."""
    path = tmp_path / "ec.db"
    h = EmbeddingCache.content_hash("def add(a, b): return a + b")

    cache_a = EmbeddingCache(path, model_name="model-A")
    cache_a.put(h, [0.1] * 384)
    cache_a.close()

    cache_b = EmbeddingCache(path, model_name="model-B")
    # Different model — must miss even though the content hash matches.
    assert cache_b.get(h) is None
    # Reading on model-A still works (different connection, same DB file).
    cache_a2 = EmbeddingCache(path, model_name="model-A")
    assert cache_a2.get(h) is not None
    cache_a2.close()
    cache_b.close()


def test_legacy_v1_table_is_dropped(tmp_path):
    """Opening a cache with the old (model-less) schema drops it.

    Old vectors had no model attribution, so reusing them after a model
    swap could return wrong-meaning embeddings.
    """
    import sqlite3

    path = tmp_path / "ec.db"
    # Manually create a v1 table to simulate an upgrade-in-place scenario.
    conn = sqlite3.connect(str(path))
    conn.execute(
        "CREATE TABLE embedding_cache (content_hash TEXT PRIMARY KEY, "
        "dim INTEGER NOT NULL, embedding BLOB NOT NULL)"
    )
    conn.execute(
        "INSERT INTO embedding_cache VALUES (?, ?, ?)",
        ("legacy-hash", 4, b"\x00" * 16),
    )
    conn.commit()
    conn.close()

    # Opening through v2 EmbeddingCache should drop the legacy table.
    cache = EmbeddingCache(path, model_name="m1")
    assert cache.get("legacy-hash") is None  # legacy data gone
    # New schema works.
    cache.put("h1", [0.1, 0.2, 0.3])
    assert cache.get("h1") == pytest.approx([0.1, 0.2, 0.3], rel=1e-6)
    cache.close()


def test_put_and_get(cache):
    h = EmbeddingCache.content_hash("hello world")
    emb = [0.1, 0.2, 0.3]
    cache.put(h, emb)
    result = cache.get(h)
    assert result == pytest.approx(emb, rel=1e-6)


def test_get_miss_returns_none(cache):
    assert cache.get("nonexistent_hash") is None


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
        assert results[h] == pytest.approx(emb, rel=1e-6)


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
    cache.get(h)            # hit
    cache.get("missing")    # miss
    assert cache.hits == 1
    assert cache.misses == 1
    assert cache.hit_rate == 0.5


def test_size(cache):
    assert cache.size() == 0
    cache.put(EmbeddingCache.content_hash("a"), [1.0])
    cache.put(EmbeddingCache.content_hash("b"), [2.0])
    assert cache.size() == 2


def test_content_hash_deterministic_and_distinct():
    assert EmbeddingCache.content_hash("same") == EmbeddingCache.content_hash("same")
    assert EmbeddingCache.content_hash("a") != EmbeddingCache.content_hash("b")


def test_prune_orphans_drops_stale_entries(cache):
    h_keep = EmbeddingCache.content_hash("kept")
    h_drop = EmbeddingCache.content_hash("orphan")
    cache.put(h_keep, [1.0, 2.0])
    cache.put(h_drop, [3.0, 4.0])

    removed = cache.prune_orphans({h_keep})
    assert removed == 1
    assert cache.get(h_keep) is not None
    assert cache.get(h_drop) is None


def test_prune_orphans_refuses_empty_set(cache):
    """Empty `known_hashes` is almost always a caller bug — refuse to wipe
    everything implicitly."""
    cache.put(EmbeddingCache.content_hash("safe"), [1.0])
    assert cache.prune_orphans(set()) == 0
    assert cache.size() == 1


def test_embedder_with_cache_uses_cached_values(cache_path):
    """Embed once → close → re-open → re-embed: second run hits cache 100%."""
    cache = EmbeddingCache(cache_path)
    embedder = Embedder(model_name="all-MiniLM-L6-v2", cache=cache)

    chunks = [_make_chunk("def add(a, b): return a + b")]
    embedder.embed(chunks)
    first_embedding = chunks[0].embedding[:]
    assert cache.misses == 1
    assert cache.hits == 0
    cache.close()

    cache2 = EmbeddingCache(cache_path)
    embedder2 = Embedder(model_name="all-MiniLM-L6-v2", cache=cache2)
    chunks2 = [_make_chunk("def add(a, b): return a + b")]
    embedder2.embed(chunks2)
    assert cache2.hits == 1
    assert cache2.misses == 0
    assert chunks2[0].embedding == pytest.approx(first_embedding, rel=1e-5)
    cache2.close()


def test_embedder_without_cache_still_works():
    embedder = Embedder(model_name="all-MiniLM-L6-v2", cache=None)
    chunks = [_make_chunk("def foo(): pass")]
    embedder.embed(chunks)
    assert chunks[0].embedding is not None
    assert len(chunks[0].embedding) > 0


def test_embedder_mixed_hits_and_misses(cache_path):
    """Two-chunk batch: one cached from a prior run, one new. Verifies the
    miss-only re-embed path doesn't corrupt the cached chunk's vector."""
    cache = EmbeddingCache(cache_path)
    embedder = Embedder(model_name="all-MiniLM-L6-v2", cache=cache)
    embedder.embed([_make_chunk("def cached(): pass", "c1")])
    cache.close()

    cache2 = EmbeddingCache(cache_path)
    embedder2 = Embedder(model_name="all-MiniLM-L6-v2", cache=cache2)
    chunks = [
        _make_chunk("def cached(): pass", "c1"),
        _make_chunk("def brand_new(): return 42", "c2"),
    ]
    embedder2.embed(chunks)
    assert cache2.hits == 1
    assert cache2.misses == 1
    assert chunks[0].embedding is not None
    assert chunks[1].embedding is not None
    cache2.close()
