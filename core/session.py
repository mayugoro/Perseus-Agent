"""Sesi Perseus: daftar, muat, dan buat file JSONL."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

DIR = Path.home() / ".perseus" / "sessions"


def new_file() -> Path:
    DIR.mkdir(parents=True, exist_ok=True)
    name = time.strftime("%Y%m%d-%H%M%S") + f"-{os.getpid()}.jsonl"
    return DIR / name


def list_sessions(limit: int = 20) -> list[dict]:
    DIR.mkdir(parents=True, exist_ok=True)
    files = [p for p in DIR.glob("*.jsonl") if p.stat().st_size > 0]
    files = sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)
    out = []
    for p in files[:limit]:
        turns = 0
        preview = ""
        try:
            for line in p.read_text(errors="replace").splitlines():
                try:
                    o = json.loads(line)
                except Exception:
                    continue
                if o.get("role") == "user":
                    turns += 1
                    if not preview:
                        preview = str(o.get("content", ""))[:120]
        except Exception:
            pass
        out.append({"path": p, "mtime": p.stat().st_mtime, "turns": turns,
                    "size": p.stat().st_size, "preview": preview})
    return out


def load(path: Path) -> list[dict]:
    msgs = []
    for line in path.read_text(errors="replace").splitlines():
        try:
            o = json.loads(line)
        except Exception:
            continue
        role = o.get("role")
        if role == "user":
            msgs.append(o)
        elif role == "assistant":
            content = (o.get("content") or "").strip()
            if content:
                msgs.append({"role": "assistant", "content": content})
        # tool result tidak dimuat ulang: konteks tool lama tidak selalu valid
        # untuk provider (butuh tool_call_id yang berpasangan)
    return msgs


def fmt_time(ts: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))
