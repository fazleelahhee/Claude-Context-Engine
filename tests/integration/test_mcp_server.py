import pytest
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
