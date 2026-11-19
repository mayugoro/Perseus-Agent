#!/usr/bin/env python3
"""Perseus — AI agent Termux-native (provider API, tanpa model lokal)."""
from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import os
import select
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core import config as cfgmod
from core import queue as qmod
from core import session as sess
from core import skills
from core.agent import Agent
from core.llm import LLM

C = {"b": "\033[1m", "c": "\033[36m", "y": "\033[33m", "r": "\033[31m", "d": "\033[2m", "0": "\033[0m"}

SLASH = [
    ("/help", "help"), ("/tools", "list tools"), ("/new", "reset conversation"),
    ("/mode", "ask | auto | read-only"), ("/model", "list / pick model"),
    ("/reasoning", "default | low | medium | high"), ("/think", "toggle thinking block"),
    ("/yolo", "disable risky-tool confirmation"), ("/learn", "auto-learn to memory"),
    ("/curator", "auto-skill after complex tasks"),
    ("/memory", "show memory & profile"), ("/forget", "delete memory by id"),
    ("/queue", "task queue"), ("/agents", "parallel subagents"),
    ("/steps", "tool step limit"), ("/copy", "copy last reply to clipboard"),
    ("/usage", "token & session duration"),
    ("/sessions", "list / search sessions"), ("/resume", "resume session"),
    ("/title", "set session title"), ("/session", "active session info"),
    ("/exit", "exit"),
]

STATUS = {}


LOGO_ART = [
    ':::::::::::::::::::::::::::::::::',
    ':::::::::::::::::::::::::::::::::',
    ':::::::::::::::::::::::::::::::::',
    ':::::::::::::::$$$:::::::::::::::',
    '::::::::::::::-$$$#::::::::::::::',
    ':::::::::::::::$$$#:-$$$$$:::::::',
    ':::::::::::::::$$$$$$$$$:::::::::',
    ':::::::::::::::$$$$$$%:::::::::::',
    ':::::::::::::::$$$$*:::::::::::::',
    ':::::::::::::$$$$$$::::::::::::::',
    ':::::::::+$$$$%$$$$::-$$$$$::::::',
    '::::::::$$$$*::$$$$:#$$$$$$::::::',
    ':::::::$$$:::::$$$$%$$$$:::::::::',
    ':::::::::::::::$$$$$$$$::::::::::',
    ':::::::::::::::*$$$$:::::::::::::',
    ':::::::::::::::$$$$::::::::::::::',
    '::::::::::::::$$$$$::::::::::::::',
    '::::::::::::=$$$$$$::::::::::::::',
    ':::::::::::$$$$-$$$::::::::::::::',
    '::::::::::$$$::-$$$::::::::::::::',
    ':::::::::::::::+$$$::::::::::::::',
    ':::::::::::::::*$$$::::::::::::::',
    ':::::::::::::::*$$$::::::::::::::',
    ':::::::::::::::$$$$::::::::::::::',
    ':::::::::::::::$$$$::::::::::::::',
    ':::::::::::::::$$$%::::::::::::::',
    ':::::::::::::::$$$#::::::::::::::',
    '::::::::::::::::--:::::::::::::::',
    ':::::::::::::::::::::::::::::::::',
    ':::::::::::::::::::::::::::::::::',
    ':::::::::::::::::::::::::::::::::',
    ':::::::::::::::::::::::::::::::::',
]

BANNER = r"""
 ██████╗ ███████╗██████╗ ███████╗███████╗██╗   ██╗███████╗
 ██╔══██╗██╔════╝██╔══██╗██╔════╝██╔════╝██║   ██║██╔════╝
 ██████╔╝█████╗  ██████╔╝███████╗█████╗  ██║   ██║███████╗
 ██╔═══╝ ██╔══╝  ██╔══██╗╚════██║██╔══╝  ██║   ██║╚════██║
 ██║     ███████╗██║  ██║███████║███████╗╚██████╔╝███████║
 ╚═╝     ╚══════╝╚═╝  ╚═╝╚══════╝╚══════╝ ╚═════╝ ╚══════╝
"""


def _clip(s: str, w: int) -> str:
    s = str(s)
    return s if len(s) <= w else s[: w - 1] + "…"


TOOLS_SHORT = [
    "Shell", "File · read/write/patch/search", "HTTP fetch", "Python exec",
    "Memory + FTS5", "Android: list/apps/info", "Android: install/uninstall/launch",
    "Android: logcat & log", "Parallel subagents", "Auto skill curator",
    "SQLite sessions + resume", "Task queue",
]


