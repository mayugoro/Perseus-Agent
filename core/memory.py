"""Memory Perseus: SQLite + FTS5 (fallback LIKE)."""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

DB = Path.home() / ".perseus" / "memory.db"


def _conn() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB)
    c.execute("CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY AUTOINCREMENT,"
              " text TEXT NOT NULL, created REAL NOT NULL)")
    try:
        c.execute("CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(text)")
        c.execute("INSERT INTO notes_fts(rowid,text) SELECT id,text FROM notes "
                  "WHERE id NOT IN (SELECT rowid FROM notes_fts)")
    except sqlite3.OperationalError:
        pass
    return c


def save(text: str) -> int:
    c = _conn()
    row = c.execute("SELECT id FROM notes WHERE text=?", (text,)).fetchone()
    if row:
        c.close()
        return row[0]
    cur = c.execute("INSERT INTO notes(text,created) VALUES (?,?)", (text, time.time()))
    mid = cur.lastrowid
    try:
        c.execute("INSERT INTO notes_fts(rowid,text) VALUES (?,?)", (mid, text))
    except sqlite3.OperationalError:
        pass
    c.commit()
    c.close()
    return mid


def recent(limit: int = 5) -> list[tuple[int, str]]:
    c = _conn()
    rows = c.execute("SELECT id,text FROM notes ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    c.close()
    return rows


def search(query: str, limit: int = 5) -> list[tuple[int, str]]:
    c = _conn()
    rows = []
    try:
        rows = c.execute(
            "SELECT n.id,n.text FROM notes_fts f JOIN notes n ON n.id=f.rowid "
            "WHERE notes_fts MATCH ? ORDER BY rank LIMIT ?", (query, limit)).fetchall()
    except sqlite3.OperationalError:
        rows = c.execute("SELECT id,text FROM notes WHERE text LIKE ? LIMIT ?",
                         (f"%{query}%", limit)).fetchall()
    c.close()
    return rows
