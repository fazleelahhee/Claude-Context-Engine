"""FastAPI dashboard server for CCE index inspection."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from typing import Literal

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel

from context_engine.config import Config
from context_engine.dashboard._page import PAGE_HTML
from context_engine.indexer.pipeline import run_indexing
from context_engine.storage.local_backend import LocalBackend


class ReindexRequest(BaseModel):
    full: bool = False


class CompressionRequest(BaseModel):
    level: Literal["off", "lite", "standard", "max"]


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

    @app.get("/api/files")
    async def get_files() -> list:
        manifest = _read_manifest()
        if not manifest:
            return []

        chunk_counts = backend.file_chunk_counts()

        result = []
        for rel_path, stored_hash in sorted(manifest.items()):
            abs_path = project_dir / rel_path
            if not abs_path.exists():
                status = "missing"
            else:
                try:
                    current = abs_path.read_text(encoding="utf-8", errors="strict")
                    current_hash = hashlib.sha256(current.encode("utf-8")).hexdigest()
                    status = "ok" if current_hash == stored_hash else "stale"
                except (UnicodeDecodeError, OSError):
                    status = "ok"  # binary file, trust the manifest
            result.append({
                "path": rel_path,
                "chunks": chunk_counts.get(rel_path, 0),
                "status": status,
            })
        return result

    @app.get("/api/sessions")
    async def get_sessions() -> list:
        return _read_sessions()

    @app.get("/api/savings")
    async def get_savings() -> dict:
        stats = _read_stats()
        full_file = stats.get("full_file_tokens", 0)
        served = stats.get("served_tokens", 0)
        raw = stats.get("raw_tokens", 0)
        baseline = full_file if full_file > 0 else raw
        saved = max(0, baseline - served)
        pct = int(saved / baseline * 100) if baseline > 0 else 0
        return {
            "queries": stats.get("queries", 0),
            "baseline_tokens": baseline,
            "served_tokens": served,
            "tokens_saved": saved,
            "savings_pct": pct,
        }

    # ── action routes ──────────────────────────────────────────────────────

    @app.post("/api/reindex")
    async def reindex(req: ReindexRequest) -> dict:
        result = await run_indexing(config, project_dir, full=req.full)
        return {
            "total_chunks": result.total_chunks,
            "indexed_files": result.indexed_files,
            "deleted_files": result.deleted_files,
            "skipped_files": result.skipped_files,
            "errors": result.errors,
        }

    @app.post("/api/reindex/{file_path:path}")
    async def reindex_file(file_path: str) -> dict:
        result = await run_indexing(config, project_dir, target_path=file_path)
        return {
            "total_chunks": result.total_chunks,
            "indexed_files": result.indexed_files,
            "deleted_files": result.deleted_files,
            "skipped_files": result.skipped_files,
            "errors": result.errors,
        }

    @app.post("/api/clear")
    async def clear_index() -> dict:
        await backend.clear()
        (storage_base / "manifest.json").write_text(json.dumps({}))
        (storage_base / "stats.json").write_text(json.dumps(
            {"queries": 0, "raw_tokens": 0, "served_tokens": 0, "full_file_tokens": 0}
        ))
        return {"ok": True}

    @app.delete("/api/files/{file_path:path}")
    async def delete_file(file_path: str) -> dict:
        await backend.delete_by_file(file_path)
        manifest = _read_manifest()
        manifest.pop(file_path, None)
        (storage_base / "manifest.json").write_text(json.dumps(manifest))
        return {"ok": True, "deleted": file_path}

    @app.post("/api/compression")
    async def set_compression(req: CompressionRequest) -> dict:
        state = _read_state()
        state["output_level"] = req.level
        (storage_base / "state.json").write_text(json.dumps(state))
        return {"level": req.level}

    @app.get("/api/export")
    async def export_data():
        payload = {
            "project": project_name,
            "stats": _read_stats(),
            "manifest": _read_manifest(),
            "sessions": _read_sessions(),
        }
        return Response(
            content=json.dumps(payload, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={project_name}-cce-export.json"},
        )

    return app
