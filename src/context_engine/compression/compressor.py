"""Compression pipeline — groups chunks, summarizes via LLM, falls back to truncation."""
import logging
from context_engine.models import Chunk, ChunkType
from context_engine.compression.ollama_client import OllamaClient
from context_engine.compression.prompts import CODE_PROMPT, DECISION_PROMPT, ARCHITECTURE_PROMPT, DOC_PROMPT
from context_engine.compression.quality import QualityChecker

log = logging.getLogger(__name__)

_PROMPT_MAP = {
    ChunkType.FUNCTION: CODE_PROMPT, ChunkType.CLASS: CODE_PROMPT,
    ChunkType.MODULE: ARCHITECTURE_PROMPT, ChunkType.DOC: DOC_PROMPT,
    ChunkType.DECISION: DECISION_PROMPT, ChunkType.SESSION: DOC_PROMPT,
    ChunkType.COMMIT: DOC_PROMPT, ChunkType.COMMENT: DOC_PROMPT,
}
_TRUNCATION_LIMITS: dict[str, int] = {"minimal": 100, "standard": 300, "full": 800}
# In "full" mode we pass a chunk through uncompressed only if we're confident it
# came from the retrieval pipeline (which sets confidence_score) — chunks
# ingested by other paths default to 0.0 and would otherwise be falsely
# classified as low-confidence. A chunk with no embedding wasn't retrieved.
_FULL_PASSTHROUGH_THRESHOLD = 0.8


class Compressor:
    def __init__(self, ollama_url: str = "http://localhost:11434", model: str = "phi3:mini") -> None:
        self._client = OllamaClient(base_url=ollama_url, model=model)
        self._quality = QualityChecker()

    async def compress(self, chunks: list[Chunk], level: str = "standard") -> list[Chunk]:
        ollama_available = await self._client.is_available()
        for chunk in chunks:
            if level == "full" and self._is_full_passthrough(chunk):
                chunk.compressed_content = chunk.content
            elif ollama_available and level != "minimal":
                chunk.compressed_content = await self._llm_compress(chunk, level)
            else:
                chunk.compressed_content = self._fallback_compress(chunk, level)
        return chunks

    def _is_full_passthrough(self, chunk: Chunk) -> bool:
        """Accept either a high retrieval-confidence chunk *or* a chunk that
        was never routed through retrieval (no embedding) — otherwise a direct
        lookup via `expand_chunk` would get silently truncated in full mode.
        """
        if chunk.confidence_score > _FULL_PASSTHROUGH_THRESHOLD:
            return True
        return chunk.embedding is None

    async def _llm_compress(self, chunk: Chunk, level: str) -> str:
        prompt = _PROMPT_MAP.get(chunk.chunk_type, CODE_PROMPT)
        try:
            summary = await self._client.summarize(chunk.content, prompt)
        except Exception as exc:
            log.info(
                "Ollama summarize failed for chunk %s; falling back to truncation (%s)",
                chunk.id,
                exc,
            )
            return self._fallback_compress(chunk, level)
        if self._quality.check(chunk.content, summary):
            return summary
        log.info(
            "Quality check failed for chunk %s (identifier retention < 40%%); "
            "falling back to truncation.",
            chunk.id,
        )
        return self._fallback_compress(chunk, level)

    def _fallback_compress(self, chunk: Chunk, level: str) -> str:
        limit = _TRUNCATION_LIMITS.get(level, 300)
        if chunk.chunk_type in (ChunkType.FUNCTION, ChunkType.CLASS):
            return self._extract_signature(chunk.content, limit)
        if len(chunk.content) <= limit:
            return chunk.content
        return chunk.content[:limit] + "..."

    def _extract_signature(self, content: str, limit: int) -> str:
        lines = content.split("\n")
        result_lines: list[str] = []
        in_docstring = False
        char_count = 0
        for line in lines:
            if char_count + len(line) > limit and result_lines:
                break
            result_lines.append(line)
            char_count += len(line) + 1
            if '"""' in line or "'''" in line:
                if in_docstring:
                    break
                in_docstring = True
            if not in_docstring and line.strip().endswith(":") and len(result_lines) > 1:
                break
        return "\n".join(result_lines)
