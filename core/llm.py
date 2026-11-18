"""Klien OpenAI-compatible minimal (stdlib saja) untuk Perseus."""
from __future__ import annotations

import json
import urllib.error
import urllib.request


class LLMError(RuntimeError):
    pass


class LLM:
    def __init__(self, base_url: str, api_key: str, model: str,
                 max_tokens: int = 4096, timeout: int = 180,
                 reasoning_effort: str = ""):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.reasoning_effort = reasoning_effort

    def _post(self, path: str, body: dict) -> dict:
        if not self.api_key:
            raise LLMError("API key kosong. Set PERSEUS_API_KEY di environment.")
        req = urllib.request.Request(
            self.base_url + path,
            data=json.dumps(body).encode(),
            headers={
                "Authorization": "Bearer " + self.api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "Perseus/0.1 (Termux)",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body = e.read()[:800].decode("utf-8", "replace")
            raise LLMError(f"HTTP {e.code}: {body}") from None
        except Exception as e:
            raise LLMError(f"request gagal: {e}") from None

    def list_models(self) -> list[str]:
        req = urllib.request.Request(
            self.base_url + "/models",
            headers={
                "Authorization": "Bearer " + self.api_key,
                "Accept": "application/json",
                "User-Agent": "Perseus/0.1 (Termux)",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            raise LLMError(f"HTTP {e.code}: {e.read()[:300].decode('utf-8', 'replace')}") from None
        except Exception as e:
            raise LLMError(f"request gagal: {e}") from None
        out = []
        for m in data.get("data", []) if isinstance(data, dict) else []:
            mid = m.get("id") if isinstance(m, dict) else None
            if mid:
                out.append(mid)
        return out

    def chat(self, messages: list, tools: list | None = None) -> dict:
        body = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
        }
        if self.reasoning_effort:
            body["reasoning_effort"] = self.reasoning_effort
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        data = self._post("/chat/completions", body)
        try:
            return data["choices"][0]["message"]
        except (KeyError, IndexError):
            raise LLMError(f"respons tidak dikenal: {json.dumps(data)[:600]}")