def banner(cfg: dict) -> None:
    import shutil
    cols = shutil.get_terminal_size((80, 24)).columns
    logo_w = max(len(l) for l in LOGO_ART)
    left_w = logo_w + 2
    right_w = max(0, cols - left_w - 2)
    right = []
    right += TOOLS_SHORT
    try:
        right += [n for n, _ in skills.list_skills()]
    except Exception:
        pass
    right = right[: len(LOGO_ART)]
    for i in range(len(LOGO_ART)):
        lt = " " + LOGO_ART[i]
        rt = "• " + right[i] if i < len(right) else ""
        rt = _clip(rt, right_w)
        print("\033[36m" + lt.ljust(left_w) + rt + "\033[0m")
    model = str(cfg.get("model", "-")).split("/")[-1]
    mode = cfg.get("permission", "ask")
    if cfg.get("yolo"):
        mode += " · YOLO"
    if cfg.get("reasoning_effort"):
        mode += " · think:" + cfg["reasoning_effort"]
    print(f"  {C['b']}Perseus{C['0']} · model {model} · provider "
          f"{_clip(cfg.get('base_url','-'),40)} · mode {mode}")
    print(f"  workspace {_clip(cfg.get('workspace','-'),44)} · skills {_skills_names(cfg)}\n")


def _skills_names(cfg: dict) -> str:
    try:
        sk = skills.list_skills()
    except Exception:
        sk = []
    if not sk:
        return "0 skill"
    names = [n for n, _ in sk]
    return f"{len(sk)} skill: " + ", ".join(names[:4]) + ("…" if len(names) > 4 else "")


def welcome() -> None:
    print("Welcome to Perseus! Type your message or /help for commands.")
    print("✦ Tip: /usage shows token usage, context, and session duration.\n")


REASONING_OPTS = [
    ("auto", ""), ("low", "low"), ("medium", "medium"), ("high", "high"),
    ("max", "max"), ("ultra", "ultra"), ("disable reasoning", "none"),
    ("cancel", None),
]


def pick_reasoning(current: str = "") -> str | None:
    """Tampilkan pilihan vertikal; return value baru, None = batal/pertahankan."""
    print("Reasoning:")
    for i, (label, _) in enumerate(REASONING_OPTS, 1):
        mark = f"{C['c']}❯{C['0']} " if (label == "auto" and not current) or label == current else "  "
        print(f"{mark}{i}. {label}")
    raw = input("Pick reasoning number [Enter=keep]: ").strip()
    if not raw:
        return None
    if raw.isdigit() and 1 <= int(raw) <= len(REASONING_OPTS):
        return REASONING_OPTS[int(raw) - 1][1]
    low = raw.lower()
    for label, val in REASONING_OPTS:
        if low == label:
            return val
    print("(invalid, keeping current)")
    return None


