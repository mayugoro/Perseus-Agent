#!/usr/bin/env python3
"""Perseus — AI agent Termux-native (provider API, tanpa model lokal)."""
from __future__ import annotations

import argparse
import getpass
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core import config as cfgmod
from core import queue as qmod
from core import session as sess
from core.agent import Agent
from core.llm import LLM

C = {"b": "\033[1m", "c": "\033[36m", "y": "\033[33m", "r": "\033[31m", "0": "\033[0m"}

SLASH = [
    ("/help", "bantuan"), ("/tools", "daftar tool"), ("/new", "reset percakapan"),
    ("/mode", "ask | auto | read-only"), ("/model", "daftar / pilih model"),
    ("/reasoning", "default | low | medium | high"), ("/think", "toggle blok thinking"),
    ("/learn", "toggle auto-learn ke memory"), ("/queue", "antrean tugas"),
    ("/agents", "subagent paralel"), ("/steps", "batas langkah tool"),
    ("/usage", "token & durasi sesi"), ("/sessions", "daftar / cari sesi"), ("/resume", "lanjutkan sesi"),
    ("/title", "atur judul sesi"),
    ("/session", "info sesi aktif"), ("/exit", "keluar"),
]

BANNER = r"""
 ██████╗ ███████╗██████╗ ███████╗███████╗██╗   ██╗███████╗
 ██╔══██╗██╔════╝██╔══██╗██╔════╝██╔════╝██║   ██║██╔════╝
 ██████╔╝█████╗  ██████╔╝███████╗█████╗  ██║   ██║███████╗
 ██╔═══╝ ██╔══╝  ██╔══██╗╚════██║██╔══╝  ██║   ██║╚════██║
 ██║     ███████╗██║  ██║███████║███████╗╚██████╔╝███████║
 ╚═╝     ╚══════╝╚═╝  ╚═╝╚══════╝╚══════╝ ╚═════╝ ╚══════╝
"""


def banner(cfg: dict) -> None:
    print(f"{C['c']}{BANNER}{C['0']}")
    print(f"  {C['b']}Perseus{C['0']} · Termux AI Agent")
    print(f"  model     : {cfg['model']}")
    print(f"  provider  : {cfg['base_url']}")
    print(f"  mode      : {cfg['permission']} · reasoning: {cfg.get('reasoning_effort') or 'default'}")
    print(f"  workspace : {cfg['workspace']}")
    print(f"  {C['y']}/help{C['0']} bantuan · {C['y']}/tools{C['0']} daftar tool · "
          f"{C['y']}/exit{C['0']} keluar\n")


STATUS = {}


