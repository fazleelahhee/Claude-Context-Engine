"""Embedding generation using sentence-transformers."""
import logging
import os
from pathlib import Path

from sentence_transformers import SentenceTransformer

from context_engine.models import Chunk

log = logging.getLogger(__name__)


def _model_cache_dir() -> Path:
    """Return the Hugging Face cache dir, honouring HF_HOME and TRANSFORMERS_CACHE."""
    hf_home = os.environ.get("HF_HOME")
    if hf_home:
        return Path(hf_home) / "hub"
    transformers_cache = os.environ.get("TRANSFORMERS_CACHE")
    if transformers_cache:
        return Path(transformers_cache)
    return Path.home() / ".cache" / "huggingface" / "hub"


def _is_model_cached(model_name: str) -> bool:
    """Cheap heuristic: do we have a snapshot for this model locally?"""
    cache_dir = _model_cache_dir()
    if not cache_dir.exists():
        return False
    # sentence-transformers stores repos as `models--{org}--{name}` under `hub/`.
    safe_name = "models--" + model_name.replace("/", "--")
    return any(child.name == safe_name for child in cache_dir.iterdir())


class Embedder:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self._model_name = model_name
        if not _is_model_cached(model_name):
            # Warn before the SentenceTransformer call triggers a network fetch.
            log.warning(
                "Downloading embedding model %s (~90MB first run). "
                "Set HF_HOME to reuse an existing cache. Press Ctrl-C to abort.",
                model_name,
            )
        try:
            self._model = SentenceTransformer(model_name)
        except Exception as exc:
            # Surface a helpful error instead of hanging or crashing deep inside
            # the sentence-transformers stack.
            raise RuntimeError(
                f"Failed to load embedding model '{model_name}'. "
                f"If you're offline, pre-download it once with internet access, "
                f"or set HF_HOME to point at an existing cache. Original error: {exc}"
            ) from exc

    def embed(self, chunks: list[Chunk]) -> None:
        if not chunks:
            return
        texts = [c.content for c in chunks]
        embeddings = self._model.encode(texts, show_progress_bar=False)
        for chunk, emb in zip(chunks, embeddings):
            chunk.embedding = emb.tolist()

    def embed_query(self, query: str) -> list[float]:
        return self._model.encode(query, show_progress_bar=False).tolist()
