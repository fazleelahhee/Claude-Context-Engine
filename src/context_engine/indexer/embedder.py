"""Embedding generation using ONNX Runtime."""
import logging
import os
from functools import lru_cache
from pathlib import Path

import numpy as np
from optimum.onnxruntime import ORTModelForFeatureExtraction
from transformers import AutoTokenizer

from context_engine.models import Chunk

log = logging.getLogger(__name__)

_DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def _model_cache_dir() -> Path:
    hf_home = os.environ.get("HF_HOME")
    if hf_home:
        return Path(hf_home) / "hub"
    transformers_cache = os.environ.get("TRANSFORMERS_CACHE")
    if transformers_cache:
        return Path(transformers_cache)
    return Path.home() / ".cache" / "huggingface" / "hub"


class Embedder:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self._model_name = model_name
        resolved = f"sentence-transformers/{model_name}" if "/" not in model_name else model_name

        _noisy_loggers = [
            "transformers.modeling_utils", "transformers",
            "huggingface_hub.file_download", "huggingface_hub",
            "optimum", "onnxruntime",
        ]
        _prior_levels = {n: logging.getLogger(n).level for n in _noisy_loggers}
        for name in _noisy_loggers:
            logging.getLogger(name).setLevel(logging.ERROR)
        try:
            self._tokenizer = AutoTokenizer.from_pretrained(resolved)
            self._model = ORTModelForFeatureExtraction.from_pretrained(
                resolved, export=True
            )
        except Exception as exc:
            raise RuntimeError(
                f"Failed to load embedding model '{model_name}'. "
                f"If you're offline, pre-download it once with internet access, "
                f"or set HF_HOME to point at an existing cache. Original error: {exc}"
            ) from exc
        finally:
            for name, level in _prior_levels.items():
                logging.getLogger(name).setLevel(level)

    def _mean_pool(self, last_hidden_state, attention_mask):
        """Attention-masked mean pooling — matches sentence-transformers."""
        mask = attention_mask[..., None].astype(np.float32)
        summed = (last_hidden_state * mask).sum(axis=1)
        counts = mask.sum(axis=1).clip(min=1e-9)
        return summed / counts

    def embed(self, chunks: list[Chunk], batch_size: int = 32) -> None:
        if not chunks:
            return
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            texts = [c.content for c in batch]
            inputs = self._tokenizer(
                texts, padding=True, truncation=True, return_tensors="np"
            )
            outputs = self._model(**inputs)
            embeddings = self._mean_pool(
                outputs.last_hidden_state, inputs["attention_mask"]
            )
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True).clip(min=1e-9)
            embeddings = embeddings / norms
            for chunk, emb in zip(batch, embeddings):
                chunk.embedding = emb.tolist()

    @lru_cache(maxsize=256)
    def embed_query(self, query: str) -> tuple:
        inputs = self._tokenizer(query, return_tensors="np", truncation=True)
        outputs = self._model(**inputs)
        emb = self._mean_pool(outputs.last_hidden_state, inputs["attention_mask"])[0]
        emb = emb / max(float(np.linalg.norm(emb)), 1e-9)
        return tuple(emb.tolist())
