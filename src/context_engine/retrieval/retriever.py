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
            top_k=max(top_k * 2, 1),
        )

        scored: list[tuple[Chunk, float]] = []
        for chunk in vector_results:
            # Prefer LanceDB's real `_distance` if the backend surfaced it in
            # metadata; fall back to 0.0 (treat as perfect) so the scorer doesn't
            # silently collapse when a backend doesn't provide distances.
            distance = chunk.metadata.get("_distance", 0.0)
            # LanceDB default is L2 distance (unbounded upper); clamp to [0, 1]
            # for the scorer which expects a normalised similarity delta.
            normalised_distance = min(max(distance, 0.0), 1.0)
            keyword_distance = self._estimate_keyword_distance(chunk, parsed)
            score = self._scorer.score(
                chunk,
                vector_distance=normalised_distance,
                keyword_distance=keyword_distance,
            )
            chunk.confidence_score = score
            if score >= confidence_threshold:
                scored.append((chunk, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [chunk for chunk, _ in scored[:top_k]]

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
