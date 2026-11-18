"""Loop agent Perseus: provider API -> tool call -> hasil -> jawaban."""
from __future__ import annotations

import json
import time
from pathlib import Path

from .config import api_key
from .llm import LLM, LLMError
from .tools import Registry

SYSTEM = """Kamu adalah Perseus, AI agent yang berjalan di Termux (Android) milik pengguna.
Kamu bukan Hermes. Identitasmu Perseus.

Aturan:
- Semua reasoning/token lewat provider API. Tidak ada model lokal; jangan mengaku bisa inferensi offline.
- Kamu punya tool lokal: shell, file, http, python, memory, android (lihat daftar tool).
- Gunakan tool hanya jika perlu. Jangan mengarang hasil tool.
- Sebelum mengubah/menghapus file atau menginstall/menghapus app, jelaskan singkat lalu panggil tool.
- Path file dibatasi ke workspace: {workspace}
- Mode izin: {permission}
- Jawab ringkas, bahasa Indonesia kasual, kecuali diminta lain.
- Jika tool gagal, laporkan error aslinya dan langkah berikutnya.
- Waktu sekarang: {now}
"""


class Agent:
    def __init__(self, cfg: dict, confirm=None, log=True):
        self.cfg = cfg
        self.registry = Registry(cfg)
        self.llm = LLM(cfg["base_url"], api_key(cfg), cfg["model"],
                       int(cfg.get("max_tokens", 4096)), int(cfg.get("timeout", 180)))
        self.confirm = confirm or (lambda name, args: False)
        self.permission = cfg.get("permission", "ask")
        self.max_steps = int(cfg.get("max_steps", 8))
        self.messages: list[dict] = []
        self.log = log
        self.session_file = None
        if log:
            d = Path.home() / ".perseus" / "sessions"
            d.mkdir(parents=True, exist_ok=True)
            self.session_file = d / (time.strftime("%Y%m%d-%H%M%S") + ".jsonl")

    def _system(self) -> dict:
        return {"role": "system", "content": SYSTEM.format(
            workspace=self.cfg["workspace"],
            permission=self.permission,
            now=time.strftime("%Y-%m-%d %H:%M:%S %Z"))}

    def _record(self, obj: dict) -> None:
        if self.session_file:
            with self.session_file.open("a") as f:
                f.write(json.dumps(obj, ensure_ascii=False) + "\n")

    def reset(self) -> None:
        self.messages = []

    def run(self, user_text: str, on_token=None) -> str:
        self.messages.append({"role": "user", "content": user_text})
        self._record({"role": "user", "content": user_text})
        tools = self.registry.schema()

        for step in range(self.max_steps):
            try:
                msg = self.llm.chat([self._system()] + self.messages[-40:], tools)
            except LLMError as e:
                return f"[provider error] {e}"

            content = msg.get("content") or ""
            calls = msg.get("tool_calls") or []
            self.messages.append(msg)
            self._record(msg)

            if not calls:
                return content.strip() or "(kosong)"

            for call in calls:
                fn = call.get("function", {})
                name = fn.get("name", "")
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}

                if self.permission == "read-only" and (
                        self.registry.tools.get(name) and self.registry.tools[name].danger):
                    result = "DITOLAK: mode read-only"
                elif self.registry.confirm_needed(name, args) and self.permission == "ask":
                    ok = self.confirm(name, args)
                    result = self.registry.call(name, args) if ok else "DITOLAK oleh pengguna"
                else:
                    result = self.registry.call(name, args)

                print(f"  \033[36m⟡ {name}\033[0m {json.dumps(args, ensure_ascii=False)[:160]}")
                self.messages.append({"role": "tool", "tool_call_id": call.get("id", ""),
                                      "name": name, "content": result})
                self._record({"role": "tool", "name": name, "content": result})

        return "[berhenti] batas langkah tercapai"
