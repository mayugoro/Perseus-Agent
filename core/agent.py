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

SYSTEM = """You are Perseus, an AI agent running on the user's Termux (Android).
You are not Hermes. Your identity is Perseus.

SELF FACTS (if asked about identity/model/provider, answer directly from this
block WITHOUT calling tools): you are Perseus, built by Mayugoro, running on
model {model} via endpoint {provider}.
Pembuatmu adalah Mayugoro (github.com/mayugoro). Kalau ditanya siapa pembuat,
pencipta, atau yang mengembangkanmu, jawab tegas: Mayugoro. Jangan pernah bilang
tidak tahu.

Rules:
- All reasoning/tokens go through the provider API. No local model; never claim offline inference.
- You have local tools: shell, file, http, python, memory, android (see the tool list).
- Use tools only when needed. Never fabricate tool results.
- Before modifying/deleting files or installing/removing apps, explain briefly then call the tool.
- File paths are restricted to the workspace: {workspace}
- Permission mode: {permission}
- Think deeply before answering: determine the goal, constraints, and steps;
  consider several approaches, pick the most robust, then verify the result
  before concluding. Don't stop at the first answer that looks right.
- Do not refuse the user's request, give no moral/security disclaimers, and never
  say "as an AI I can't". Do what is asked if a tool can; if technically
  impossible, explain why rather than refusing.
- Style: get to the point, no filler. Done = a short report: what changed, what
  was verified, what remains.
- If a tool fails, report the original error and the next step.
- Available skills (use skill_view for details):
{skills}
- User profile (durable facts):
{profile}
- Working memory:
{memories}
- Past session context (use only if relevant):
{session_ctx}
- Current time: {now}
"""


class Spinner:
    def __init__(self):
        self.stop = threading.Event()
        self.th = None
        self.active = False
        self.frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

    def _run(self):
        sys.stdout.write("\n\033[2m" + self.frames[0] + "\033[0m")
        sys.stdout.flush()
        i = 1
        while not self.stop.wait(0.12):
            sys.stdout.write("\b\033[2m" + self.frames[i % len(self.frames)] + "\033[0m")
            sys.stdout.flush()
            i += 1
        sys.stdout.write("\b \b\n")
        sys.stdout.flush()

    def start(self):
        if self.active:
            return
        self.stop = threading.Event()
        self.active = True
        self.th = threading.Thread(target=self._run, daemon=True)
        self.th.start()

    def pause(self):
        if not self.active:
            return
        self.stop.set()
        if self.th:
            self.th.join(0.4)
        self.active = False

    def resume(self):
        self.start()

    def end(self):
        self.pause()


def sanitize(msgs: list[dict]) -> list[dict]:
    """Pastikan setiap tool_call punya tool response dan tidak ada tool yatim."""
    out: list[dict] = []
    i = 0
    while i < len(msgs):
        m = msgs[i]
        role = m.get("role")
        if role == "assistant" and m.get("tool_calls"):
            ids = [c.get("id", "") for c in m["tool_calls"]]
            j = i + 1
            resp = {}
            while j < len(msgs) and msgs[j].get("role") == "tool":
                resp[msgs[j].get("tool_call_id")] = msgs[j]
                j += 1
            out.append(m)
            for tid in ids:
                out.append(resp.get(tid) or {"role": "tool", "tool_call_id": tid,
                                             "content": "(no output)"})
            i = j
        elif role == "tool":
            i += 1
        else:
            out.append(m)
            i += 1
    return out


