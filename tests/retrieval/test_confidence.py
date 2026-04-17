import pytest
import time
from context_engine.models import Chunk, ChunkType, ConfidenceLevel
from context_engine.retrieval.confidence import ConfidenceScorer


@pytest.fixture
def scorer():
    return ConfidenceScorer()


def _make_chunk(chunk_id: str, distance: float = 0.1) -> tuple[Chunk, float]:
    chunk = Chunk(id=chunk_id, content="test", chunk_type=ChunkType.FUNCTION,
                  file_path="test.py", start_line=1, end_line=1, language="python")
    return chunk, distance


def test_high_confidence_for_close_match(scorer):
    chunk, dist = _make_chunk("c1", distance=0.05)
    score = scorer.score(chunk, vector_distance=dist, keyword_distance=0)
    assert score > 0.8
    assert ConfidenceLevel.from_score(score) == ConfidenceLevel.HIGH


def test_low_confidence_for_distant_match(scorer):
    chunk, dist = _make_chunk("c1", distance=0.95)
    score = scorer.score(chunk, vector_distance=dist, keyword_distance=5)
    assert score < 0.5
    assert ConfidenceLevel.from_score(score) == ConfidenceLevel.LOW


def test_keyword_distance_reduces_confidence(scorer):
    chunk, dist = _make_chunk("c1", distance=0.1)
    score_close = scorer.score(chunk, vector_distance=dist, keyword_distance=0)
    score_far = scorer.score(chunk, vector_distance=dist, keyword_distance=4)
    assert score_close > score_far


def test_recency_boosts_score(scorer):
    old_chunk = Chunk(id="old", content="test", chunk_type=ChunkType.FUNCTION,
                      file_path="test.py", start_line=1, end_line=1, language="python",
                      metadata={"modified_ts": 1000000})
    new_chunk = Chunk(id="new", content="test", chunk_type=ChunkType.FUNCTION,
                      file_path="test.py", start_line=1, end_line=1, language="python",
                      metadata={"modified_ts": time.time()})
    score_old = scorer.score(old_chunk, vector_distance=0.2, keyword_distance=1)
    score_new = scorer.score(new_chunk, vector_distance=0.2, keyword_distance=1)
    assert score_new > score_old
