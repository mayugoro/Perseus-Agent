#!/usr/bin/env python3
"""Perseus — AI agent Termux-native (provider API, tanpa model lokal)."""
from __future__ import annotations

import argparse
import getpass
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core import config as cfgmod
from core import queue as qmod
from core.agent import Agent

C = {"b": "\033[1m", "c": "\033[36m", "y": "\033[33m", "r": "\033[31m", "0": "\033[0m"}

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
    print(f"  mode      : {cfg['permission']}")
    print(f"  workspace : {cfg['workspace']}")
    print(f"  {C['y']}/help{C['0']} bantuan · {C['y']}/tools{C['0']} daftar tool · "
          f"{C['y']}/exit{C['0']} keluar\n")


def show_tools(agent: Agent) -> None:
    for t in agent.registry.tools.values():
        flag = "!" if t.danger else " "
        print(f" {flag} {t.name:<20} {t.description[:70]}")


def wizard(cfg: dict) -> dict:
    print(f"{C['b']}Perseus setup{C['0']} — isi provider sendiri (tidak ada default).\n")
    base = input(f"Base URL  [{cfg.get('base_url') or 'https://…/v1'}]: ").strip()
    if base:
        cfg["base_url"] = base.rstrip("/")
    model = input(f"Model     [{cfg.get('model') or 'nama-model'}]: ").strip()
    if model:
        cfg["model"] = model
    print("API key disimpan lokal di ~/.perseus/config.json (0600).")
    print("Kosongkan kalau mau pakai env PERSEUS_API_KEY.")
    key = getpass.getpass("API key   : ").strip()
    if key:
        cfg["api_key"] = key
    mode = input(f"Mode izin [ask/auto/read-only, sekarang {cfg.get('permission','ask')}]: ").strip()
    if mode in ("ask", "auto", "read-only"):
        cfg["permission"] = mode
    cfgmod.save(cfg)
    print(f"\nTersimpan. Model={cfg['model']} · mode={cfg['permission']}\n")
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
    ap.add_argument("command", nargs="?", choices=["model", "setup"],
                    help="model = ubah provider/model/API key")
    ap.add_argument("--init", action="store_true", help="buat config default")
    ap.add_argument("--show-config", action="store_true")
    a = ap.parse_args()

    cfg = cfgmod.load()
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
        cfg = wizard(cfg)
    elif not ready(cfg) and not a.prompt:
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

    if a.prompt:
        print(agent.run(a.prompt))
        return 0

    banner(cfg)

    while True:
        try:
            line = input(f"{C['c']}perseus>{C['0']} ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line in ("/exit", "/quit", "exit", "quit"):
            break
        if line == "/help":
            print("/tools  daftar tool\n/new    reset percakapan\n/mode ask|auto|read-only"
                  "\n/model <id>\n/queue [tugas|run|rm N|clear]  antrean tugas\n/exit   keluar")
            continue
        if line == "/tools":
            show_tools(agent)
            continue
        if line == "/new":
            agent.reset()
            print("(percakapan baru)")
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
        if line.startswith("/model "):
            m = line.split(None, 1)[1].strip()
            agent.llm.model = m
            cfg["model"] = m
            cfgmod.save(cfg)
            print(f"model={m}")
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
                            out = agent.run(q["text"])
                            print(out)
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
            print(agent.run(line))
        except KeyboardInterrupt:
            print("\n(dibatalkan)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
