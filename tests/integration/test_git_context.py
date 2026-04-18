"""Tests for git context helpers used by the init prompt."""
import os
import subprocess
import pytest
from context_engine.integration.git_context import (
    get_recent_commits,
    get_recently_modified_files,
    get_working_state,
)


@pytest.fixture
def git_repo(tmp_path):
    """Create a small git repo with a couple of commits."""
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)
    # First commit
    (tmp_path / "hello.py").write_text("print('hello')\n")
    subprocess.run(["git", "add", "hello.py"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat: add hello"], cwd=tmp_path, capture_output=True)
    # Second commit
    (tmp_path / "world.py").write_text("print('world')\n")
    subprocess.run(["git", "add", "world.py"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat: add world"], cwd=tmp_path, capture_output=True)
    return tmp_path


def test_get_recent_commits(git_repo):
    commits = get_recent_commits(str(git_repo))
    assert len(commits) == 2
    assert "feat: add world" in commits[0]
    assert "feat: add hello" in commits[1]


def test_get_recent_commits_respects_count(git_repo):
    commits = get_recent_commits(str(git_repo), count=1)
    assert len(commits) == 1
    assert "feat: add world" in commits[0]


def test_get_recent_commits_non_git_dir(tmp_path):
    commits = get_recent_commits(str(tmp_path))
    assert commits == []


def test_get_working_state_clean(git_repo):
    state = get_working_state(str(git_repo))
    # Should at least have the branch name
    assert any("Branch:" in line for line in state)


def test_get_working_state_with_modifications(git_repo):
    (git_repo / "hello.py").write_text("print('modified')\n")
    state = get_working_state(str(git_repo))
    assert any("Modified" in line or "unstaged" in line for line in state)


def test_get_working_state_with_untracked(git_repo):
    (git_repo / "new_file.py").write_text("x = 1\n")
    state = get_working_state(str(git_repo))
    assert any("Untracked" in line for line in state)


def test_get_recently_modified_files(git_repo):
    files = get_recently_modified_files(str(git_repo))
    assert "world.py" in files
    assert "hello.py" in files


def test_get_recently_modified_files_includes_unstaged(git_repo):
    (git_repo / "hello.py").write_text("print('changed')\n")
    files = get_recently_modified_files(str(git_repo))
    assert files[0] == "hello.py"  # unstaged changes come first


def test_get_recently_modified_files_non_git_dir(tmp_path):
    files = get_recently_modified_files(str(tmp_path))
    assert files == []
