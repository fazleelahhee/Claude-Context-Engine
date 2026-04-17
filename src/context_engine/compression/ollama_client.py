"""Ollama API client for local LLM summarization."""

import httpx


class OllamaClient:
    def __init__(self, base_url="http://localhost:11434", model="phi3:mini", timeout=30.0):
        self.base_url = base_url
        self.model = model
        self._timeout = timeout

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                return resp.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    async def summarize(self, content: str, prompt: str) -> str:
        full_prompt = prompt.format(content=content) if "{content}" in prompt else f"{prompt}\n\n{content}"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": full_prompt,
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 256},
                },
            )
            resp.raise_for_status()
            return resp.json()["response"].strip()
