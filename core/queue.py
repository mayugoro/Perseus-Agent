"""Antrean tugas Perseus — disimpan di ~/.perseus/queue.json."""
from __future__ import annotations

import json
import time
from pathlib import Path

FILE = Path.home() / ".perseus" / "queue.json"


def _load() -> list[dict]:
    if not FILE.exists():
        return []
    try:
        data = json.loads(FILE.read_text())
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save(items: list[dict]) -> None:
    FILE.parent.mkdir(parents=True, exist_ok=True)
    FILE.write_text(json.dumps(items, indent=2, ensure_ascii=False))
    try:
        FILE.chmod(0o600)
    except OSError:
        pass


def add(text: str) -> int:
    items = _load()
    items.append({"text": text, "created": time.strftime("%Y-%m-%d %H:%M:%S")})
    _save(items)
    return len(items)


def items() -> list[dict]:
    return _load()


def remove(index: int) -> bool:
    items = _load()
    if 1 <= index <= len(items):
        items.pop(index - 1)
        _save(items)
        return True
    return False


def clear() -> int:
    n = len(_load())
    _save([])
    return n
