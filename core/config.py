"""Konfigurasi Perseus — disimpan di ~/.perseus/config.json (0600)."""
from __future__ import annotations

import json
import os
from pathlib import Path

HOME = Path.home()
CONFIG_DIR = HOME / ".perseus"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULTS = {
    "base_url": "",
    "model": "",
    "workspace": str(HOME / "perseus-workspace"),
    "permission": "ask",          # ask | auto | read-only
    "max_steps": 8,
    "max_tokens": 4096,
    "timeout": 180,
    "allow_root": False,
    "api_key_env": "PERSEUS_API_KEY",
    "show_reasoning": True,
    "reasoning_effort": "",
    "auto_learn": True,
    "context_messages": 36,
    "subagents": {"enabled": True, "max_parallel": 3, "permission": "auto"},
}


def _ensure_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(CONFIG_DIR, 0o700)
    except OSError:
        pass


def load() -> dict:
    _ensure_dir()
    cfg = dict(DEFAULTS)
    if CONFIG_FILE.exists():
        try:
            cfg.update(json.loads(CONFIG_FILE.read_text()))
        except Exception:
            pass
    cfg["workspace"] = str(Path(os.path.expanduser(cfg["workspace"])).resolve())
    Path(cfg["workspace"]).mkdir(parents=True, exist_ok=True)
    return cfg


def save(cfg: dict) -> None:
    _ensure_dir()
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))
    try:
        os.chmod(CONFIG_FILE, 0o600)
    except OSError:
        pass


def api_key(cfg: dict) -> str:
    env = cfg.get("api_key_env") or "PERSEUS_API_KEY"
    key = os.environ.get(env, "").strip()
    if not key:
        key = (cfg.get("api_key") or "").strip()
    return key
