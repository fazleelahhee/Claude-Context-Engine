"""Tests for git history indexer."""
import subprocess
import pytest
from context_engine.indexer.git_indexer import index_commits
from context_engine.models import ChunkType, NodeType, EdgeType


@pytest.fixture
def git_repo(tmp_path):
    """Create a minimal git repo with 3 commits."""
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True, check=True)
    for i in range(3):
        (tmp_path / f"file{i}.py").write_text(f"def fn{i}(): pass\n")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", f"Add file{i}"], cwd=tmp_path, capture_output=True, check=True)
    return tmp_path


@pytest.mark.asyncio
async def test_index_commits_returns_chunks(git_repo):
    chunks, nodes, edges = await index_commits(git_repo, max_commits=10)
    assert len(chunks) == 3
    assert all(c.chunk_type == ChunkType.COMMIT for c in chunks)


@pytest.mark.asyncio
async def test_commit_chunks_have_metadata(git_repo):
    chunks, _, _ = await index_commits(git_repo, max_commits=10)
    for chunk in chunks:
        assert "author" in chunk.metadata
        assert "hash" in chunk.metadata
        assert chunk.file_path.startswith("git:")


@pytest.mark.asyncio
async def test_commit_nodes_and_edges(git_repo):
    chunks, nodes, edges = await index_commits(git_repo, max_commits=10)
    assert len(nodes) >= 3
    assert all(n.node_type == NodeType.COMMIT for n in nodes)
    assert len(edges) > 0
    assert all(e.edge_type == EdgeType.MODIFIES for e in edges)


@pytest.mark.asyncio
async def test_incremental_since_sha(git_repo):
    chunks_all, _, _ = await index_commits(git_repo, max_commits=10)
    first_sha = chunks_all[-1].metadata["hash"]  # oldest commit
    chunks_new, _, _ = await index_commits(git_repo, since_sha=first_sha)
    assert len(chunks_new) < len(chunks_all)
