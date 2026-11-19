import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { spawn, ChildProcess } from "node:child_process";

const ROOT = path.resolve(__dirname, "..", "..");
const PUBLIC = path.resolve(__dirname, "..", "public");
const API_PORT = Number(process.env.PERSEUS_API_PORT || 8801);
const PORT = Number(process.env.PORT || 8787);

const MIME: Record<string, string> = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".json": "application/json; charset=utf-8",
};

let py: ChildProcess | null = null;
if (process.env.PERSEUS_NO_SPAWN !== "1") {
  py = spawn(process.env.PERSEUS_PY || "python3",
    ["perseus.py", "serve", "--port", String(API_PORT)],
    { cwd: ROOT, stdio: ["ignore", "inherit", "inherit"] });
  py.on("exit", (c) => console.error(`[perseus] python exited ${c}`));
}

async function proxy(req: http.IncomingMessage, res: http.ServerResponse) {
  const chunks: Buffer[] = [];
  for await (const c of req) chunks.push(c as Buffer);
  const body = Buffer.concat(chunks);
  try {
    const r = await fetch(`http://127.0.0.1:${API_PORT}${req.url}`, {
      method: req.method,
      headers: { "content-type": req.headers["content-type"] || "application/json" },
      body: req.method === "GET" || req.method === "HEAD" ? undefined : body,
    });
    const buf = Buffer.from(await r.arrayBuffer());
    res.writeHead(r.status, { "content-type": r.headers.get("content-type") || "application/json" });
    res.end(buf);
  } catch (e) {
    res.writeHead(502, { "content-type": "application/json" });
    res.end(JSON.stringify({ error: "perseus API unavailable", detail: String(e) }));
  }
}

const server = http.createServer((req, res) => {
  const url = (req.url || "/").split("?")[0];
  if (url.startsWith("/api/")) return void proxy(req, res);
  const rel = url === "/" ? "index.html" : url.replace(/^\/+/, "");
  const file = path.resolve(PUBLIC, rel);
  if (!file.startsWith(PUBLIC)) { res.writeHead(403); return res.end("forbidden"); }
  fs.readFile(file, (err, data) => {
    if (err) { res.writeHead(404); return res.end("not found"); }
    res.writeHead(200, { "content-type": MIME[path.extname(file)] || "application/octet-stream" });
    res.end(data);
  });
});

server.listen(PORT, "127.0.0.1", () => {
  console.log(`Perseus web UI: http://127.0.0.1:${PORT}`);
});

function shutdown() { py?.kill("SIGTERM"); server.close(); process.exit(0); }
process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
