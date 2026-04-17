import json
import pytest
from unittest.mock import MagicMock
from context_engine.integration.mcp_server import ContextEngineMCP


def test_mcp_server_has_required_tools():
    server = ContextEngineMCP.__new__(ContextEngineMCP)
    tool_names = server.get_tool_names()
    assert "context_search" in tool_names
    assert "expand_chunk" in tool_names
    assert "related_context" in tool_names
    assert "session_recall" in tool_names
    assert "index_status" in tool_names
    assert "reindex" in tool_names


def _make_server(tmp_path):
    """Build a minimal ContextEngineMCP with a tmp storage dir."""
    config = MagicMock()
    config.storage_path = str(tmp_path)
    config.output_compression = "standard"
    server = ContextEngineMCP.__new__(ContextEngineMCP)
    server._config = config
    server._output_level = "standard"
    server._stats_path = tmp_path / "stats.json"
    server._stats = server._load_stats()
    return server


@pytest.mark.asyncio
async def test_index_status_no_queries(tmp_path):
    server = _make_server(tmp_path)
    result = await server._handle_index_status()
    text = result[0].text
    assert "no queries recorded yet" in text


@pytest.mark.asyncio
async def test_index_status_with_tracked_stats(tmp_path):
    server = _make_server(tmp_path)
    server._stats = {"queries": 5, "raw_tokens": 1000, "served_tokens": 400}
    result = await server._handle_index_status()
    text = result[0].text
    assert "5 queries" in text
    assert "1,000" in text   # raw
    assert "400" in text     # served
    assert "600" in text     # saved
    assert "60%" in text
