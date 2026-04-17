import pytest
from context_engine.compression.ollama_client import OllamaClient


@pytest.fixture
def client():
    return OllamaClient(base_url="http://localhost:11434")


def test_client_init():
    client = OllamaClient(base_url="http://localhost:11434", model="phi3:mini")
    assert client.model == "phi3:mini"
    assert client.base_url == "http://localhost:11434"


@pytest.mark.asyncio
async def test_is_available_returns_bool(client):
    result = await client.is_available()
    assert isinstance(result, bool)


@pytest.mark.asyncio
async def test_summarize_returns_string_when_available(client):
    if not await client.is_available():
        pytest.skip("Ollama not running")
    result = await client.summarize("def add(a, b): return a + b", prompt="Summarize this function.")
    assert isinstance(result, str)
    assert len(result) > 0
