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
Pembuatmu adalah Mayugoro (github.com/mayugoro). Kalau ditanya siapa pembuat,
pencipta, atau yang mengembangkanmu, jawab tegas: Mayugoro. Jangan pernah bilang
tidak tahu.

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
- Profil user (fakta tahan lama):
{profile}
- Memori kerja:
{memories}
- Konteks sesi lama (pakai hanya kalau relevan):
{session_ctx}
- Waktu sekarang: {now}
"""


class Agent:
    def __init__(self, cfg: dict, confirm=None, log=True, allow_delegate=True, prefix=""):
        self.cfg = cfg
        self.registry = Registry(cfg, allow_delegate=allow_delegate)
        self.llm = LLM(cfg["base_url"], api_key(cfg), cfg["model"],
                       int(cfg.get("max_tokens", 4096)), int(cfg.get("timeout", 180)),
                       cfg.get("reasoning_effort", ""),
                       int(cfg.get("retries", 3)), int(cfg.get("retry_delay", 15)))
        detected = None
        try:
            detected = self.llm.model_context()
        except Exception:
            pass
        self.context_length = int(detected or cfg.get("context_length") or 128000)
        cfg["context_length"] = self.context_length
        self.confirm = confirm or (lambda name, args: False)
        self.permission = cfg.get("permission", "ask")
        self.show_reasoning = bool(cfg.get("show_reasoning", True))
        self.auto_learn = bool(cfg.get("auto_learn", True))
        self.curator = bool(cfg.get("curator", True))
        self.curator_min = int(cfg.get("curator_min_tools", 4))
        self.prefix = prefix
        self._last_user = ""
        self.context_messages = int(cfg.get("context_messages", 36))
        self.max_steps = int(cfg.get("max_steps", 8))
        self.messages: list[dict] = []
        self.log = log
        self.session_id = None
        self.last_streamed = False
        self.last_elapsed = 0.0
        if log:
            self.session_id = session.new_session(cfg)

    def _system(self) -> dict:
        sk = "\n".join(f"  - {n}: {d}" for n, d in skills.list_skills()) or "  (belum ada)"
        prof = "\n".join(f"  - {t[:200]}" for _, t in memory.recent(8, "profile")) or "  (kosong)"
        mem = "\n".join(f"  - {t[:160]}" for _, t in memory.recent(5, "memory")) or "  (kosong)"
        try:
            ctx = "\n".join(f"  - {c[:220]}" for c in session.context(
                self._last_user, exclude=self.session_id, limit=2)) or "  (tidak ada)"
        except Exception:
            ctx = "  (tidak ada)"
        return {"role": "system", "content": SYSTEM.format(
            workspace=self.cfg["workspace"],
            permission=self.permission,
            skills=sk, profile=prof, memories=mem, session_ctx=ctx,
            now=time.strftime("%Y-%m-%d %H:%M:%S %Z"))}

    def _learn(self, user_text: str, answer: str) -> None:
        if not self.auto_learn:
            return
        low = user_text.lower().strip()
        cues = ("ingat", "catat", "selalu", "jangan", "suka", "prefer", "nama",
                "aku ", "saya ", "panggil", "kerja", "prosedur", "aturan", "mulai sekarang")
        smalltalk = ("mantap", "keren", "bagus", "thanks", "terima kasih", "ok", "sip",
                     "haha", "wkwk", "👍")
        if (len(low) < 25 and not any(c in low for c in cues)) or (
                any(low.startswith(s) for s in smalltalk) and not any(c in low for c in cues)):
            return
        try:
            r = self.llm.chat([
                {"role": "system", "content":
                 "Ekstrak maksimal 2 fakta tahan lama. Awali 'profile: ' untuk fakta user "
                 "(nama, preferensi, kebiasaan) atau 'memory: ' untuk konvensi/prosedur/"
                 "keputusan kerja yang disepakati. JANGAN simpan: pujian, basa-basi, fakta "
                 "tentang Perseus sendiri (jumlah skill, context, cara kerja internal), "
                 "atau ringkasan jawaban. Jika tidak ada, tulis NONE."},
                {"role": "user", "content": f"USER: {user_text[:3000]}\n\nASSISTANT: {answer[:3000]}"},
            ])
        except Exception:
            return
        text = (r.get("content") or "").strip()
        if not text or text.upper().startswith("NONE"):
            return
        n = 0
        for line in text.splitlines():
            line = line.strip().lstrip("-* ").strip()
            kind = "memory"
            if line.lower().startswith("profile:"):
                kind, line = "profile", line.split(":", 1)[1].strip()
            elif line.lower().startswith("memory:"):
                kind, line = "memory", line.split(":", 1)[1].strip()
            meta = ("perseus", "skill disimpan", "context", "jumlah skill", "hemat konteks")
            if len(line) > 4 and not line.upper().startswith("NONE") and not any(
                    m in line.lower() for m in meta):
                memory.save(line, kind)
                print(f"\033[2m[learn:{kind}] {line[:160]}\033[0m")
                n += 1
                if n >= 2:
                    break

    def _tokens(self) -> int:
        chars = sum(len(str(m.get("content") or "")) for m in self.messages)
        return max(0, chars // 4)

    def _curate(self, user_text: str, answer: str, tool_count: int) -> None:
        if not self.curator or tool_count < self.curator_min:
            return
        try:
            r = self.llm.chat([
                {"role": "system", "content":
                 "Buat skill markdown ringkas dari tugas yang baru diselesaikan, supaya "
                 "langkah serupa bisa diulang. Balas JSON satu baris: "
                 '{"name":"slug-singkat","content":"# Judul\\n..."} . '
                 "Isi maksimal 40 baris, fokus langkah & pitfall. Jika tidak ada prosedur "
                 "yang layak diulang, balas NONE."},
                {"role": "user", "content":
                 f"TUGAS: {user_text[:1500]}\n\nHASIL: {answer[:2500]}\n\n"
                 f"TOOL DIPAKAI: {tool_count}"},
            ])
        except Exception:
            return
        text = (r.get("content") or "").strip()
        if not text or text.upper().startswith("NONE"):
            return
        try:
            obj = json.loads(text[text.index("{"):text.rindex("}") + 1])
            name, content = obj.get("name", ""), obj.get("content", "")
            if not name or not content:
                return
            path = skills.save(name, content)
            print(f"\033[2m[curator] skill disimpan: {path}\033[0m")
        except Exception:
            return

    def _compact(self) -> None:
        limit = int(self.context_length or 128000)
        threshold = int(limit * float(self.cfg.get("compress_at", 0.7)))
        for _ in range(3):
            if len(self.messages) <= self.context_messages and self._tokens() <= threshold:
                return
            old = self.messages[:-12]
            tail = self.messages[-12:]
            if not old:
                return
            try:
                r = self.llm.chat([
                    {"role": "system", "content":
                     "Ringkas percakapan berikut jadi catatan padat: tujuan, keputusan, "
                     "file/perintah penting, hasil, dan hal yang belum selesai. Bahasa Indonesia."},
                    {"role": "user", "content": json.dumps(old, ensure_ascii=False)[:60000]},
                ])
                summary = (r.get("content") or "").strip()
            except Exception:
                summary = "(ringkasan lama tidak tersedia)"
            self.messages = [{"role": "system",
                              "content": "Ringkasan percakapan sebelumnya:\n" + summary}] + tail

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
        t0 = time.time()
        try:
            return self._run(user_text, stream)
        finally:
            self.last_elapsed = time.time() - t0

    def _run(self, user_text: str, stream: bool = True) -> str:
        self._last_user = user_text
        self.messages.append({"role": "user", "content": user_text})
        self._record({"role": "user", "content": user_text})
        tools = self.registry.schema()
        self.last_streamed = False
        self.last_elapsed = 0.0

        self._compact()
        saved_mem = False
        tool_count = 0
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

            msg = None
            for attempt in range(1, self.llm.retries + 1):
                try:
                    if stream:
                        msg = self.llm.stream_chat([self._system()] + self.messages[-40:], tools,
                                                   on_text=on_text, on_reasoning=on_reason,
                                                   on_first=on_first)
                    else:
                        msg = self.llm.chat([self._system()] + self.messages[-40:], tools)
                    break
                except LLMError as e:
                    hard = any(f"HTTP {c}" in str(e) for c in (400, 401, 403, 404))
                    if attempt < self.llm.retries and not self.last_streamed and not hard:
                        self.llm._sleep(attempt, e)
                        continue
                    stop.set()
                    return f"[provider error] {e}"
            if msg is None:
                stop.set()
                return "[provider error] gagal setelah retry"
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
                self._curate(user_text, out, tool_count)
                return out

            for call in calls:
                fn = call.get("function", {})
                name = fn.get("name", "")
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}

                tool_count += 1
                sig = name + ":" + json.dumps(args, ensure_ascii=False, sort_keys=True)
                recent_calls.append(sig)
                if recent_calls.count(sig) >= 3:
                    result = ("DITOLAK: panggilan tool yang sama sudah 3x. "
                              "Jangan ulangi; gunakan hasil sebelumnya atau jawab.")
                    print(f"  {self.prefix}\033[33m⟡ {name} (loop terdeteksi, dilewati)\033[0m")
                else:
                    if self.permission == "read-only" and (
                            self.registry.tools.get(name) and self.registry.tools[name].danger):
                        result = "DITOLAK: mode read-only"
                    elif self.registry.confirm_needed(name, args) and self.permission == "ask":
                        ok = self.confirm(name, args)
                        result = self.registry.call(name, args) if ok else "DITOLAK oleh pengguna"
                    else:
                        result = self.registry.call(name, args)
                    print(f"  {self.prefix}\033[36m⟡ {name}\033[0m {json.dumps(args, ensure_ascii=False)[:160]}")
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