def est_tokens(agent: Agent) -> int:
    chars = sum(len(str(m.get("content") or "")) for m in agent.messages)
    return max(0, chars // 4)


def status_line() -> str:
    agent = STATUS.get("agent")
    cfg = STATUS.get("cfg", {})
    if not agent:
        return ""
    limit = int(cfg.get("context_length") or getattr(agent, "context_length", 128000) or 128000)
    tok = est_tokens(agent)
    ratio = min(100.0, tok * 100.0 / max(1, limit))
    pct_s = f"{ratio:.1f}%" if ratio < 1 else f"{int(ratio)}%"
    fill = max(1 if tok else 0, min(10, int(ratio // 10)))
    bar = "█" * fill + "░" * (10 - fill)
    dur = int(time.time() - STATUS.get("start", time.time()))
    model = str(agent.llm.model).split("/")[-1]
    last = agent.last_elapsed
    yolo = " · YOLO" if cfg.get("yolo") else ""
    return (f" ☤ {model}{yolo} · ctx {pct_s} [{bar}] {tok}/{limit//1000}k"
            f" · {last:.0f}s · ⏲ {dur}s    / commands · @ files · ! shell")


def cmd_usage(agent: Agent, cfg: dict) -> None:
    st = sess.stats(agent.session_id) if agent.session_id else None
    tok = est_tokens(agent)
    limit = int(cfg.get("context_length") or getattr(agent, "context_length", 128000) or 128000)
    dur = int(time.time() - STATUS.get("start", time.time()))
    print(f"model     : {agent.llm.model}")
    print(f"provider  : {cfg.get('base_url')}")
    if st:
        print(f"session   : {st['id']} ({st['title'] or '-'})")
        print(f"turns     : {st['turns']} · messages: {st['total']}")
    print(f"context   : ~{tok} tokens / {limit} ({min(100, tok*100//max(1,limit))}%)")
    print(f"durasi    : {dur}s · respons terakhir {agent.last_elapsed:.1f}s")
    print(f"reasoning : {cfg.get('reasoning_effort') or 'default'} · steps: "
          f"{'unlimited' if agent.max_steps <= 0 else agent.max_steps}")


def build_prompt(get_status=None):
    """PromptSession dengan completion; None kalau bukan TTY/tanpa prompt_toolkit."""
    if not sys.stdin.isatty():
        return None
    try:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.completion import Completer, Completion
        from prompt_toolkit.history import FileHistory

        class SlashCompleter(Completer):
            def get_completions(self, document, complete_event):
                text = document.text_before_cursor
                if not text.startswith("/"):
                    return
                parts = text.split()
                if len(parts) <= 1 and not text.endswith(" "):
                    prefix = parts[0] if parts else ""
                    for cmd, desc in SLASH:
                        if cmd.startswith(prefix):
                            yield Completion(cmd, start_position=-len(prefix),
                                             display_meta=desc)
                    return
                opts = {
                    "/mode": ["ask", "auto", "read-only"],
                    "/reasoning": ["default", "low", "medium", "high"],
                    "/agents": ["on", "off", "max", "permission"],
                    "/queue": ["run", "clear", "rm"],
                }.get(parts[0], [])
                if opts:
                    prefix = parts[-1] if not text.endswith(" ") else ""
                    for o in opts:
                        if o.startswith(prefix):
                            yield Completion(o, start_position=-len(prefix))

        hist = Path.home() / ".perseus" / "history"
        hist.parent.mkdir(parents=True, exist_ok=True)
        from prompt_toolkit.formatted_text import ANSI
        return PromptSession(ANSI("\033[97m❯\033[0m "), completer=SlashCompleter(),
                             complete_while_typing=True,
                             history=FileHistory(str(hist)))
    except Exception as e:
        globals()["_PT_ERROR"] = f"{type(e).__name__}: {e}"
        return None


def setup_readline() -> bool:
    """Fallback completion via GNU readline (Tab)."""
    try:
        import readline

        def completer(text, state):
            buf = readline.get_line_buffer()
            if not buf.startswith("/"):
                return None
            parts = buf.split()
            if len(parts) <= 1:
                opts = [c for c, _ in SLASH if c.startswith(text)]
            else:
                opts = {
                    "/mode": ["ask", "auto", "read-only"],
                    "/reasoning": ["default", "low", "medium", "high"],
                    "/agents": ["on", "off", "max", "permission"],
                    "/queue": ["run", "clear", "rm"],
                }.get(parts[0], [])
                opts = [o for o in opts if o.startswith(text)]
            return opts[state] if state < len(opts) else None

        readline.set_completer(completer)
        readline.set_completer_delims(" \t\n")
        readline.parse_and_bind("tab: complete")
        return True
    except Exception:
        return False


def divider() -> None:
    import shutil
    w = max(30, min(64, shutil.get_terminal_size((64, 20)).columns - 2))
    print(f"\033[36m{'─' * w}\033[0m")


def sessions_table(rows: list) -> None:
    if not rows:
        print("(no sessions yet)")
        return
    tw = min(24, max(8, max(len(r["title"] or "(tanpa judul)") for r in rows)))
    print(f"{'#':>2} | {'title':<{tw}} | {'last':<9} | first message")
    for i, r in enumerate(rows, 1):
        title = (r["title"] or "(tanpa judul)")[:tw]
        prev = (r["preview"] or "").replace("\n", " ")[:40]
        print(f"{i:>2} | {title:<{tw}} | {sess.rel_time(r['updated']):<9} | {prev}")
    print("\nOpen: perseus sessions <id|title> · Search: perseus sessions search <word>")


def show_history(msgs: list, limit: int = 6) -> None:
    tail = [m for m in msgs if (m.get("content") or "").strip()][-limit:]
    if not tail:
        return
    divider()
    # gabung baris berurutan dengan role sama (hasil multi-step tool)
    merged = []
    for m in tail:
        text = str(m.get("content", "")).strip().replace("\n", " ")
        role = "you" if m.get("role") == "user" else "perseus"
        if merged and merged[-1][0] == role:
            prev = merged[-1][1]
            merged[-1] = (role, (prev + " · " + text)[:300])
        else:
            merged.append((role, text[:300]))
    for role, text in merged:
        if role == "you":
            print(f"  you    : {text}")
        else:
            print(f"\033[36m  perseus: {text}\033[0m")
    divider()
    print()


def run_show(agent: Agent, text: str, ps=None) -> str:
    try:
        out = agent.run(text, stream=True)
    except KeyboardInterrupt:
        agent.abort.set()
        print("\n\033[33m[stopped]\033[0m")
        return ""
    if not agent.last_streamed:
        print(out)
    return out
def show_tools(agent: Agent) -> None:
    for t in agent.registry.tools.values():
        flag = "!" if t.danger else " "
        print(f" {flag} {t.name:<20} {t.description[:70]}")


def _providers(cfg: dict) -> list[dict]:
    ps = cfg.get("providers")
    return ps if isinstance(ps, list) else []


def _save_provider(cfg: dict, entry: dict) -> None:
    ps = [p for p in _providers(cfg) if p.get("display_name") != entry.get("display_name")]
    ps.append(entry)
    cfg["providers"] = ps
    cfg["active_provider"] = entry.get("display_name", "")


def wizard(cfg: dict) -> dict:
    print(f"{C['b']}Perseus setup{C['0']} — provider + model\n")
    providers = _providers(cfg)
    if not providers and cfg.get("base_url"):
        try:
            from urllib.parse import urlparse
            host = urlparse(cfg["base_url"]).netloc
        except Exception:
            host = ""
        legacy = {
            "display_name": cfg.get("display_name") or host or "default",
            "base_url": cfg["base_url"],
            "api_key": cfg.get("api_key", ""),
            "model": cfg.get("model", ""),
            "context_length": cfg.get("context_length"),
            "reasoning_effort": cfg.get("reasoning_effort", ""),
        }
        cfg["providers"] = [legacy]
        cfg["active_provider"] = legacy["display_name"]
        providers = _providers(cfg)
    entry = None
    if providers:
        print("Providers:")
        print("  1. + custom model")
        for i, p in enumerate(providers, 2):
            mark = f"{C['c']}❯{C['0']} " if p.get("display_name") == cfg.get("active_provider") else "  "
            print(f"{mark}{i}. {p.get('display_name') or p.get('base_url')}  {C['d']}{p.get('base_url','')}{C['0']}")
        print(f"  {len(providers)+2}. cancel")
        pick = input("Pick a number [Enter=cancel]: ").strip()
        if not pick or pick == str(len(providers) + 2):
            print("(cancelled)")
            return cfg
        if pick.isdigit() and 2 <= int(pick) <= len(providers) + 1:
            entry = dict(providers[int(pick) - 2])
            if not cfgmod.api_key({**cfg, **entry}):
                print("API key untuk provider ini belum ada.")
                key = getpass.getpass("API key   : ").strip()
                if key:
                    entry["api_key"] = key
        elif pick != "1":
            print("(invalid)")
            return cfg

    if entry is None:
        host = ""
        try:
            from urllib.parse import urlparse
            host = urlparse(cfg.get("base_url") or "https://…/v1").netloc
        except Exception:
            pass
        disp = input(f"Display name [{host or 'custom'}]: ").strip() or host or "custom"
        base = input(f"Base URL  [{cfg.get('base_url') or 'https://…/v1'}]: ").strip()
        if base:
            cfg["base_url"] = base.rstrip("/")
        print("API key disimpan lokal di ~/.perseus/config.json (0600).")
        print("Kosongkan kalau mau pakai env PERSEUS_API_KEY.")
        key = getpass.getpass("API key   : ").strip()
        if key:
            cfg["api_key"] = key
        entry = {"display_name": disp}

    if entry.get("base_url"):
        cfg["base_url"] = entry["base_url"]
    if entry.get("api_key"):
        cfg["api_key"] = entry["api_key"]
    cfg["display_name"] = entry.get("display_name", "")

    models = []
    if cfg.get("base_url"):
        try:
            models = LLM(cfg["base_url"], cfgmod.api_key(cfg), "").list_models()
        except Exception as e:
            print(f"(failed to fetch model list: {e})")

    if models:
        for i, mid in enumerate(models[:40], 1):
            mark = f"{C['c']}❯{C['0']} " if mid == cfg.get("model") else "  "
            print(f"{mark}{i}. {mid}")
        if len(models) > 40:
            print(f"   … {len(models)-40} model lain")
        choice = input("Pick a model number [Enter=keep]: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(models):
            cfg["model"] = models[int(choice) - 1]
        elif choice and not choice.startswith("/"):
            cfg["model"] = choice
    else:
        model = input(f"Model     [{cfg.get('model') or 'nama-model'}]: ").strip()
        if model:
            cfg["model"] = model

    try:
        c = LLM(cfg["base_url"], cfgmod.api_key(cfg), cfg["model"]).model_context()
        if c:
            cfg["context_length"] = c
    except Exception:
        pass

    val = pick_reasoning(cfg.get("reasoning_effort", ""))
    if val is not None:
        cfg["reasoning_effort"] = val

    mopts = ["ask", "auto", "read-only"]
    print("Permission: 1. ask  2. auto  3. read-only")
    mode = input(f"Pick permission number [Enter={cfg.get('permission','ask')}]: ").strip()
    if mode.isdigit() and 1 <= int(mode) <= 3:
        cfg["permission"] = mopts[int(mode) - 1]
    elif mode in mopts:
        cfg["permission"] = mode

    entry.update({
        "base_url": cfg.get("base_url", ""),
        "api_key": cfg.get("api_key", ""),
        "model": cfg.get("model", ""),
        "context_length": cfg.get("context_length"),
        "reasoning_effort": cfg.get("reasoning_effort", ""),
    })
    _save_provider(cfg, entry)
    cfgmod.save(cfg)
    print(f"\nSaved. provider={entry.get('display_name')} · model={cfg.get('model')} · mode={cfg.get('permission')}\n")
    return cfg


def ready(cfg: dict) -> bool:
    return bool(cfg.get("base_url") and cfg.get("model") and cfgmod.api_key(cfg))


def make_confirm():
    def confirm(name: str, args: dict) -> bool:
        print(f"\n{C['y']}⚠ risky tool: {name}{C['0']}")
        for k, v in args.items():
            s = str(v)
            if k in ("content", "new", "old") and len(s) > 300:
                s = s[:300] + f"… ({len(s)} chars)"
            print(f"   {k}: {s}")
        try:
            ans = input("Continue? [y/N] ").strip().lower()
        except EOFError:
            return False
        return ans in ("y", "ya", "yes")
    return confirm


def main() -> int:
    ap = argparse.ArgumentParser(prog="perseus")
    ap.add_argument("-p", "--prompt", help="run one command then exit")
    ap.add_argument("--mode", choices=["ask", "auto", "read-only"])
    ap.add_argument("--model")
    ap.add_argument("--workspace")
    ap.add_argument("command", nargs="?", choices=["model", "setup", "sessions", "resume"],
                    help="model | setup | sessions | resume")
    ap.add_argument("rest", nargs="*", help="argumen untuk command")
    ap.add_argument("-c", "-resume", "--resume", dest="resume", metavar="SESI",
                    help="resume session (id or id prefix)")
    ap.add_argument("--init", action="store_true", help="buat config default")
    ap.add_argument("--show-config", action="store_true")
    a = ap.parse_args()

    cfg = cfgmod.load()

    if a.command == "sessions":
        words = a.rest
        sub = words[0].lower() if words else ""
        q = " ".join(words[1:]).strip()

        if not words or sub in ("list", "ls"):
            sessions_table(sess.list_sessions())
            return 0

        if sub == "search":
            if not q:
                print("format: perseus sessions search <word>")
                return 2
            rows = sess.search(q)
            if not rows:
                print("(tidak ada hasil)")
            seen = set()
            for r in rows:
                if r["id"] in seen:
                    continue
                seen.add(r["id"])
                print(f"- {sess.fmt_time(r['updated'])} · {r['title'] or r['id']}")
                print(f"  {r['snippet']}")
            return 0

        # selain list/search: anggap id/title -> buka sesi
        sid = sess.resolve(" ".join(words).strip())
        if sid:
            a.resume = sid
        else:
            print(f"Sesi '{' '.join(words)}' tidak ditemukan. "
                  f"Lihat: perseus sessions list · Cari: perseus sessions search <kata>")
            return 2

    if a.command == "resume":
        a.resume = " ".join(a.rest).strip() or None
    if a.mode:
        cfg["permission"] = a.mode
    if a.model:
        cfg["model"] = a.model
    if a.workspace:
        cfg["workspace"] = str(Path(a.workspace).expanduser().resolve())
        Path(cfg["workspace"]).mkdir(parents=True, exist_ok=True)
    if a.command in ("model", "setup"):
        cfg = wizard(cfg)
        return 0

    if a.init:
        wizard(cfg)
        return 0
    elif not ready(cfg) and not a.prompt and not a.show_config:
        print("Provider not set. Run setup first.\n")
        cfg = wizard(cfg)

    if a.show_config:
        safe = dict(cfg)
        safe.pop("api_key", None)
        print(json.dumps(safe, indent=2))
        print("api key:", "ADA" if cfgmod.api_key(cfg) else "BELUM")
        if not a.prompt:
            return 0

    if not ready(cfg):
        print(f"{C['r']}Provider incomplete.{C['0']} Run: python3 perseus.py --init")
        return 2

    agent = Agent(cfg, confirm=make_confirm())

    resumed = False
    if a.resume:
        sid = sess.resolve(a.resume)
        if not sid:
            print(f"{C['r']}Sesi '{a.resume}' tidak ditemukan.{C['0']}")
            return 2
        msgs = sess.load(sid)
        st = sess.stats(sid)
        agent.session_id = sid
        agent.messages = msgs
        print(f"resumed session {sid} · {st['turns']} turn · {st['total']} messages · "
              f"{sess.fmt_time(st['updated'])}")
        show_history(msgs)
        resumed = True

    if a.prompt:
        run_show(agent, a.prompt)
        return 0

    if not resumed:
        banner(cfg)
        welcome()
    STATUS.update(agent=agent, cfg=cfg, start=time.time())
    _PT_ERROR = "bukan TTY" if not sys.stdin.isatty() else ""
    ps = build_prompt(status_line)
    if ps:
        pass
    else:
        err = globals().get("_PT_ERROR") or _PT_ERROR or "prompt_toolkit tidak tersedia"
        if setup_readline():
            print(f"  completion: tab/readline (prompt_toolkit gagal: {err})")
        else:
            print(f"  completion: off ({err})"
              f" — ketik / lalu Enter untuk daftar\n")

    while True:
        try:
            if ps:
                print(f"\033[2m{status_line()}\033[0m")
                line = ps.prompt().strip()
            else:
                print(f"\033[2m{status_line()}\033[0m")
                line = input(f"{C['c']}❯{C['0']} ").strip()
        except KeyboardInterrupt:
            print(f"\n{C['c']}Good bye{C['0']}")
            break
        except EOFError:
            print()
            break
        if not line:
            continue
        if line in ("/exit", "/quit", "exit", "quit"):
            st = sess.stats(agent.session_id) if agent.session_id else None
            if st:
                print(f"\nsession : {st['id']}")
                print(f"title   : {st['title'] or '-'}")
                print(f"time    : {sess.fmt_time(st['created'])} → {sess.fmt_time(st['updated'])}")
                print(f"content : {st['turns']} turns · {st['total']} messages · model {st['model'] or '-'}")
                print(f"db      : {sess.DB}")
                print(f"resume  : perseus -c {st['id']}")
            break
        if line == "/copy":
            last = ""
            for m in reversed(agent.messages):
                if m.get("role") == "assistant" and m.get("content"):
                    last = m["content"]
                    break
            if not last:
                print("(no reply to copy)")
                continue
            helper = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "dist", "cli.js")
            ok = False
            if os.path.exists(helper):
                r = subprocess.run(["node", helper, "copy"], input=last, text=True)
                ok = r.returncode == 0
            if not ok and shutil.which("termux-clipboard-set"):
                r = subprocess.run(["termux-clipboard-set"], input=last, text=True)
                ok = r.returncode == 0
            print("(copied)" if ok else "(clipboard helper not available — install nodejs / termux-api)")
            continue
        if line == "/usage":
            cmd_usage(agent, cfg)
            continue
        if line.startswith("!"):
            cmd = line[1:].strip()
            if not cmd:
                continue
            if agent.registry.confirm_needed("shell", {"command": cmd}) and agent.permission == "ask":
                ok = make_confirm()("shell", {"command": cmd})
                if not ok:
                    continue
            print(agent.registry.call("shell", {"command": cmd}))
            continue
        if line.startswith("@"):
            target = line[1:].strip()
            try:
                pth = agent.registry.resolve(target)
                content = pth.read_text(errors="replace")[:40000]
                line = f"Isi file {target}:\n```\n{content}\n```\n\nApa yang perlu dilakukan?"
                print(f"\033[2m[file] {target} ({len(content)} chars)\033[0m")
                divider()
            except Exception as e:
                print(f"(gagal baca file: {e})")
                continue
        if line == "/stop":
            print("(no task running)")
            continue
        if line == "/":
            for cmd, desc in SLASH:
                print(f"  {cmd:<12} {desc}")
            print()
            continue
        if line == "/help":
            print("/tools  list tools\n/new    reset conversation\n/mode ask|auto|read-only"
                  "\n/model [id]  change/list model\n/think  show/hide reasoning\n/queue [task|run|rm N|clear]  task queue\n/agents [on|off|max N]  parallel subagents\n/exit   exit")
            continue
        if line == "/tools":
            show_tools(agent)
            continue
        if line == "/new":
            agent.reset()
            agent.session_id = sess.new_session(cfg)
            STATUS["start"] = time.time()
            banner(cfg)
            welcome()
            continue
        if line.startswith("/mode "):
            m = line.split(None, 1)[1].strip()
            if m in ("ask", "auto", "read-only"):
                agent.permission = m
                cfg["permission"] = m
                cfgmod.save(cfg)
                print(f"mode={m}")
            else:
                print("mode: ask | auto | read-only")
            continue
        if line == "/model" or line.startswith("/model "):
            print(f"provider : {cfg['base_url']}")
            print(f"model    : {agent.llm.model}")
            if line == "/model":
                try:
                    models = agent.llm.list_models()
                except Exception as e:
                    print(f"(failed to fetch model list: {e})")
                    models = []
                if models:
                    for i, mid in enumerate(models[:40], 1):
                        mark = f"{C['c']}❯{C['0']} " if mid == agent.llm.model else "  "
                        print(f"{mark}{i}. {mid}")
                    if len(models) > 40:
                        print(f"   … {len(models)-40} model lain")
                choice = input("Pick a number / type a model id [Enter=cancel]: ").strip()
                if not choice or choice.startswith("/"):
                    print("(batal)")
                    continue
                if not models and choice.isdigit():
                    print("(model list unavailable — type a model id)")
                    continue
                if choice.isdigit() and 1 <= int(choice) <= len(models):
                    m = models[int(choice) - 1]
                else:
                    m = choice
            else:
                m = line.split(None, 1)[1].strip()
            if line == "/model" and m:
                val = pick_reasoning(cfg.get("reasoning_effort", ""))
                if val is not None:
                    agent.llm.reasoning_effort = val
                    cfg["reasoning_effort"] = val
                    cfgmod.save(cfg)
                    print(f"reasoning={val or 'auto'}")
            agent.llm.model = m
            cfg["model"] = m
            try:
                c = agent.llm.model_context()
                if c:
                    agent.context_length = c
                    cfg["context_length"] = c
            except Exception:
                pass
            cfgmod.save(cfg)
            print(f"model={m} · ctx {cfg.get('context_length', '?')}")
            continue
        if line.startswith("/reasoning"):
            v = line.split(None, 1)[1].strip().lower() if " " in line else ""
            aliases = {"default": "", "auto": "", "disable": "none",
                       "disable reasoning": "none", "none": "none",
                       "low": "low", "medium": "medium", "high": "high",
                       "max": "max", "ultra": "ultra"}
            if v in aliases:
                val = aliases[v]
                agent.llm.reasoning_effort = val
                cfg["reasoning_effort"] = val
                cfgmod.save(cfg)
                print(f"reasoning={v}")
            else:
                print(f"reasoning sekarang: {cfg.get('reasoning_effort') or 'default'}")
                print("set: /reasoning auto|low|medium|high|max|ultra|none")
            continue
        if line == "/steps" or line.startswith("/steps "):
            if " " in line:
                try:
                    v = max(0, min(500, int(line.split()[1])))
                    agent.max_steps = v
                    cfg["max_steps"] = v
                    cfgmod.save(cfg)
                    print(f"max_steps={'unlimited' if v == 0 else v}")
                except ValueError:
                    print("format: /steps N (1-500)")
            else:
                print(f"max_steps={'unlimited' if agent.max_steps <= 0 else agent.max_steps}")
            continue
        if line == "/title" or line.startswith("/title "):
            if " " in line:
                t = line.split(None, 1)[1].strip()
                sess.set_title(agent.session_id, t)
                print(f"title={t}")
            else:
                st = sess.stats(agent.session_id) if agent.session_id else None
                print(f"title: {st['title'] if st and st['title'] else '(belum ada)'}")
            continue
        if line == "/session":
            print(f"id: {agent.session_id}")
            print(f"pesan: {len(agent.messages)}")
            continue
        if line.startswith("/sessions "):
            q = line[10:].strip()
            rows = sess.search(q)
            if not rows:
                print("(tidak ada hasil)")
            else:
                for r in rows:
                    print(f"- {sess.fmt_time(r['updated'])} · {r['id']}\n  {r['snippet']}")
            continue
        if line == "/sessions" or line.startswith("/resume"):
            if line.startswith("/resume"):
                arg = line.split(None, 1)[1].strip() if " " in line else ""
                if arg.isdigit():
                    rows = sess.list_sessions()
                    if not (1 <= int(arg) <= len(rows)):
                        print("number not found (lihat /sessions)")
                        continue
                    sid = rows[int(arg) - 1]["id"]
                else:
                    sid = sess.resolve(arg) if arg else None
                    if not sid:
                        print("sesi tidak ditemukan (id, awalan id, atau title)")
                        continue
                msgs = sess.load(sid)
                if not msgs:
                    print("(sesi kosong)")
                    continue
                st = sess.stats(sid)
                agent.messages = msgs
                agent.session_id = sid
                print(f"resume: {st['title'] or sid} · {sess.fmt_time(st['updated'])} · "
                      f"{st['turns']} turn · {len(msgs)} pesan")
                show_history(msgs)
                continue
            sessions_table(sess.list_sessions())
            continue
        if line == "/memory" or line.startswith("/memory "):
            import core.memory as mem
            c = mem._conn()
            data = c.execute("SELECT id,kind,text FROM notes ORDER BY id DESC LIMIT 20").fetchall()
            c.close()
            for mid, kind, text in data:
                print(f"#{mid} [{kind}] {text[:140]}")
            print("\nHapus: /forget <id>")
            continue
        if line.startswith("/forget"):
            arg = line.split(None, 1)[1].strip() if " " in line else ""
            import core.memory as mem
            try:
                ok = mem.delete(int(arg))
                print("deleted" if ok else "id not found")
            except ValueError:
                print("format: /forget <id>")
            continue
        if line == "/curator" or line.startswith("/curator "):
            arg = line.split(None, 1)[1].strip().lower() if " " in line else ""
            on = (not cfg.get("curator", True)) if arg not in ("on", "off") else (arg == "on")
            cfg["curator"] = on
            agent.curator = on
            cfgmod.save(cfg)
            print(f"curator={'on' if on else 'off'}")
            continue
        if line == "/yolo" or line.startswith("/yolo "):
            arg = line.split(None, 1)[1].strip().lower() if " " in line else ""
            on = (not cfg.get("yolo", False)) if arg not in ("on", "off") else (arg == "on")
            if on:
                cfg["_prev_permission"] = agent.permission if agent.permission != "auto" else "ask"
                cfg["yolo"] = True
                agent.permission = "auto"
                print("YOLO on — risky tools run without confirmation. /yolo off to restore.")
            else:
                cfg["yolo"] = False
                agent.permission = cfg.pop("_prev_permission", "ask")
                print(f"YOLO off — permission mode restored to {agent.permission}")
            cfgmod.save(cfg)
            continue
        if line == "/learn":
            agent.auto_learn = not agent.auto_learn
            cfg["auto_learn"] = agent.auto_learn
            cfgmod.save(cfg)
            print(f"learn={'on' if agent.auto_learn else 'off'}")
            continue
        if line == "/think":
            agent.show_reasoning = not agent.show_reasoning
            cfg["show_reasoning"] = agent.show_reasoning
            cfgmod.save(cfg)
            print(f"think={'on' if agent.show_reasoning else 'off'}")
            continue
        if line == "/agents" or line.startswith("/agents "):
            sub = cfg.setdefault("subagents", {"enabled": True, "max_parallel": 3, "permission": "auto"})
            rest = line[7:].strip()
            if not rest:
                print(f"subagents : {'ON' if sub.get('enabled', True) else 'OFF'}")
                print(f"max paralel: {sub.get('max_parallel', 3)}")
                print(f"permission : {sub.get('permission', 'auto')}")
                print("\n/agents on|off · /agents max N · /agents permission auto|read-only")
            elif rest in ("on", "off"):
                sub["enabled"] = rest == "on"
                cfgmod.save(cfg)
                print(f"subagents={rest}")
            elif rest.startswith("max "):
                try:
                    sub["max_parallel"] = max(1, min(8, int(rest.split()[1])))
                    cfgmod.save(cfg)
                    print(f"max paralel={sub['max_parallel']}")
                except (IndexError, ValueError):
                    print("format: /agents max N (1-8)")
            elif rest.startswith("permission "):
                v = rest.split(None, 1)[1].strip()
                if v in ("auto", "read-only"):
                    sub["permission"] = v
                    cfgmod.save(cfg)
                    print(f"permission={v}")
                else:
                    print("pilihan: auto | read-only")
            else:
                print("perintah: /agents on|off · /agents max N · /agents permission auto|read-only")
            continue
        if line == "/queue" or line.startswith("/queue "):
            rest = line[6:].strip()
            if not rest:
                qs = qmod.items()
                if not qs:
                    print("(queue empty)")
                else:
                    for i, q in enumerate(qs, 1):
                        print(f"{i}. [{q.get('created','')}] {q['text'][:160]}")
                    print("\n/queue run  run all · /queue rm N · /queue clear")
            elif rest == "run":
                qs = qmod.items()
                if not qs:
                    print("(queue empty)")
                else:
                    for i, q in enumerate(qs, 1):
                        print(f"\n{C['c']}[queue {i}/{len(qs)}]{C['0']} {q['text']}")
                        try:
                            run_show(agent, q["text"], ps)
                            divider()
                        except KeyboardInterrupt:
                            print("(cancelled, remaining queue kept)")
                            break
                        qmod.remove(1)
                    print(f"\nqueue done, remaining {len(qmod.items())}")
            elif rest == "clear":
                n = qmod.clear()
                print(f"{n} tugas deleted")
            elif rest.startswith("rm "):
                try:
                    ok = qmod.remove(int(rest.split()[1]))
                    print("deleted" if ok else "number not found")
                except (IndexError, ValueError):
                    print("format: /queue rm N")
            else:
                n = qmod.add(rest)
                print(f"added to queue (#{n})")
            continue
        try:
            run_show(agent, line, ps)
            divider()
        except KeyboardInterrupt:
            print("\n(dibatalkan)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nGood bye")
        raise SystemExit(0)
