"""Embedding generation using fastembed (lightweight ONNX-based embeddings).

Uses BAAI/bge-small-en-v1.5 by default — 33% smaller and better quality
than all-MiniLM-L6-v2. Parallel embedding for 3-4x faster indexing.

Supports an optional EmbeddingCache so unchanged code chunks are never
re-embedded across index runs (inspired by Cursor's content-hash cache).
"""
import logging
import os
from functools import lru_cache

import numpy as np
from fastembed import TextEmbedding

from context_engine.models import Chunk
from context_engine.indexer.embedding_cache import EmbeddingCache

log = logging.getLogger(__name__)

_DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"

# Number of parallel threads for embedding. Auto-detect based on CPU cores,
# capped at 4 to avoid memory pressure.
_PARALLEL = min(os.cpu_count() or 2, 4)


class Embedder:
    def __init__(
        self,
        model_name: str = "BAAI/bge-small-en-v1.5",
        cache: EmbeddingCache | None = None,
    ) -> None:
        self._model_name = model_name
        self._cache = cache
        # Resolve short names: "all-MiniLM-L6-v2" → "sentence-transformers/all-MiniLM-L6-v2"
        # but leave fully qualified names like "BAAI/bge-small-en-v1.5" alone.
        if "/" not in model_name:
            resolved = f"sentence-transformers/{model_name}"
        else:
            resolved = model_name
        try:
            self._model = TextEmbedding(resolved)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to load embedding model '{model_name}'. "
                f"Ensure fastembed is installed and the model name is valid. "
                f"Supported models: TextEmbedding.list_supported_models(). "
                f"Original error: {exc}"
            ) from exc

    def embed(self, chunks: list[Chunk], batch_size: int = 64) -> None:
        """Embed chunks in-place, using cache for hits and model for misses."""
        if not chunks:
            return

        if self._cache is None:
            self._embed_all(chunks, batch_size)
            return

        # Compute content hashes and check cache in batch
        hashes = [EmbeddingCache.content_hash(c.content) for c in chunks]
        cached = self._cache.get_batch(hashes)

        # Separate hits and misses
        miss_indices: list[int] = []
        for i, h in enumerate(hashes):
            if h in cached:
                chunks[i].embedding = cached[h]
            else:
                miss_indices.append(i)

        if miss_indices:
            miss_chunks = [chunks[i] for i in miss_indices]
            miss_hashes = [hashes[i] for i in miss_indices]
            self._embed_all(miss_chunks, batch_size)

            # Store newly computed embeddings back to cache
            new_entries = [
                (miss_hashes[j], miss_chunks[j].embedding)
                for j in range(len(miss_chunks))
                if miss_chunks[j].embedding is not None
            ]
            if new_entries:
                self._cache.put_batch(new_entries)

        cache_total = len(chunks)
        cache_hits = cache_total - len(miss_indices)
        if cache_hits > 0:
            log.info(
                "Embedding cache: %d/%d hits (%.0f%% reused)",
                cache_hits, cache_total, cache_hits / cache_total * 100,
            )

    def _embed_all(self, chunks: list[Chunk], batch_size: int = 64) -> None:
        """Embed all chunks using the model (no cache)."""
        texts = [c.content for c in chunks]
        embeddings = list(self._model.embed(
            texts,
            batch_size=batch_size,
            parallel=_PARALLEL,
        ))
        for chunk, emb in zip(chunks, embeddings):
            chunk.embedding = emb.tolist()

    @lru_cache(maxsize=256)
    def embed_query(self, query: str) -> tuple:
        """Embed a single query string. Returns tuple for LRU cache hashability.

        Callers that need a list (e.g. LanceDB) should use list(result)
        or the _to_list() helper in vector_store.
        """
        results = list(self._model.query_embed(query))
        return tuple(results[0].tolist())
