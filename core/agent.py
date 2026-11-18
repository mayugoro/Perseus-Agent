"""Loop agent Perseus: provider API -> tool call -> hasil -> jawaban."""
from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

from . import memory, session, skills
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
- Berpikir mendalam sebelum menjawab: tentukan tujuan, batasan, dan langkah;
  pertimbangkan beberapa pendekatan, pilih yang paling kokoh, lalu verifikasi hasil
  sebelum menyimpulkan. Jangan berhenti di jawaban pertama yang terlihat benar.
- Gaya: langsung ke inti, tanpa basa-basi. Selesai = laporan singkat: apa yang
  berubah, apa yang terverifikasi, apa yang tersisa.
- Jika tool gagal, laporkan error aslinya dan langkah berikutnya.
- Skill yang tersedia (pakai skill_view untuk detail):
{skills}
- Memori terbaru:
{memories}
- Waktu sekarang: {now}
"""


class Agent:
    def __init__(self, cfg: dict, confirm=None, log=True, allow_delegate=True):
        self.cfg = cfg
        self.registry = Registry(cfg, allow_delegate=allow_delegate)
        self.llm = LLM(cfg["base_url"], api_key(cfg), cfg["model"],
                       int(cfg.get("max_tokens", 4096)), int(cfg.get("timeout", 180)),
                       cfg.get("reasoning_effort", ""))
        self.confirm = confirm or (lambda name, args: False)
        self.permission = cfg.get("permission", "ask")
        self.show_reasoning = bool(cfg.get("show_reasoning", True))
        self.auto_learn = bool(cfg.get("auto_learn", True))
        self.context_messages = int(cfg.get("context_messages", 36))
        self.max_steps = int(cfg.get("max_steps", 8))
        self.messages: list[dict] = []
        self.log = log
        self.session_id = None
        self.last_streamed = False
        if log:
            self.session_id = session.new_session(cfg)

    def _system(self) -> dict:
        sk = "\n".join(f"  - {n}: {d}" for n, d in skills.list_skills()) or "  (belum ada)"
        mem = "\n".join(f"  - {t[:160]}" for _, t in memory.recent(5)) or "  (kosong)"
        return {"role": "system", "content": SYSTEM.format(
            workspace=self.cfg["workspace"],
            permission=self.permission,
            skills=sk, memories=mem,
            now=time.strftime("%Y-%m-%d %H:%M:%S %Z"))}

    def _learn(self, user_text: str, answer: str) -> None:
        if not self.auto_learn:
            return
        try:
            r = self.llm.chat([
                {"role": "system", "content":
                 "Ekstrak maksimal 2 fakta tahan lama dari percakapan: preferensi user, "
                 "konvensi, prosedur, atau keputusan penting. Tulis satu fakta per baris "
                 "diawali '- '. Jika tidak ada yang layak disimpan, tulis NONE."},
                {"role": "user", "content": f"USER: {user_text[:3000]}\n\nASSISTANT: {answer[:3000]}"},
            ])
        except Exception:
            return
        text = (r.get("content") or "").strip()
        if not text or text.upper().startswith("NONE"):
            return
        n = 0
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("- ") and len(line) > 4:
                memory.save(line[2:].strip())
                print(f"\033[2m[learn] {line[2:][:160]}\033[0m")
                n += 1
                if n >= 2:
                    break

    def _compact(self) -> None:
        if len(self.messages) <= self.context_messages:
            return
        old = self.messages[:-12]
        tail = self.messages[-12:]
        try:
            r = self.llm.chat([
                {"role": "system", "content": "Ringkas percakapan berikut jadi catatan padat: "
                 "tujuan, keputusan, file/perintah penting, hasil. Bahasa Indonesia."},
                {"role": "user", "content": json.dumps(old, ensure_ascii=False)[:24000]},
            ])
            summary = (r.get("content") or "").strip()
        except Exception:
            summary = "(ringkasan lama tidak tersedia)"
        self.messages = [{"role": "system", "content": "Ringkasan percakapan sebelumnya:\n" + summary}] + tail

    def _record(self, obj: dict) -> None:
        if self.session_id:
            session.append(self.session_id, obj)

    def reset(self) -> None:
        self.messages = []

    def _spinner(self, stop: threading.Event):
        frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        i = 0
        while not stop.wait(0.08):
            sys.stdout.write("\r\033[2m" + frames[i % len(frames)] + " thinking…\033[0m")
            sys.stdout.flush()
            i += 1
        sys.stdout.write("\r\033[2K")
        sys.stdout.flush()

    def run(self, user_text: str, stream: bool = True) -> str:
        self.messages.append({"role": "user", "content": user_text})
        self._record({"role": "user", "content": user_text})
        tools = self.registry.schema()
        self.last_streamed = False

        self._compact()
        saved_mem = False
        recent_calls: list[str] = []
        step = 0
        while self.max_steps <= 0 or step < self.max_steps:
            step += 1
            stop = threading.Event()
            if stream and sys.stdout.isatty():
                threading.Thread(target=self._spinner, args=(stop,), daemon=True).start()
            state = {"reason": False, "blue": False}

            def on_first():
                stop.set()

            def on_reason(chunk: str):
                if not self.show_reasoning:
                    return
                if not state["reason"]:
                    sys.stdout.write("\033[2m[think] ")
                    state["reason"] = True
                sys.stdout.write(chunk)
                sys.stdout.flush()

            def on_text(chunk: str):
                if state["reason"]:
                    sys.stdout.write("\033[0m\n")
                    state["reason"] = False
                if not state["blue"]:
                    sys.stdout.write("\033[36m")
                    state["blue"] = True
                self.last_streamed = True
                sys.stdout.write(chunk)
                sys.stdout.flush()

            try:
                if stream:
                    msg = self.llm.stream_chat([self._system()] + self.messages[-40:], tools,
                                               on_text=on_text, on_reasoning=on_reason,
                                               on_first=on_first)
                else:
                    msg = self.llm.chat([self._system()] + self.messages[-40:], tools)
            except LLMError as e:
                stop.set()
                return f"[provider error] {e}"
            finally:
                stop.set()
                time.sleep(0.02)
                if state["reason"]:
                    sys.stdout.write("\033[0m\n")
                    state["reason"] = False
                if state["blue"]:
                    sys.stdout.write("\033[0m")
                    state["blue"] = False

            content = msg.get("content") or ""
            calls = msg.get("tool_calls") or []
            self.messages.append(msg)
            self._record(msg)

            if calls and self.last_streamed:
                print()
            if not calls:
                out = content.strip() or "(kosong)"
                if self.last_streamed:
                    print()
                if not saved_mem:
                    self._learn(user_text, out)
                return out

            for call in calls:
                fn = call.get("function", {})
                name = fn.get("name", "")
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}

                sig = name + ":" + json.dumps(args, ensure_ascii=False, sort_keys=True)
                recent_calls.append(sig)
                if recent_calls.count(sig) >= 3:
                    result = ("DITOLAK: panggilan tool yang sama sudah 3x. "
                              "Jangan ulangi; gunakan hasil sebelumnya atau jawab.")
                    print(f"  \033[33m⟡ {name} (loop terdeteksi, dilewati)\033[0m")
                else:
                    if self.permission == "read-only" and (
                            self.registry.tools.get(name) and self.registry.tools[name].danger):
                        result = "DITOLAK: mode read-only"
                    elif self.registry.confirm_needed(name, args) and self.permission == "ask":
                        ok = self.confirm(name, args)
                        result = self.registry.call(name, args) if ok else "DITOLAK oleh pengguna"
                    else:
                        result = self.registry.call(name, args)
                    print(f"  \033[36m⟡ {name}\033[0m {json.dumps(args, ensure_ascii=False)[:160]}")
                if name == "memory_save" and result.startswith("OK"):
                    saved_mem = True
                self.messages.append({"role": "tool", "tool_call_id": call.get("id", ""),
                                      "name": name, "content": result})
                self._record({"role": "tool", "name": name,
                              "tool_call_id": call.get("id", ""), "content": result})

        try:
            r = self.llm.chat([self._system()] + self.messages[-30:] + [{
                "role": "system",
                "content": "Batas langkah tercapai. Jangan panggil tool lagi. "
                           "Berikan ringkasan: apa yang sudah dikerjakan, apa yang "
                           "terverifikasi, dan apa yang tersisa."}], None)
            text = (r.get("content") or "").strip()
        except Exception:
            text = ""
        return text or "[berhenti] batas langkah tercapai"
