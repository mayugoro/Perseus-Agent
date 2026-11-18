"""Sesi Perseus: SQLite + FTS5 (seperti Hermes state.db)."""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

DIR = Path.home() / ".perseus"
DB = DIR / "state.db"
LEGACY_DIR = DIR / "sessions"


def _conn() -> sqlite3.Connection:
    DIR.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("""CREATE TABLE IF NOT EXISTS sessions(
        id TEXT PRIMARY KEY, created REAL, updated REAL,
        title TEXT DEFAULT '', model TEXT DEFAULT '', provider TEXT DEFAULT '')""")
    c.execute("""CREATE TABLE IF NOT EXISTS messages(
        id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT,
        name TEXT DEFAULT '', tool_call_id TEXT DEFAULT '', content TEXT DEFAULT '',
        created REAL)""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id)")
    try:
        c.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts
                     USING fts5(content, session_id UNINDEXED, role UNINDEXED)""")
    except sqlite3.OperationalError:
        pass
    c.execute("CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT)")
    c.commit()
    _migrate_legacy(c)
    return c


def _migrate_legacy(c: sqlite3.Connection) -> None:
    row = c.execute("SELECT value FROM meta WHERE key='jsonl_migrated'").fetchone()
    if row or not LEGACY_DIR.exists():
        return
    for p in sorted(LEGACY_DIR.glob("*.jsonl")):
        sid = "legacy-" + p.stem
        if c.execute("SELECT 1 FROM sessions WHERE id=?", (sid,)).fetchone():
            continue
        c.execute("INSERT INTO sessions(id,created,updated,title) VALUES (?,?,?,?)",
                  (sid, p.stat().st_mtime, p.stat().st_mtime, ""))
        for line in p.read_text(errors="replace").splitlines():
            try:
                o = json.loads(line)
            except Exception:
                continue
            role = o.get("role")
            if role not in ("user", "assistant", "tool"):
                continue
            _insert(c, sid, o)
    c.execute("INSERT OR REPLACE INTO meta(key,value) VALUES ('jsonl_migrated','1')")
    c.commit()


def _insert(c: sqlite3.Connection, sid: str, msg: dict) -> int:
    content = str(msg.get("content") or "")
    cur = c.execute(
        "INSERT INTO messages(session_id,role,name,tool_call_id,content,created)"
        " VALUES (?,?,?,?,?,?)",
        (sid, msg.get("role", ""), msg.get("name", ""), msg.get("tool_call_id", ""),
         content, time.time()))
    mid = cur.lastrowid
    try:
        c.execute("INSERT INTO messages_fts(rowid,content,session_id,role) VALUES (?,?,?,?)",
                  (mid, content, sid, msg.get("role", "")))
    except sqlite3.OperationalError:
        pass
    return mid


def new_session(cfg: dict | None = None) -> str:
    c = _conn()
    sid = time.strftime("%Y%m%d-%H%M%S") + f"-{int(time.time() * 1000) % 1000}"
    cfg = cfg or {}
    c.execute("INSERT INTO sessions(id,created,updated,title,model,provider) VALUES (?,?,?,?,?,?)",
              (sid, time.time(), time.time(), "", cfg.get("model", ""), cfg.get("base_url", "")))
    c.commit()
    c.close()
    return sid


def append(sid: str, msg: dict) -> None:
    c = _conn()
    _insert(c, sid, msg)
    c.execute("UPDATE sessions SET updated=? WHERE id=?", (time.time(), sid))
    if msg.get("role") == "user":
        row = c.execute("SELECT title FROM sessions WHERE id=?", (sid,)).fetchone()
        if row and not row[0]:
            c.execute("UPDATE sessions SET title=? WHERE id=?",
                      (str(msg.get("content") or "")[:100], sid))
    c.commit()
    c.close()


def list_sessions(limit: int = 20) -> list[dict]:
    c = _conn()
    rows = c.execute("""
        SELECT s.id, s.updated, s.title, s.model,
          (SELECT COUNT(*) FROM messages m WHERE m.session_id=s.id AND m.role='user') AS turns,
          (SELECT COUNT(*) FROM messages m WHERE m.session_id=s.id) AS total,
          (SELECT content FROM messages m WHERE m.session_id=s.id AND m.role='user'
             ORDER BY m.id LIMIT 1) AS preview
        FROM sessions s
        WHERE EXISTS (SELECT 1 FROM messages m WHERE m.session_id=s.id)
        ORDER BY s.updated DESC LIMIT ?""", (limit,)).fetchall()
    c.close()
    return [{"id": r[0], "updated": r[1], "title": r[2], "model": r[3],
             "turns": r[4], "total": r[5], "preview": (r[6] or r[2] or "")[:120]}
            for r in rows]


def load(sid: str) -> list[dict]:
    c = _conn()
    rows = c.execute("SELECT role,content,name FROM messages WHERE session_id=? ORDER BY id",
                     (sid,)).fetchall()
    c.close()
    msgs = []
    for role, content, name in rows:
        content = (content or "").strip()
        if role == "user" and content:
            msgs.append({"role": "user", "content": content})
        elif role == "assistant" and content:
            msgs.append({"role": "assistant", "content": content})
    return msgs


def search(query: str, limit: int = 10) -> list[dict]:
    c = _conn()
    try:
        rows = c.execute("""
            SELECT s.id, s.updated, s.title,
                   snippet(messages_fts, 0, '[', ']', '…', 12) AS snip
            FROM messages_fts f JOIN sessions s ON s.id=f.session_id
            WHERE messages_fts MATCH ? ORDER BY rank LIMIT ?""", (query, limit)).fetchall()
    except sqlite3.OperationalError:
        rows = []
    c.close()
    return [{"id": r[0], "updated": r[1], "title": r[2], "snippet": r[3]} for r in rows]


def resolve(prefix: str) -> str | None:
    c = _conn()
    rows = c.execute("SELECT id FROM sessions WHERE id LIKE ? ORDER BY updated DESC LIMIT 1",
                     (prefix + "%",)).fetchall()
    c.close()
    return rows[0][0] if rows else None


def stats(sid: str) -> dict | None:
    c = _conn()
    r = c.execute("""
        SELECT s.id,s.created,s.updated,s.title,s.model,s.provider,
          (SELECT COUNT(*) FROM messages m WHERE m.session_id=s.id AND m.role='user'),
          (SELECT COUNT(*) FROM messages m WHERE m.session_id=s.id)
        FROM sessions s WHERE s.id=?""", (sid,)).fetchone()
    c.close()
    if not r:
        return None
    return {"id": r[0], "created": r[1], "updated": r[2], "title": r[3],
            "model": r[4], "provider": r[5], "turns": r[6], "total": r[7]}


def fmt_time(ts: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))
