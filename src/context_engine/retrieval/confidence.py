"""Confidence scoring for retrieved chunks."""
import time
from context_engine.models import Chunk

_VECTOR_WEIGHT = 0.5
_GRAPH_WEIGHT = 0.3
_RECENCY_WEIGHT = 0.2
_MAX_GRAPH_HOPS = 5
_RECENCY_HALF_LIFE = 7 * 24 * 3600  # 1 week


class ConfidenceScorer:
    def score(self, chunk: Chunk, vector_distance: float, graph_hops: int) -> float:
        vector_score = max(0.0, 1.0 - vector_distance)
        graph_score = max(0.0, 1.0 - (graph_hops / _MAX_GRAPH_HOPS))
        recency_score = self._recency_score(chunk)
        combined = (_VECTOR_WEIGHT * vector_score + _GRAPH_WEIGHT * graph_score + _RECENCY_WEIGHT * recency_score)
        return min(1.0, max(0.0, combined))

    def _recency_score(self, chunk: Chunk) -> float:
        modified_ts = chunk.metadata.get("modified_ts")
        if modified_ts is None:
            return 0.5
        age_seconds = time.time() - modified_ts
        if age_seconds <= 0:
            return 1.0
        return 0.5 ** (age_seconds / _RECENCY_HALF_LIFE)
