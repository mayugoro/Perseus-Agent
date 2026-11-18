"""Tool registry Perseus — semua eksekusi lokal, tanpa model lokal."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import memory
from . import skills as sk

DESTRUCTIVE = [
    r"\brm\s+-[a-z]*r[a-z]*f?\s+/(\s|$)", r"\bmkfs\b", r"\bdd\s+.*of=/dev/",
    r">\s*/dev/(sd|block)", r"\breboot\b", r"\bpoweroff\b", r"\bpm\s+uninstall\b",
    r"\bpm\s+clear\b", r"\bcmd\s+package\s+uninstall\b", r"\bsu\s+-c\s+rm\b",
]


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    func: Callable[..., str]
    danger: bool = False


class Registry:
    def __init__(self, cfg: dict, allow_delegate: bool = True):
        self.cfg = cfg
        self.allow_delegate = allow_delegate
        self.workspace = Path(cfg["workspace"])
        self.timeout = int(cfg.get("timeout", 180))
        self.tools: dict[str, Tool] = {}
        self._register()

    # ---------------------------------------------------------------- utils
    def add(self, name, description, parameters, func, danger=False):
        self.tools[name] = Tool(name, description, parameters, func, danger)

    def schema(self) -> list:
        return [{"type": "function", "function": {
            "name": t.name, "description": t.description, "parameters": t.parameters,
        }} for t in self.tools.values()]

    def confirm_needed(self, name: str, args: dict) -> bool:
        if name not in self.tools:
            return False
        t = self.tools[name]
        if t.danger:
            return True
        if name == "shell":
            cmd = str(args.get("command", ""))
            return any(re.search(p, cmd) for p in DESTRUCTIVE)
        return False

    def call(self, name: str, args: dict) -> str:
        t = self.tools.get(name)
        if not t:
            return f"ERROR: tool '{name}' tidak ada"
        try:
            return t.func(**args)
        except TypeError as e:
            return f"ERROR argumen: {e}"
        except Exception as e:
            return f"ERROR: {type(e).__name__}: {e}"

    def resolve(self, p: str) -> Path:
        path = Path(os.path.expanduser(str(p)))
        if not path.is_absolute():
            path = self.workspace / path
        path = path.resolve()
        if self.workspace not in path.parents and path != self.workspace:
            raise PermissionError(f"di luar workspace: {path}")
        return path

    def backup(self, path: Path) -> None:
        if not path.exists():
            return
        bdir = self.workspace / ".perseus" / "backups"
        bdir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        shutil.copy2(path, bdir / f"{path.name}.{stamp}.bak")

    # ---------------------------------------------------------------- daftar
    def _register(self):
        self.add("shell", "Jalankan perintah shell di workspace. Kembalikan stdout+stderr.",
                 {"type": "object", "properties": {
                     "command": {"type": "string"},
                     "timeout": {"type": "integer", "description": "detik, default 180"}},
                  "required": ["command"]}, self.t_shell)

        self.add("read_file", "Baca file teks (maks 200 KB).",
                 {"type": "object", "properties": {"path": {"type": "string"}},
                  "required": ["path"]}, self.t_read)

        self.add("write_file", "Tulis/overwrite file. Backup otomatis file lama.",
                 {"type": "object", "properties": {
                     "path": {"type": "string"}, "content": {"type": "string"}},
                  "required": ["path", "content"]}, self.t_write, danger=True)

        self.add("patch_file", "Ganti satu potongan teks di file (old -> new).",
                 {"type": "object", "properties": {
                     "path": {"type": "string"}, "old": {"type": "string"},
                     "new": {"type": "string"}, "replace_all": {"type": "boolean"}},
                  "required": ["path", "old", "new"]}, self.t_patch, danger=True)

        self.add("list_dir", "Daftar isi direktori.",
                 {"type": "object", "properties": {"path": {"type": "string"}},
                  "required": []}, self.t_ls)

        self.add("search_files", "Cari teks di file (regex sederhana).",
                 {"type": "object", "properties": {
                     "pattern": {"type": "string"}, "path": {"type": "string"},
                     "glob": {"type": "string"}},
                  "required": ["pattern"]}, self.t_search)

        self.add("http_fetch", "Ambil isi URL (GET, teks/JSON).",
                 {"type": "object", "properties": {
                     "url": {"type": "string"}, "max_chars": {"type": "integer"}},
                  "required": ["url"]}, self.t_http)

        self.add("python_exec", "Jalankan kode Python di workspace.",
                 {"type": "object", "properties": {
                     "code": {"type": "string"}, "timeout": {"type": "integer"}},
                  "required": ["code"]}, self.t_py)

        self.add("memory_save", "Simpan catatan permanen (kind: profile untuk fakta user).",
                 {"type": "object", "properties": {
                     "text": {"type": "string"},
                     "kind": {"type": "string", "enum": ["profile", "memory"]}},
                  "required": ["text"]}, self.t_mem_save)

        self.add("memory_search", "Cari catatan permanen.",
                 {"type": "object", "properties": {
                     "query": {"type": "string"}, "limit": {"type": "integer"}},
                  "required": ["query"]}, self.t_mem_search)

        self.add("android_list_apps", "Daftar aplikasi terpasang (third-party).",
                 {"type": "object", "properties": {"all": {"type": "boolean"}},
                  "required": []}, self.t_apps)

        self.add("android_app_info", "Detail paket: versi, signature, komponen.",
                 {"type": "object", "properties": {"package": {"type": "string"}},
                  "required": ["package"]}, self.t_app_info)

        self.add("android_install", "Install APK. Coba pm install; jika gagal, sarankan installer UI.",
                 {"type": "object", "properties": {"path": {"type": "string"}},
                  "required": ["path"]}, self.t_install, danger=True)

        self.add("android_uninstall", "Uninstall aplikasi.",
                 {"type": "object", "properties": {"package": {"type": "string"}},
                  "required": ["package"]}, self.t_uninstall, danger=True)

        self.add("android_launch", "Buka aplikasi berdasarkan package.",
                 {"type": "object", "properties": {"package": {"type": "string"}},
                  "required": ["package"]}, self.t_launch)

        self.add("android_logcat", "Ambil logcat terakhir (opsional filter teks).",
                 {"type": "object", "properties": {
                     "filter": {"type": "string"}, "lines": {"type": "integer"}},
                  "required": []}, self.t_logcat)

        if self.allow_delegate and (self.cfg.get("subagents") or {}).get("enabled", True):
            self.add("delegate_task",
                     "Jalankan beberapa subagent paralel, masing-masing punya konteks sendiri. "
                     "Kirim daftar tugas; hasilnya ringkasan per tugas.",
                     {"type": "object", "properties": {
                         "tasks": {"type": "array", "items": {"type": "object", "properties": {
                             "goal": {"type": "string"},
                             "context": {"type": "string"}},
                             "required": ["goal"]}},
                         "max_parallel": {"type": "integer"}},
                      "required": ["tasks"]}, self.t_delegate)

        self.add("skill_list", "Daftar skill markdown di folder skills/.",
                 {"type": "object", "properties": {}, "required": []}, self.t_skill_list)

        self.add("skill_view", "Baca isi skill markdown.",
                 {"type": "object", "properties": {"name": {"type": "string"}},
                  "required": ["name"]}, self.t_skill_view)

        self.add("skill_save", "Simpan/perbarui skill markdown agar dipakai di sesi berikutnya.",
                 {"type": "object", "properties": {
                     "name": {"type": "string"}, "content": {"type": "string"}},
                  "required": ["name", "content"]}, self.t_skill_save, danger=True)

    # ---------------------------------------------------------------- impl
    def t_shell(self, command: str, timeout: int | None = None) -> str:
        t = min(int(timeout or self.timeout), 600)
        r = subprocess.run(command, shell=True, cwd=self.workspace,
                           capture_output=True, text=True, timeout=t)
        out = (r.stdout or "") + (("\n[stderr]\n" + r.stderr) if r.stderr else "")
        return f"exit={r.returncode}\n{out[:12000]}"

    def t_read(self, path: str) -> str:
        p = self.resolve(path)
        if p.stat().st_size > 200_000:
            return f"ERROR: file > 200KB ({p.stat().st_size} bytes)"
        return p.read_text(errors="replace")

    def t_write(self, path: str, content: str) -> str:
        p = self.resolve(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        self.backup(p)
        p.write_text(content)
        return f"OK tulis {p} ({len(content)} chars)"

    def t_patch(self, path: str, old: str, new: str, replace_all: bool = False) -> str:
        p = self.resolve(path)
        s = p.read_text()
        n = s.count(old)
        if n == 0:
            return "ERROR: teks tidak ditemukan"
        self.backup(p)
        s = s.replace(old, new) if replace_all else s.replace(old, new, 1)
        p.write_text(s)
        return f"OK patch {p} ({n} kecocokan, replaced={'all' if replace_all else 1})"

    def t_ls(self, path: str = ".") -> str:
        p = self.resolve(path)
        rows = []
        for x in sorted(p.iterdir(), key=lambda z: z.name.lower()):
            rows.append(f"{'d' if x.is_dir() else '-'} {x.stat().st_size:>9} {x.name}")
        return "\n".join(rows) or "(kosong)"

    def t_search(self, pattern: str, path: str = ".", glob: str = "*") -> str:
        p = self.resolve(path)
        rx = re.compile(pattern)
        hits = []
        for f in p.rglob(glob):
            if not f.is_file() or f.stat().st_size > 500_000:
                continue
            try:
                for i, line in enumerate(f.read_text(errors="replace").splitlines(), 1):
                    if rx.search(line):
                        hits.append(f"{f.relative_to(self.workspace)}:{i}: {line[:200]}")
                        if len(hits) >= 60:
                            return "\n".join(hits)
            except Exception:
                continue
        return "\n".join(hits) or "(tidak ada)"

    def t_http(self, url: str, max_chars: int = 12000) -> str:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 Perseus"})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read(int(max_chars) * 2).decode("utf-8", "replace")
        return data[:int(max_chars)]

    def t_py(self, code: str, timeout: int | None = None) -> str:
        t = min(int(timeout or self.timeout), 600)
        r = subprocess.run(["python3", "-c", code], cwd=self.workspace,
                           capture_output=True, text=True, timeout=t)
        out = (r.stdout or "") + (("\n[stderr]\n" + r.stderr) if r.stderr else "")
        return f"exit={r.returncode}\n{out[:12000]}"

    def t_mem_save(self, text: str, kind: str = "memory") -> str:
        mid = memory.save(text, kind)
        return f"OK {kind} #{mid}"

    def t_mem_search(self, query: str, limit: int = 5) -> str:
        rows = memory.search(query, int(limit))
        return "\n".join(f"#{r[0]} {r[1]}" for r in rows) or "(tidak ada)"

    # android
    def _run(self, cmd: list[str], timeout: int = 60) -> subprocess.CompletedProcess:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

    def t_apps(self, all: bool = False) -> str:
        cmd = ["pm", "list", "packages"] + ([] if all else ["-3"])
        r = self._run(cmd)
        lines = sorted(x.replace("package:", "") for x in r.stdout.splitlines() if x)
        return f"{len(lines)} paket\n" + "\n".join(lines[:200])

    def t_app_info(self, package: str) -> str:
        r = self._run(["dumpsys", "package", package])
        out = r.stdout
        keep = [l for l in out.splitlines() if re.search(
            r"versionName|versionCode|firstInstallTime|lastUpdateTime|signatures|codePath|"
            r"pkgFlags|privateFlags|splitName|primaryCpuAbi|dataDir|userId", l)]
        return "\n".join(keep[:80]) or out[:4000]

    def t_install(self, path: str) -> str:
        p = Path(os.path.expanduser(path))
        if not p.exists():
            return f"ERROR: file tidak ada: {p}"
        r = self._run(["pm", "install", "-r", str(p)], timeout=300)
        if r.returncode == 0 and "Success" in (r.stdout + r.stderr):
            return "OK: " + (r.stdout + r.stderr).strip()
        return (f"GAGAL pm install: {(r.stdout + r.stderr).strip()[:300]}\n"
                f"Fallback: termux-open '{p}' lalu ketuk Install, atau pakai SAI untuk split.")

    def t_uninstall(self, package: str) -> str:
        r = self._run(["pm", "uninstall", package], timeout=120)
        return (r.stdout + r.stderr).strip() or f"exit={r.returncode}"

    def t_launch(self, package: str) -> str:
        r = self._run(["monkey", "-p", package, "-c",
                       "android.intent.category.LAUNCHER", "1"], timeout=30)
        return (r.stdout + r.stderr).strip()[:1000]

    def t_logcat(self, filter: str = "", lines: int = 80) -> str:
        r = self._run(["logcat", "-d", "-t", str(int(lines))], timeout=30)
        out = r.stdout
        if filter:
            rx = re.compile(filter, re.I)
            out = "\n".join(l for l in out.splitlines() if rx.search(l))
        return out[-12000:] or "(kosong)"

    # subagents
    def t_delegate(self, tasks: list, max_parallel: int | None = None) -> str:
        import concurrent.futures as cf
        from .agent import Agent

        conf = self.cfg.get("subagents") or {}
        limit = int(max_parallel or conf.get("max_parallel", 3))
        limit = max(1, min(limit, 8))
        if not tasks:
            return "ERROR: tasks kosong"

        def run_one(idx_item) -> dict:
            i, item = idx_item
            goal = str(item.get("goal", "")).strip()
            ctx = str(item.get("context", "")).strip()
            sub_cfg = dict(self.cfg)
            sub_cfg["permission"] = conf.get("permission", "auto")
            tag = f"[A{i}]"
            print(f"{tag} ▶ {goal[:100]}")
            a = Agent(sub_cfg, confirm=lambda *_: True, log=True,
                      allow_delegate=False, prefix=tag + " ")
            prompt = goal if not ctx else f"{goal}\n\nKonteks:\n{ctx}"
            try:
                res = a.run(prompt)
                print(f"{tag} ✓ selesai")
                return {"goal": goal, "result": res}
            except Exception as e:
                print(f"{tag} ✗ {type(e).__name__}: {e}")
                return {"goal": goal, "result": f"ERROR: {type(e).__name__}: {e}"}

        with cf.ThreadPoolExecutor(max_workers=limit) as ex:
            results = list(ex.map(run_one, list(enumerate(tasks, 1))))
        return json.dumps(results, ensure_ascii=False, indent=2)

    # skills
    def t_skill_list(self) -> str:
        return "\n".join(f"- {n}: {d}" for n, d in sk.list_skills()) or "(belum ada skill)"

    def t_skill_view(self, name: str) -> str:
        return sk.view(name)

    def t_skill_save(self, name: str, content: str) -> str:
        return "OK skill disimpan: " + sk.save(name, content)
