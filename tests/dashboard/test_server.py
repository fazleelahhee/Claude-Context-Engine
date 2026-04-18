"""Tests for the CCE dashboard FastAPI server."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from context_engine.config import Config
from context_engine.dashboard.server import create_app


def _setup_storage(tmp_path: Path, project_name: str = "my-project") -> tuple[Path, Path]:
    """Create storage dir with stats.json and manifest.json; return (storage_root, project_dir)."""
    project_dir = tmp_path / "workspace" / project_name
    project_dir.mkdir(parents=True)
    storage_base = tmp_path / "storage" / project_name
    storage_base.mkdir(parents=True)
    return storage_base, project_dir


def _make_client(tmp_path: Path, project_name: str = "my-project") -> tuple[TestClient, Path]:
    storage_base, project_dir = _setup_storage(tmp_path, project_name)
    config = Config(storage_path=str(tmp_path / "storage"))
    app = create_app(config, project_dir)
    return TestClient(app), storage_base


def test_get_root_returns_html(tmp_path):
    client, _ = _make_client(tmp_path)
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "<html" in r.text.lower()


def test_status_no_data(tmp_path):
    client, _ = _make_client(tmp_path)
    r = client.get("/api/status")
    assert r.status_code == 200
    data = r.json()
    assert data["initialized"] is False
    assert data["chunks"] == 0
    assert data["files"] == 0
    assert data["queries"] == 0
    assert data["tokens_saved_pct"] == 0
    assert data["output_level"] == "standard"


def test_status_with_stats(tmp_path):
    client, storage_base = _make_client(tmp_path)
    stats = {"queries": 38, "full_file_tokens": 48000, "served_tokens": 14200, "raw_tokens": 14200}
    (storage_base / "stats.json").write_text(json.dumps(stats))
    manifest = {"src/cli.py": "abc123", "src/config.py": "def456"}
    (storage_base / "manifest.json").write_text(json.dumps(manifest))
    r = client.get("/api/status")
    assert r.status_code == 200
    data = r.json()
    assert data["initialized"] is True
    assert data["files"] == 2
    assert data["queries"] == 38
    assert data["tokens_saved_pct"] == 70


def test_status_with_custom_output_level(tmp_path):
    client, storage_base = _make_client(tmp_path)
    (storage_base / "state.json").write_text(json.dumps({"output_level": "max"}))
    r = client.get("/api/status")
    assert r.json()["output_level"] == "max"
