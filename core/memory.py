"""Memory Perseus: SQLite + FTS5, profil user terpisah, konsolidasi fakta."""
from __future__ import annotations

import re
import sqlite3
import time
from pathlib import Path

DB = Path.home() / ".perseus" / "memory.db"
KINDS = ("profile", "memory")


def _conn() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB)
    c.execute("CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY AUTOINCREMENT,"
              " text TEXT NOT NULL, kind TEXT DEFAULT 'memory', created REAL NOT NULL,"
              " updated REAL NOT NULL DEFAULT 0)")
    cols = {r[1] for r in c.execute("PRAGMA table_info(notes)")}
    if "kind" not in cols:
        c.execute("ALTER TABLE notes ADD COLUMN kind TEXT DEFAULT 'memory'")
    if "updated" not in cols:
        c.execute("ALTER TABLE notes ADD COLUMN updated REAL DEFAULT 0")
    try:
        c.execute("CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(text)")
        c.execute("INSERT INTO notes_fts(rowid,text) SELECT id,text FROM notes "
                  "WHERE id NOT IN (SELECT rowid FROM notes_fts)")
    except sqlite3.OperationalError:
        pass
    c.commit()
    return c


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) >= 3}


def _similar(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def save(text: str, kind: str = "memory") -> int:
    kind = kind if kind in KINDS else "memory"
    c = _conn()
    row = c.execute("SELECT id FROM notes WHERE lower(text)=lower(?)", (text,)).fetchone()
    if row:
        c.execute("UPDATE notes SET updated=?, kind=? WHERE id=?", (time.time(), kind, row[0]))
        c.commit()
        c.close()
        return row[0]
    now = time.time()
    cur = c.execute("INSERT INTO notes(text,kind,created,updated) VALUES (?,?,?,?)",
                    (text, kind, now, now))
    mid = cur.lastrowid
    try:
        c.execute("INSERT INTO notes_fts(rowid,text) VALUES (?,?)", (mid, text))
    except sqlite3.OperationalError:
        pass
    c.commit()
    c.close()
    consolidate(kind)
    return mid


def consolidate(kind: str | None = None) -> int:
    """Gabungkan fakta yang sangat mirip (Jaccard >= 0.75)."""
    c = _conn()
    q = "SELECT id,text,created FROM notes"
    args = ()
    if kind:
        q += " WHERE kind=?"
        args = (kind,)
    rows = c.execute(q + " ORDER BY id", args).fetchall()
    removed = 0
    alive = []
    for rid, text, created in rows:
        merged = False
        for i, (pid, ptext, pcreated) in enumerate(alive):
            if _similar(text, ptext) >= 0.75:
                # pertahankan versi terbaru, id lama
                keep = text if created >= pcreated else ptext
                c.execute("UPDATE notes SET text=?, updated=? WHERE id=?", (keep, time.time(), pid))
                try:
                    c.execute("DELETE FROM notes_fts WHERE rowid=?", (rid,))
                    c.execute("UPDATE notes_fts SET text=? WHERE rowid=?", (keep, pid))
                except sqlite3.OperationalError:
                    pass
                c.execute("DELETE FROM notes WHERE id=?", (rid,))
                alive[i] = (pid, keep, max(created, pcreated))
                removed += 1
                merged = True
                break
        if not merged:
            alive.append((rid, text, created))
    c.commit()
    c.close()
    return removed


def recent(limit: int = 5, kind: str | None = None) -> list[tuple[int, str]]:
    c = _conn()
    if kind:
        rows = c.execute("SELECT id,text FROM notes WHERE kind=? ORDER BY id DESC LIMIT ?",
                         (kind, limit)).fetchall()
    else:
        rows = c.execute("SELECT id,text FROM notes ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    c.close()
    return rows


def search(query: str, limit: int = 5, kind: str | None = None) -> list[tuple[int, str]]:
    c = _conn()
    rows = []
    try:
        sql = ("SELECT n.id,n.text FROM notes_fts f JOIN notes n ON n.id=f.rowid "
               "WHERE notes_fts MATCH ?")
        args: list = [query]
        if kind:
            sql += " AND n.kind=?"
            args.append(kind)
        sql += " ORDER BY rank LIMIT ?"
        args.append(limit)
        rows = c.execute(sql, args).fetchall()
    except sqlite3.OperationalError:
        rows = c.execute("SELECT id,text FROM notes WHERE text LIKE ? LIMIT ?",
                         (f"%{query}%", limit)).fetchall()
    c.close()
    return rows
