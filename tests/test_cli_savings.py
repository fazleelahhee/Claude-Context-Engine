"""Tests for the `cce savings` CLI command."""
import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from context_engine.cli import main
from context_engine.config import Config


@pytest.fixture()
def runner():
    return CliRunner()


@pytest.fixture()
def stats_dir(tmp_path):
    """Create a temporary storage directory with a stats.json file."""
    project_name = "test-project"
    project_dir = tmp_path / project_name
    project_dir.mkdir(parents=True)
    stats = {"queries": 10, "full_file_tokens": 5000, "raw_tokens": 3000, "served_tokens": 2000}
    (project_dir / "stats.json").write_text(json.dumps(stats))
    return tmp_path, project_name


def _invoke_savings(runner, storage_path, project_name, *args):
    """Helper: invoke `cce savings` with a patched storage path."""
    from unittest.mock import patch

    config = Config(storage_path=str(storage_path))
    with runner.isolated_filesystem():
        cwd_path = Path.cwd() / project_name
        cwd_path.mkdir(parents=True, exist_ok=True)
        with patch("context_engine.cli.load_config", return_value=config), \
             patch("context_engine.cli.Path.cwd", return_value=cwd_path):
            result = runner.invoke(main, ["savings", *args])
    return result


def test_savings_no_data(runner, tmp_path):
    """savings command reports no usage when stats.json is absent."""
    config = Config(storage_path=str(tmp_path))
    with runner.isolated_filesystem():
        project_dir = Path.cwd() / "my-project"
        project_dir.mkdir()
        from unittest.mock import patch
        with patch("context_engine.cli.load_config", return_value=config), \
             patch("context_engine.cli.Path.cwd", return_value=project_dir):
            result = runner.invoke(main, ["savings"])
    assert result.exit_code == 0
    assert "No usage recorded" in result.output


def test_savings_with_data(runner, stats_dir):
    """savings command shows correct token counts and savings percentage."""
    storage_path, project_name = stats_dir
    result = _invoke_savings(runner, storage_path, project_name)
    assert result.exit_code == 0
    assert "test-project" in result.output
    assert "5.0k" in result.output       # baseline tokens (fmt_k)
    assert "2,000" in result.output      # served_tokens
    assert "3,000" in result.output      # tokens_saved
    assert "60%" in result.output        # savings_pct


def test_savings_json_output(runner, stats_dir):
    """--json flag returns valid JSON with correct fields."""
    storage_path, project_name = stats_dir
    result = _invoke_savings(runner, storage_path, project_name, "--json")
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["queries"] == 10
    assert data["full_file_tokens"] == 5000
    assert data["served_tokens"] == 2000
    assert data["tokens_saved"] == 3000
    assert data["savings_pct"] == 60


def test_savings_json_no_data(runner, tmp_path):
    """--json flag returns zeroed JSON when no usage data exists."""
    config = Config(storage_path=str(tmp_path))
    from unittest.mock import patch
    with runner.isolated_filesystem():
        project_dir = Path.cwd() / "no-data-project"
        project_dir.mkdir()
        with patch("context_engine.cli.load_config", return_value=config), \
             patch("context_engine.cli.Path.cwd", return_value=project_dir):
            result = runner.invoke(main, ["savings", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["full_file_tokens"] == 0
    assert data["tokens_saved"] == 0


def test_savings_all_projects(runner, tmp_path):
    """--all shows a report for each project with recorded stats."""
    for name, full, served in [("proj-a", 8000, 3000), ("proj-b", 2000, 1500)]:
        d = tmp_path / name
        d.mkdir()
        (d / "stats.json").write_text(json.dumps({
            "queries": 5, "full_file_tokens": full, "raw_tokens": full, "served_tokens": served,
        }))

    config = Config(storage_path=str(tmp_path))
    from unittest.mock import patch
    with runner.isolated_filesystem():
        cwd = Path.cwd() / "proj-a"
        cwd.mkdir()
        with patch("context_engine.cli.load_config", return_value=config), \
             patch("context_engine.cli.Path.cwd", return_value=cwd):
            result = runner.invoke(main, ["savings", "--all"])
    assert result.exit_code == 0
    assert "proj-a" in result.output
    assert "proj-b" in result.output


def test_savings_all_projects_json(runner, tmp_path):
    """--all --json returns a list of project entries."""
    for name, full, served in [("p1", 4000, 1000), ("p2", 6000, 3000)]:
        d = tmp_path / name
        d.mkdir()
        (d / "stats.json").write_text(json.dumps({
            "queries": 3, "full_file_tokens": full, "raw_tokens": full, "served_tokens": served,
        }))

    config = Config(storage_path=str(tmp_path))
    from unittest.mock import patch
    with runner.isolated_filesystem():
        cwd = Path.cwd() / "p1"
        cwd.mkdir()
        with patch("context_engine.cli.load_config", return_value=config), \
             patch("context_engine.cli.Path.cwd", return_value=cwd):
            result = runner.invoke(main, ["savings", "--all", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    projects = {p["project"]: p for p in data["projects"]}
    assert "p1" in projects
    assert projects["p1"]["tokens_saved"] == 3000
    assert projects["p2"]["savings_pct"] == 50


def test_savings_all_projects_empty(runner, tmp_path):
    """--all-projects with no data reports no usage."""
    config = Config(storage_path=str(tmp_path))
    from unittest.mock import patch
    with runner.isolated_filesystem():
        cwd = Path.cwd() / "empty-project"
        cwd.mkdir()
        with patch("context_engine.cli.load_config", return_value=config), \
             patch("context_engine.cli.Path.cwd", return_value=cwd):
            result = runner.invoke(main, ["savings", "--all"])
    assert result.exit_code == 0
    assert "No usage recorded" in result.output
