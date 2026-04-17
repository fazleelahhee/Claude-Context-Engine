import pytest
from context_engine.storage.remote_backend import RemoteBackend


def test_remote_backend_init():
    backend = RemoteBackend(host="fazle@198.162.2.2")
    assert backend.host == "fazle@198.162.2.2"


@pytest.mark.asyncio
async def test_is_reachable_returns_bool():
    backend = RemoteBackend(host="fazle@198.162.2.2", fallback_to_local=True)
    result = await backend.is_reachable()
    assert isinstance(result, bool)


@pytest.mark.asyncio
async def test_fallback_flag():
    backend = RemoteBackend(host="invalid-host", fallback_to_local=True)
    assert backend.fallback_to_local is True