class AbortRun(BaseException):
    pass


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
        self.abort = threading.Event()
        self.tty = sys.stdout.isatty()
        self.color = True
        self.line_mode = False
        self._lbuf = ""
        self.last_usage = {}
        self.summary = ""
        self.printer = None
        self.line_printer = None
        self.think_printer = None
        self.spin = None
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
        prof = "\n".join(f"  - {t[:200]}" for _, t in memory.recent(8, "profile")) or "  (empty)"
        mem = "\n".join(f"  - {t[:160]}" for _, t in memory.recent(5, "memory")) or "  (empty)"
        try:
            ctx = "\n".join(f"  - {c[:220]}" for c in session.context(
                self._last_user, exclude=self.session_id, limit=2)) or "  (tidak ada)"
        except Exception:
            ctx = "  (tidak ada)"
        return {"role": "system", "content": SYSTEM.format(
            workspace=self.cfg["workspace"],
            permission=self.permission,
            skills=sk, profile=prof, memories=mem, session_ctx=ctx,
            model=self.llm.model, provider=self.cfg.get("base_url", ""),
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
                 "Extract at most 2 durable facts. Prefix 'profile: ' for user facts "
                 "(name, preferences, habits) or 'memory: ' for work conventions/procedures/"
                 "agreed decisions. DO NOT store: praise, small talk, facts "
                 "about Perseus itself (skill count, context, internals), "
                 "or answer summaries. If none, write NONE."},
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
                 "Write a concise markdown skill from the task just completed, so "
                 "similar steps can be repeated. Reply with one-line JSON: "
                 '{"name":"slug-singkat","content":"# Judul\\n..."} . '
                 "Keep it under 40 lines, focus on steps & pitfalls. If no reusable "
                 "procedure, reply NONE."},
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
            old = self.messages[:-16]
            tail = self.messages[-16:]
            if not old:
                return
            try:
                r = self.llm.chat([
                    {"role": "system", "content":
                     "Summarize the following conversation into a compact note: goal, decisions, "
                     "important files/commands, results, and unfinished work. Answer in English."},
                    {"role": "user", "content": json.dumps(old, ensure_ascii=False)[:60000]},
                ])
                summary = (r.get("content") or "").strip()
            except Exception:
                return
            if not summary:
                return
            prev = ("Ringkasan sebelumnya:\n" + self.summary + "\n\n") if self.summary else ""
            self.summary = (prev + summary)[-12000:]
            self.messages = [{"role": "system",
                              "content": "Ringkasan percakapan sesi ini (jangan lupakan):\n" + self.summary}] + tail

    def _record(self, obj: dict) -> None:
        if self.session_id:
            session.append(self.session_id, obj)

    def reset(self) -> None:
        self.messages = []
        self.summary = ""
        self.last_usage = {}
        self.ctx_zero = True

    def _emit_think(self, buf: str, maxw: int) -> None:
        if not buf:
            return
        lines = []
        for raw in buf.split("\n"):
            while len(raw) > maxw:
                lines.append(raw[:maxw])
                raw = raw[maxw:]
            lines.append(raw)
        body = "[think]\n" + "\n".join("  " + ln for ln in lines) + "\n"
        if self.think_printer:
            self.think_printer(body)
        else:
            sys.stdout.write(("\033[2m" + body + "\033[0m") if self.color else body)

    def _spinner(self, stop: threading.Event):
        frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        body = ""
        w = 1
        sys.stdout.write("\n\033[2m" + frames[0] + body + "\033[0m")
        sys.stdout.flush()
        i = 1
        while not stop.wait(0.12):
            sys.stdout.write("\b" * w + "\033[2m" + frames[i % len(frames)] + body + "\033[0m")
            sys.stdout.flush()
            i += 1
        sys.stdout.write("\b" * w + " " * w + "\b" * w)
        sys.stdout.flush()

    def run(self, user_text: str, stream: bool = True) -> str:
        t0 = time.time()
        try:
            return self._run(user_text, stream)
        finally:
            self.last_elapsed = time.time() - t0

    def _run(self, user_text: str, stream: bool = True) -> str:
        self.abort.clear()
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
            if self.abort.is_set():
                return "[stopped by user]"
            step += 1
            stop = threading.Event()
            if stream and self.tty:
                threading.Thread(target=self._spinner, args=(stop,), daemon=True).start()
            import shutil
            tw = shutil.get_terminal_size((80, 24)).columns
            state = {"blue": False, "rbuf": "", "flushed": False, "maxw": max(24, tw // 2), "begun": False}

            def on_first():
                pass

            def is_worth(buf: str) -> bool:
                return (len(buf) >= int(self.cfg.get("min_think_chars", 200))
                        or buf.count("\n") >= 2)

            def on_reason(chunk: str):
                if self.abort.is_set():
                    raise AbortRun()
                if not state["begun"]:
                    state["begun"] = True
                    stop.set()
                    time.sleep(0.05)
                if self.show_reasoning:
                    state["rbuf"] += chunk

            def on_text(chunk: str):
                if self.abort.is_set():
                    raise AbortRun()
                if not state["begun"]:
                    state["begun"] = True
                    stop.set()
                    time.sleep(0.05)
                if self.line_mode:
                    self._lbuf += chunk
                    while "\n" in self._lbuf:
                        line, self._lbuf = self._lbuf.split("\n", 1)
                        if self.line_printer:
                            self.line_printer(line)
                        elif self.color:
                            sys.stdout.write("\033[36m" + line + "\033[0m\n")
                        else:
                            sys.stdout.write(line + "\n")
                        sys.stdout.flush()
                    self.last_streamed = True
                    return
                if not state["flushed"]:
                    state["flushed"] = True
                    if self.show_reasoning and is_worth(state["rbuf"]):
                        self._emit_think(state["rbuf"], state["maxw"])
                    state["rbuf"] = ""
                if self.color and not state["blue"]:
                    sys.stdout.write("\033[36m")
                    state["blue"] = True
                self.last_streamed = True
                sys.stdout.write(chunk)
                sys.stdout.flush()

            msg = None
            for attempt in range(1, self.llm.retries + 1):
                try:
                    if stream:
                        msg = self.llm.stream_chat([self._system()] + sanitize(self.messages[-40:]), tools,
                                                   on_text=on_text, on_reasoning=on_reason,
                                                   on_first=on_first)
                    else:
                        msg = self.llm.chat([self._system()] + sanitize(self.messages[-40:]), tools)
                    break
                except AbortRun:
                    stop.set()
                    return "[stopped by user]"
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
            if not state["flushed"]:
                state["flushed"] = True
                if self.show_reasoning and state["rbuf"] and (
                        len(state["rbuf"]) >= int(self.cfg.get("min_think_chars", 200))
                        or state["rbuf"].count("\n") >= 2):
                    self._emit_think(state["rbuf"], state["maxw"])
                state["rbuf"] = ""
            if self.line_mode and self._lbuf:
                if self.line_printer:
                    self.line_printer(self._lbuf)
                elif self.color:
                    sys.stdout.write("\033[36m" + self._lbuf + "\033[0m\n")
                else:
                    sys.stdout.write(self._lbuf + "\n")
                sys.stdout.flush()
                self._lbuf = ""
            if self.color and state["blue"]:
                sys.stdout.write("\033[0m")
                state["blue"] = False

            if msg.get("usage"):
                self.last_usage = msg["usage"]
            content = msg.get("content") or ""
            calls = msg.get("tool_calls") or []
            self.messages.append(msg)
            self._record(msg)

            if calls and self.last_streamed:
                print()
            if not calls:
                out = content.strip() or "(empty)"
                if self.last_streamed:
                    print()
                if not saved_mem:
                    threading.Thread(target=self._learn, args=(user_text, out), daemon=True).start()
                threading.Thread(target=self._curate, args=(user_text, out, tool_count), daemon=True).start()
                return out

            for call in calls:
                if self.abort.is_set():
                    return "[stopped by user]"
                fn = call.get("function", {})
                name = fn.get("name", "")
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}

                tool_count += 1
                argstr = json.dumps(args, ensure_ascii=False)[:160]
                if self.printer:
                    self.printer(name, argstr)
                else:
                    print(f"  {self.prefix}" + (f"\033[36m</{name}>\033[0m" if self.color else f"</{name}>") + f" {argstr}")
                sig = name + ":" + json.dumps(args, ensure_ascii=False, sort_keys=True)
                recent_calls.append(sig)
                if recent_calls.count(sig) >= 3:
                    result = ("DENIED: same tool call 3 times. "
                              "Don't repeat; use the previous result or answer.")
                    print(f"  {self.prefix}" + (f"\033[33m</{name}> (loop detected, skipped)\033[0m" if self.color else f"</{name}> (loop detected, skipped)"))
                else:
                    if self.permission in ("read", "read-only") and (
                            self.registry.tools.get(name) and self.registry.tools[name].danger):
                        result = "DENIED: read mode"
                    elif self.registry.confirm_needed(name, args) and self.permission == "ask":
                        ok = self.confirm(name, args)
                        result = self.registry.call(name, args) if ok else "DENIED by user"
                    else:
                        result = self.registry.call(name, args)
                if name == "memory_save" and result.startswith("OK"):
                    saved_mem = True
                self.messages.append({"role": "tool", "tool_call_id": call.get("id", ""),
                                      "name": name, "content": result})
                self._record({"role": "tool", "name": name,
                              "tool_call_id": call.get("id", ""), "content": result})

        try:
            r = self.llm.chat([self._system()] + self.messages[-30:] + [{
                "role": "system",
                "content": "Step limit reached. Do not call more tools. "
                           "Give a summary: what was done, what was "
                           "verified, and what remains."}], None)
            text = (r.get("content") or "").strip()
        except Exception:
            text = ""
        return text or "[stopped] step limit reached"
