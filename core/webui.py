"""HTTP API untuk Web UI (Node/TS). Bind 127.0.0.1."""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LOCK = threading.Lock()


def make_handler(agent, cfg):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _json(self, obj, code=200):
            b = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def do_GET(self):
            if self.path.startswith("/api/status"):
                self._json({
                    "model": agent.llm.model,
                    "provider": cfg.get("base_url", ""),
                    "mode": agent.permission,
                    "reasoning": cfg.get("reasoning_effort", ""),
                    "yolo": cfg.get("yolo", False),
                    "ctx_limit": agent.context_length,
                    "ctx_tokens": int(agent.last_usage.get("total_tokens") or 0),
                    "session": agent.session_id,
                    "skills": 0,
                })
            elif self.path.startswith("/api/sessions"):
                from . import session as sess
                ss = sess.list_sessions(30)
                for x in ss:
                    x["rel"] = sess.rel_time(x.get("updated", 0))
                self._json({"sessions": ss})
            else:
                self._json({"error": "not found"}, 404)

        def do_POST(self):
            n = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(n) or b"{}")
            except Exception:
                body = {}
            if self.path == "/api/chat":
                text = str(body.get("text", "")).strip()
                if not text:
                    return self._json({"error": "empty"}, 400)
                with LOCK:
                    out = agent.run(text, stream=False)
                return self._json({"text": out})
            if self.path == "/api/stop":
                agent.abort.set()
                return self._json({"ok": True})
            if self.path == "/api/new":
                agent.reset()
                from . import session as sess
                agent.session_id = sess.new_session(cfg)
                return self._json({"ok": True, "session": agent.session_id})
            if self.path == "/api/resume":
                from . import session as sess
                sid = sess.resolve(str(body.get("id", "")))
                if not sid:
                    return self._json({"error": "session not found"}, 404)
                agent.messages = sess.load(sid)
                agent.session_id = sid
                st = sess.stats(sid) or {}
                return self._json({"ok": True, "session": sid, "title": st.get("title", ""),
                                   "messages": agent.messages[-20:]})
            self._json({"error": "not found"}, 404)

    return H


def serve(agent, cfg, port: int = 8765):
    srv = ThreadingHTTPServer(("127.0.0.1", port), make_handler(agent, cfg))
    print(f"Perseus web API: http://127.0.0.1:{port}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
