"""Hybrid retrieval — vector search + FTS BM25 + RRF merging + confidence scoring."""
import logging

from context_engine.models import Chunk
from context_engine.storage.backend import StorageBackend
from context_engine.indexer.embedder import Embedder
from context_engine.retrieval.confidence import ConfidenceScorer
from context_engine.retrieval.query_parser import QueryParser

log = logging.getLogger(__name__)

_DEPRIORITISED_PATHS = {"tests/", "test_", "docs/", "spec", "plan"}
_RRF_K = 60


class HybridRetriever:
    def __init__(self, backend: StorageBackend, embedder: Embedder) -> None:
        self._backend = backend
        self._embedder = embedder
        self._scorer = ConfidenceScorer()
        self._parser = QueryParser()
        self._fts_warned = False

    async def retrieve(
        self,
        query: str,
        top_k: int = 10,
        confidence_threshold: float = 0.0,
        max_tokens: int | None = None,
    ) -> list[Chunk]:
        parsed = self._parser.parse(query)
        query_embedding = self._embedder.embed_query(query)

        # NOTE: embed_query may return a tuple (if LRU cached). Convert to list.
        if isinstance(query_embedding, tuple):
            query_embedding = list(query_embedding)

        vector_results = await self._backend.vector_search(
            query_embedding=query_embedding,
            top_k=max(top_k * 3, 1),
        )

        # FTS search with graceful fallback
        fts_ids: dict[str, int] = {}
        try:
            fts_results = await self._backend.fts_search(query, top_k=top_k * 3)
            fts_ids = {id_: rank for rank, (id_, _) in enumerate(fts_results)}
        except Exception:
            if not self._fts_warned:
                log.warning("FTS search unavailable; falling back to vector-only")
                self._fts_warned = True

        # Build vector rankings and chunk map
        vector_ranks: dict[str, int] = {}
        chunk_map: dict[str, Chunk] = {}
        seen_keys: set[str] = set()

        for rank, chunk in enumerate(vector_results):
            dedup_key = f"{chunk.file_path}:{chunk.start_line}-{chunk.end_line}"
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)
            vector_ranks[chunk.id] = rank
            chunk_map[chunk.id] = chunk

        # Hydrate FTS-only results
        fts_only_ids = [id_ for id_ in fts_ids if id_ not in chunk_map]
        if fts_only_ids:
            try:
                hydrated = await self._backend.get_chunks_by_ids(fts_only_ids)
                for chunk in hydrated:
                    chunk_map[chunk.id] = chunk
            except Exception:
                pass

        # Compute RRF scores
        all_ids = set(vector_ranks.keys()) | set(fts_ids.keys())
        rrf_scores: dict[str, float] = {}
        for id_ in all_ids:
            score = 0.0
            if id_ in vector_ranks:
                score += 1.0 / (_RRF_K + vector_ranks[id_])
            if id_ in fts_ids:
                score += 1.0 / (_RRF_K + fts_ids[id_])
            rrf_scores[id_] = score

        # Score with confidence scorer
        scored: list[tuple[Chunk, float]] = []
        for id_, rrf_score in rrf_scores.items():
            chunk = chunk_map.get(id_)
            if chunk is None:
                continue

            distance = chunk.metadata.get("_distance", 0.0)
            normalised_distance = min(max(distance / 2.0, 0.0), 1.0)
            keyword_distance = self._estimate_keyword_distance(chunk, parsed)
            conf_score = self._scorer.score(
                chunk,
                vector_distance=normalised_distance,
                keyword_distance=keyword_distance,
            )

            final_score = 0.5 * conf_score + 0.5 * min(rrf_score * _RRF_K, 1.0)
            final_score = self._apply_path_penalty(chunk.file_path, final_score)
            chunk.confidence_score = final_score

            if final_score >= confidence_threshold:
                scored.append((chunk, final_score))

        scored.sort(key=lambda x: x[1], reverse=True)
        ranked = [chunk for chunk, _ in scored[:top_k]]

        if max_tokens is None:
            return ranked

        packed: list[Chunk] = []
        budget = max_tokens
        for chunk in ranked:
            tokens = chunk.token_count
            if tokens <= budget:
                packed.append(chunk)
                budget -= tokens
            elif chunk.compressed_content:
                compressed_tokens = max(1, int(len(chunk.compressed_content) / 3.3))
                if compressed_tokens <= budget:
                    packed.append(chunk)
                    budget -= compressed_tokens
        return packed

    @staticmethod
    def _apply_path_penalty(file_path: str, score: float) -> float:
        if file_path.startswith("git:"):
            return score
        fp_lower = file_path.lower()
        for marker in _DEPRIORITISED_PATHS:
            if marker in fp_lower:
                return score * 0.8
        return score

    def _estimate_keyword_distance(self, chunk, parsed) -> int:
        if parsed.file_hints:
            for hint in parsed.file_hints:
                if hint in chunk.file_path:
                    return 0
        for keyword in parsed.keywords:
            if keyword.lower() in chunk.content.lower():
                return 0
        return 2
