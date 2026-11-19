# Perseus Web UI (TypeScript + Node.js)

Antarmuka Perseus untuk Termux/Android. Semua UI (server, routing, chat, session list)
ditulis TypeScript/JavaScript dan dijalankan Node.js; Python tetap mesin agent di belakang.

```
desktop/
  src/server.ts      HTTP server + proxy /api ke Python + spawn `perseus serve`
  public/index.html  layout
  public/style.css   tema gelap/cyan
  public/app.js      logika chat, sessions, status, stop
```

## Jalankan di Termux

```bash
pkg install -y nodejs
cd ~/Perseus-Agent/desktop
npm install
npm run build
npm start
```

Buka: http://127.0.0.1:8787

Buka otomatis di browser:

```bash
termux-open-url http://127.0.0.1:8787
```

## Konfigurasi

- `PORT` — port UI (default 8787)
- `PERSEUS_API_PORT` — port API Python (default 8801)
- `PERSEUS_PY` — interpreter Python (default `python3`)
- `PERSEUS_NO_SPAWN=1` — jangan spawn Python (kalau `perseus serve` sudah jalan sendiri)

## API

- `GET /api/status` — model, provider, mode, ctx
- `GET /api/sessions` — daftar sesi
- `POST /api/chat` `{text}` — kirim pesan
- `POST /api/stop` — hentikan agent
- `POST /api/new` — sesi baru
- `POST /api/resume` `{id}` — muat sesi
