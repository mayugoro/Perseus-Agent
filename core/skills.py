"""Skill markdown Perseus — dibaca on-demand, bisa ditulis sendiri."""
from __future__ import annotations

import re
from pathlib import Path

USER_DIR = Path.home() / ".perseus" / "skills"
REPO_DIR = Path(__file__).resolve().parent.parent / "skills"


def _dirs() -> list[Path]:
    return [USER_DIR, REPO_DIR]


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s[:60] or "skill"


def list_skills() -> list[tuple[str, str]]:
    out = []
    seen = set()
    for d in _dirs():
        if not d.exists():
            continue
        for p in sorted(d.glob("*.md")):
            if p.stem in seen:
                continue
            seen.add(p.stem)
            desc = ""
            for line in p.read_text(errors="replace").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:120]
                    break
            out.append((p.stem, desc))
    return out


def view(name: str) -> str:
    name = _slug(name)
    for d in _dirs():
        p = d / f"{name}.md"
        if p.exists():
            return p.read_text(errors="replace")
    return f"ERROR: skill '{name}' tidak ada"


def save(name: str, content: str) -> str:
    USER_DIR.mkdir(parents=True, exist_ok=True)
    p = USER_DIR / f"{_slug(name)}.md"
    p.write_text(content)
    try:
        p.chmod(0o600)
    except OSError:
        pass
    return str(p)
