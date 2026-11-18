"""Klien OpenAI-compatible minimal (stdlib saja) untuk Perseus."""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request


class LLMError(RuntimeError):
    pass


class LLM:
    def __init__(self, base_url: str, api_key: str, model: str,
                 max_tokens: int = 4096, timeout: int = 180,
                 reasoning_effort: str = "", retries: int = 3,
                 retry_delay: int = 15):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.reasoning_effort = reasoning_effort
        self.retries = max(1, retries)
        self.retry_delay = max(0, retry_delay)

    @staticmethod
    def _retryable(e: Exception) -> bool:
        if isinstance(e, urllib.error.HTTPError):
            return e.code in (408, 409, 425, 429, 500, 502, 503, 504)
        return True

    def _sleep(self, attempt: int, err: Exception) -> None:
        print(f"\033[2m[retry {attempt}/{self.retries}] {err} — tunggu "
              f"{self.retry_delay}s…\033[0m", file=sys.stderr)
        time.sleep(self.retry_delay)

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
        last = None
        for attempt in range(1, self.retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read())
            except urllib.error.HTTPError as e:
                body = e.read()[:800].decode("utf-8", "replace")
                last = LLMError(f"HTTP {e.code}: {body}")
                if self._retryable(e) and attempt < self.retries:
                    self._sleep(attempt, last)
                    continue
                raise last from None
            except Exception as e:
                last = LLMError(f"request gagal: {e}")
                if attempt < self.retries:
                    self._sleep(attempt, last)
                    continue
                raise last from None
        raise last or LLMError("request gagal")

    def models_info(self) -> list[dict]:
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
        return [m for m in (data.get("data", []) if isinstance(data, dict) else [])
                if isinstance(m, dict) and m.get("id")]

    def list_models(self) -> list[str]:
        return [m["id"] for m in self.models_info()]

    def model_context(self) -> int | None:
        for m in self.models_info():
            if m.get("id") == self.model:
                for k in ("context_length", "max_context_length", "context_window"):
                    v = m.get(k)
                    if isinstance(v, int) and v > 0:
                        return v
        return None

    def stream_chat(self, messages: list, tools: list | None = None,
                    on_text=None, on_reasoning=None, on_first=None) -> dict:
        """Streaming SSE; kembalikan message utuh (content + tool_calls)."""
        if not self.api_key:
            raise LLMError("API key kosong. Set PERSEUS_API_KEY di environment.")
        body = {"model": self.model, "messages": messages,
                "max_tokens": self.max_tokens, "stream": True}
        if self.reasoning_effort:
            body["reasoning_effort"] = self.reasoning_effort
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        req = urllib.request.Request(
            self.base_url + "/chat/completions", data=json.dumps(body).encode(),
            headers={"Authorization": "Bearer " + self.api_key,
                     "Content-Type": "application/json",
                     "Accept": "text/event-stream",
                     "User-Agent": "Perseus/0.1 (Termux)"})
        content, reasoning = [], []
        calls: dict[int, dict] = {}
        first = False
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                for raw in resp:
                    line = raw.decode("utf-8", "replace").strip()
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        j = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    ch = (j.get("choices") or [{}])[0]
                    d = ch.get("delta") or {}
                    rc = d.get("reasoning_content") or d.get("reasoning")
                    if rc:
                        if not first:
                            first = True
                            if on_first:
                                on_first()
                        reasoning.append(rc)
                        if on_reasoning:
                            on_reasoning(rc)
                    txt = d.get("content")
                    if txt:
                        if not first:
                            first = True
                            if on_first:
                                on_first()
                        content.append(txt)
                        if on_text:
                            on_text(txt)
                    for tc in d.get("tool_calls") or []:
                        i = int(tc.get("index", 0))
                        slot = calls.setdefault(i, {"id": "", "type": "function",
                                                    "function": {"name": "", "arguments": ""}})
                        if tc.get("id"):
                            slot["id"] = tc["id"]
                        fn = tc.get("function") or {}
                        if fn.get("name"):
                            slot["function"]["name"] += fn["name"]
                        if fn.get("arguments"):
                            slot["function"]["arguments"] += fn["arguments"]
        except urllib.error.HTTPError as e:
            body = e.read()[:800].decode("utf-8", "replace")
            if self.reasoning_effort and e.code == 400:
                saved, self.reasoning_effort = self.reasoning_effort, ""
                try:
                    return self.stream_chat(messages, tools, on_text, on_reasoning, on_first)
                finally:
                    self.reasoning_effort = saved
            raise LLMError(f"HTTP {e.code}: {body}") from None
        except Exception as e:
            raise LLMError(f"stream gagal: {e}") from None
        msg = {"role": "assistant", "content": "".join(content)}
        if reasoning:
            msg["reasoning_content"] = "".join(reasoning)
        if calls:
            msg["tool_calls"] = [calls[k] for k in sorted(calls)]
        return msg

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
        try:
            data = self._post("/chat/completions", body)
        except LLMError as e:
            if "HTTP 400" in str(e) and self.reasoning_effort:
                saved, self.reasoning_effort = self.reasoning_effort, ""
                try:
                    return self.chat(messages, tools)
                finally:
                    self.reasoning_effort = saved
            raise
        try:
            return data["choices"][0]["message"]
        except (KeyError, IndexError):
            raise LLMError(f"respons tidak dikenal: {json.dumps(data)[:600]}")
