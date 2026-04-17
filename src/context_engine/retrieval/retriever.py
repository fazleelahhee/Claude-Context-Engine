"""Hybrid retrieval — vector search + keyword/file-hint bonus + confidence scoring.

The scorer weights three signals (vector similarity, keyword-match bonus,
recency). Historically the middle term was called "graph hops" — the name is
kept as a method alias for a release but the real feature is a query-parser
bonus based on file-hint and keyword hits (see `confidence.py`).
"""
from context_engine.models import Chunk
from context_engine.storage.backend import StorageBackend
from context_engine.indexer.embedder import Embedder
from context_engine.retrieval.confidence import ConfidenceScorer
from context_engine.retrieval.query_parser import QueryParser

# Paths that contain these segments get a score penalty — they are useful
# as supporting evidence but should not dominate results over source code.
_DEPRIORITISED_PATHS = {"tests/", "test_", "docs/", "spec", "plan"}


class HybridRetriever:
    def __init__(self, backend: StorageBackend, embedder: Embedder) -> None:
        self._backend = backend
        self._embedder = embedder
        self._scorer = ConfidenceScorer()
        self._parser = QueryParser()

    async def retrieve(
        self,
        query: str,
        top_k: int = 10,
        confidence_threshold: float = 0.0,
    ) -> list[Chunk]:
        parsed = self._parser.parse(query)
        query_embedding = self._embedder.embed_query(query)

        vector_results = await self._backend.vector_search(
            query_embedding=query_embedding,
            top_k=max(top_k * 3, 1),
        )

        scored: list[tuple[Chunk, float]] = []
        seen_keys: set[str] = set()

        for chunk in vector_results:
            # ── deduplicate by file + line range ──
            dedup_key = f"{chunk.file_path}:{chunk.start_line}-{chunk.end_line}"
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            distance = chunk.metadata.get("_distance", 0.0)
            # LanceDB returns L2 distance (range ~0-4 for normalised embeddings).
            # Scale to [0, 1] where 0=identical, 1=unrelated. L2 of 2.0 means
            # orthogonal vectors; anything beyond is anti-correlated.
            normalised_distance = min(max(distance / 2.0, 0.0), 1.0)
            keyword_distance = self._estimate_keyword_distance(chunk, parsed)
            score = self._scorer.score(
                chunk,
                vector_distance=normalised_distance,
                keyword_distance=keyword_distance,
            )

            # Deprioritise test/doc files so source code ranks higher
            score = self._apply_path_penalty(chunk.file_path, score)

            chunk.confidence_score = score
            if score >= confidence_threshold:
                scored.append((chunk, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [chunk for chunk, _ in scored[:top_k]]

    @staticmethod
    def _apply_path_penalty(file_path: str, score: float) -> float:
        """Reduce score for test/doc files so source code ranks higher."""
        fp_lower = file_path.lower()
        for marker in _DEPRIORITISED_PATHS:
            if marker in fp_lower:
                return score * 0.8
        return score

    def _estimate_keyword_distance(self, chunk, parsed) -> int:
        """Return 0 (perfect match) when the parsed query references this chunk
        by file hint or a keyword that appears in its content, else 2 (neutral).

        The query parser extracts `file_hints` and `keywords`; this bonus is
        what used to be labelled "graph hops" before the graph store was cut.
        """
        if parsed.file_hints:
            for hint in parsed.file_hints:
                if hint in chunk.file_path:
                    return 0
        for keyword in parsed.keywords:
            if keyword.lower() in chunk.content.lower():
                return 0
        return 2