def est_tokens(agent: Agent) -> int:
    chars = sum(len(str(m.get("content") or "")) for m in agent.messages)
    return max(0, chars // 4)


def status_line() -> str:
    agent = STATUS.get("agent")
    cfg = STATUS.get("cfg", {})
    if not agent:
        return ""
    limit = int(cfg.get("context_length", 128000))
    tok = est_tokens(agent)
    pct = min(100, int(tok * 100 / max(1, limit)))
    fill = min(10, pct // 10)
    bar = "█" * fill + "░" * (10 - fill)
    dur = int(time.time() - STATUS.get("start", time.time()))
    model = str(agent.llm.model).split("/")[-1]
    last = agent.last_elapsed
    return (f" ☤ {model} · ctx {pct}% [{bar}] {tok//1000}k/{limit//1000}k"
            f" · {last:.0f}s · ⏲ {dur}s    / commands · @ files · ! shell")


def welcome() -> None:
    print("Welcome to Perseus! Type your message or /help for commands.")
    print("✦ Tip: /usage shows token usage, context, and session duration.\n")


def cmd_usage(agent: Agent, cfg: dict) -> None:
    st = sess.stats(agent.session_id) if agent.session_id else None
    tok = est_tokens(agent)
    limit = int(cfg.get("context_length", 128000))
    dur = int(time.time() - STATUS.get("start", time.time()))
    print(f"model     : {agent.llm.model}")
    print(f"provider  : {cfg.get('base_url')}")
    if st:
        print(f"session   : {st['id']} ({st['title'] or '-'})")
        print(f"turns     : {st['turns']} · pesan: {st['total']}")
    print(f"context   : ~{tok} token / {limit} ({min(100, tok*100//max(1,limit))}%)")
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
        return PromptSession(ANSI("\033[36m❯\033[0m "), completer=SlashCompleter(),
                             complete_while_typing=True,
                             bottom_toolbar=get_status,
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
        print("(belum ada sesi)")
        return
    tw = min(24, max(8, max(len(r["title"] or "(tanpa judul)") for r in rows)))
    print(f"{'#':>2} | {'title':<{tw}} | {'terakhir':<9} | obrolan pertama")
    for i, r in enumerate(rows, 1):
        title = (r["title"] or "(tanpa judul)")[:tw]
        prev = (r["preview"] or "").replace("\n", " ")[:40]
        print(f"{i:>2} | {title:<{tw}} | {sess.rel_time(r['updated']):<9} | {prev}")
    print("\nBuka: perseus sessions <id|title> · Cari: perseus sessions search <kata>")


def show_history(msgs: list, limit: int = 6) -> None:
    tail = [m for m in msgs if (m.get("content") or "").strip()][-limit:]
    if not tail:
        return
    divider()
    for m in tail:
        text = str(m.get("content", "")).strip().replace("\n", " ")
        if len(text) > 300:
            text = text[:300] + "…"
        if m.get("role") == "user":
            print(f"  kamu   : {text}")
        else:
            print(f"\033[36m  perseus: {text}\033[0m")
    divider()
    print()


def run_show(agent: Agent, text: str) -> str:
    out = agent.run(text)
    if not agent.last_streamed:
        print(out)
    return out


def show_tools(agent: Agent) -> None:
    for t in agent.registry.tools.values():
        flag = "!" if t.danger else " "
        print(f" {flag} {t.name:<20} {t.description[:70]}")


def wizard(cfg: dict) -> dict:
    print(f"{C['b']}Perseus setup{C['0']} — Base URL + API key, model diambil otomatis.\n")
    base = input(f"Base URL  [{cfg.get('base_url') or 'https://…/v1'}]: ").strip()
    if base:
        cfg["base_url"] = base.rstrip("/")

    print("API key disimpan lokal di ~/.perseus/config.json (0600).")
    print("Kosongkan kalau mau pakai env PERSEUS_API_KEY.")
    key = getpass.getpass("API key   : ").strip()
    if key:
        cfg["api_key"] = key

    models = []
    if cfg.get("base_url"):
        try:
            models = LLM(cfg["base_url"], cfgmod.api_key(cfg), "").list_models()
        except Exception as e:
            print(f"(gagal ambil daftar model: {e})")

    if models:
        for i, mid in enumerate(models[:40], 1):
            mark = " *" if mid == cfg.get("model") else "  "
            print(f"{mark}{i}. {mid}")
        if len(models) > 40:
            print(f"   … {len(models)-40} model lain")
        choice = input("Pilih nomor model [Enter=pertahankan]: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(models):
            cfg["model"] = models[int(choice) - 1]
        elif choice and not choice.startswith("/"):
            cfg["model"] = choice
    else:
        model = input(f"Model     [{cfg.get('model') or 'nama-model'}]: ").strip()
        if model:
            cfg["model"] = model

    r = input(f"Reasoning [default/low/medium/high, sekarang {cfg.get('reasoning_effort') or 'default'}]: ").strip().lower()
    if r in ("default", "low", "medium", "high"):
        cfg["reasoning_effort"] = "" if r == "default" else r

    mode = input(f"Mode izin [ask/auto/read-only, sekarang {cfg.get('permission','ask')}]: ").strip()
    if mode in ("ask", "auto", "read-only"):
        cfg["permission"] = mode
    cfgmod.save(cfg)
    print(f"\nTersimpan. Model={cfg.get('model')} · mode={cfg.get('permission')}\n")
    return cfg


def ready(cfg: dict) -> bool:
    return bool(cfg.get("base_url") and cfg.get("model") and cfgmod.api_key(cfg))


def make_confirm():
    def confirm(name: str, args: dict) -> bool:
        print(f"\n{C['y']}⚠ tool berisiko: {name}{C['0']}")
        for k, v in args.items():
            s = str(v)
            if k in ("content", "new", "old") and len(s) > 300:
                s = s[:300] + f"… ({len(s)} chars)"
            print(f"   {k}: {s}")
        try:
            ans = input("Lanjutkan? [y/N] ").strip().lower()
        except EOFError:
            return False
        return ans in ("y", "ya", "yes")
    return confirm


def main() -> int:
    ap = argparse.ArgumentParser(prog="perseus")
    ap.add_argument("-p", "--prompt", help="jalankan satu perintah lalu keluar")
    ap.add_argument("--mode", choices=["ask", "auto", "read-only"])
    ap.add_argument("--model")
    ap.add_argument("--workspace")
    ap.add_argument("command", nargs="?", choices=["model", "setup", "sessions", "resume"],
                    help="model | setup | sessions | resume")
    ap.add_argument("rest", nargs="*", help="argumen untuk command")
    ap.add_argument("-c", "-resume", "--resume", dest="resume", metavar="SESI",
                    help="lanjutkan sesi (id atau awalan id)")
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
                print("format: perseus sessions search <kata>")
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
        print("Provider belum diset. Jalankan setup dulu.\n")
        cfg = wizard(cfg)

    if a.show_config:
        safe = dict(cfg)
        safe.pop("api_key", None)
        print(json.dumps(safe, indent=2))
        print("api key:", "ADA" if cfgmod.api_key(cfg) else "BELUM")
        if not a.prompt:
            return 0

    if not ready(cfg):
        print(f"{C['r']}Provider belum lengkap.{C['0']} Jalankan: python3 perseus.py --init")
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
        print(f"resume sesi {sid} · {st['turns']} turn · {st['total']} pesan · "
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
        print(f"  completion: aktif — ketik / untuk daftar perintah\n")
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
                line = ps.prompt().strip()
            else:
                print(f"\033[2m{status_line()}\033[0m")
                line = input(f"{C['c']}❯{C['0']} ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line in ("/exit", "/quit", "exit", "quit"):
            st = sess.stats(agent.session_id) if agent.session_id else None
            if st:
                print(f"\nsession : {st['id']}")
                print(f"title   : {st['title'] or '-'}")
                print(f"waktu   : {sess.fmt_time(st['created'])} → {sess.fmt_time(st['updated'])}")
                print(f"isi     : {st['turns']} turn · {st['total']} pesan · model {st['model'] or '-'}")
                print(f"db      : {sess.DB}")
                print(f"resume  : perseus -c {st['id']}")
            break
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
        if line == "/":
            for cmd, desc in SLASH:
                print(f"  {cmd:<12} {desc}")
            print()
            continue
        if line == "/help":
            print("/tools  daftar tool\n/new    reset percakapan\n/mode ask|auto|read-only"
                  "\n/model [id]  ganti/daftar model\n/think  tampilkan/sembunyikan reasoning\n/queue [tugas|run|rm N|clear]  antrean tugas\n/agents [on|off|max N]  subagent paralel\n/exit   keluar")
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
                    print(f"(gagal ambil daftar model: {e})")
                    models = []
                if models:
                    for i, mid in enumerate(models[:40], 1):
                        mark = " *" if mid == agent.llm.model else "  "
                        print(f"{mark}{i}. {mid}")
                    if len(models) > 40:
                        print(f"   … {len(models)-40} model lain")
                choice = input("Pilih nomor / ketik model id [Enter=batal]: ").strip()
                if not choice or choice.startswith("/"):
                    print("(batal)")
                    continue
                if choice.isdigit() and 1 <= int(choice) <= len(models):
                    m = models[int(choice) - 1]
                else:
                    m = choice
            else:
                m = line.split(None, 1)[1].strip()
            if line == "/model" and m:
                r = input("Reasoning [default/low/medium/high] (Enter=pertahankan): ").strip().lower()
                if r in ("default", "low", "medium", "high"):
                    v = "" if r == "default" else r
                    agent.llm.reasoning_effort = v
                    cfg["reasoning_effort"] = v
                    cfgmod.save(cfg)
                    print(f"reasoning={r}")
            agent.llm.model = m
            cfg["model"] = m
            cfgmod.save(cfg)
            print(f"model={m}")
            continue
        if line.startswith("/reasoning"):
            v = line.split(None, 1)[1].strip().lower() if " " in line else ""
            if v in ("default", "low", "medium", "high"):
                val = "" if v == "default" else v
                agent.llm.reasoning_effort = val
                cfg["reasoning_effort"] = val
                cfgmod.save(cfg)
                print(f"reasoning={v}")
            else:
                print(f"reasoning sekarang: {cfg.get('reasoning_effort') or 'default'}")
                print("ubah: /reasoning default|low|medium|high")
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
                    print("format: /steps N (1-40)")
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
                        print("nomor tidak ada (lihat /sessions)")
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
                    print("(antrean kosong)")
                else:
                    for i, q in enumerate(qs, 1):
                        print(f"{i}. [{q.get('created','')}] {q['text'][:160]}")
                    print("\n/queue run  jalankan semua · /queue rm N · /queue clear")
            elif rest == "run":
                qs = qmod.items()
                if not qs:
                    print("(antrean kosong)")
                else:
                    for i, q in enumerate(qs, 1):
                        print(f"\n{C['c']}[queue {i}/{len(qs)}]{C['0']} {q['text']}")
                        try:
                            run_show(agent, q["text"])
                        except KeyboardInterrupt:
                            print("(dibatalkan, sisa antrean disimpan)")
                            break
                        qmod.remove(1)
                    print(f"\nantrean selesai, sisa {len(qmod.items())}")
            elif rest == "clear":
                n = qmod.clear()
                print(f"{n} tugas dihapus")
            elif rest.startswith("rm "):
                try:
                    ok = qmod.remove(int(rest.split()[1]))
                    print("dihapus" if ok else "nomor tidak ada")
                except (IndexError, ValueError):
                    print("format: /queue rm N")
            else:
                n = qmod.add(rest)
                print(f"ditambahkan ke antrean (#{n})")
            continue
        try:
            divider()
            run_show(agent, line)
        except KeyboardInterrupt:
            print("\n(dibatalkan)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
