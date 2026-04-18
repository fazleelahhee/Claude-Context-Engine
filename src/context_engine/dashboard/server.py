"""FastAPI dashboard server for CCE index inspection."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from context_engine.config import Config
from context_engine.dashboard._page import PAGE_HTML
from context_engine.storage.local_backend import LocalBackend


def create_app(config: Config, project_dir: Path) -> FastAPI:
    """Build and return the FastAPI application.

    All route handlers close over `storage_base` and `project_dir` so the
    app is self-contained and trivial to test with TestClient.
    """
    project_name = project_dir.name
    storage_base = Path(config.storage_path) / project_name

    app = FastAPI(title="CCE Dashboard", docs_url=None, redoc_url=None)

    backend = LocalBackend(base_path=str(storage_base))

    # ── helpers ────────────────────────────────────────────────────────────

    def _read_json(path: Path) -> dict:
        if path.exists():
            try:
                return json.loads(path.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def _read_manifest() -> dict[str, str]:
        return _read_json(storage_base / "manifest.json")

    def _read_stats() -> dict:
        return _read_json(storage_base / "stats.json")

    def _read_state() -> dict:
        return _read_json(storage_base / "state.json")

    def _read_sessions(limit: int = 20) -> list[dict]:
        sessions_dir = storage_base / "sessions"
        if not sessions_dir.exists():
            return []
        files = sorted(sessions_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        result = []
        for f in files[:limit]:
            try:
                result.append(json.loads(f.read_text()))
            except (json.JSONDecodeError, OSError):
                pass
        return result

    # ── routes ─────────────────────────────────────────────────────────────

    @app.get("/", response_class=HTMLResponse)
    async def serve_page() -> str:
        return PAGE_HTML

    @app.get("/api/status")
    async def get_status() -> dict:
        stats = _read_stats()
        manifest = _read_manifest()
        state = _read_state()

        try:
            chunks = backend.count_chunks()
        except Exception:
            chunks = 0

        full_file = stats.get("full_file_tokens", 0)
        served = stats.get("served_tokens", 0)
        baseline = full_file if full_file > 0 else stats.get("raw_tokens", 0)
        saved_pct = max(0, int((1 - served / baseline) * 100)) if baseline > 0 else 0

        output_level = state.get("output_level", config.output_compression)

        return {
            "project": project_name,
            "initialized": bool(manifest),
            "chunks": chunks,
            "files": len(manifest),
            "queries": stats.get("queries", 0),
            "tokens_saved_pct": saved_pct,
            "output_level": output_level,
        }

    return app
