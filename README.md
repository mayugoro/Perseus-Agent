# Perseus Agent

AI agent ringan untuk **Termux (Android)**. Semua reasoning lewat provider API
(OpenAI-compatible) — tidak ada model lokal, GGUF, ONNX, atau inferensi CPU.

Dibuat oleh **Mayugoro** (github.com/mayugoro).

Repo ini **kosong secara konfigurasi**: base URL, model, dan API key diisi sendiri
saat setup pertama. Tidak ada provider yang di-hardcode.

## Instal

```bash
pkg install -y git
git clone https://github.com/mayugoro/Perseus-Agent.git
cd Perseus-Agent
./install.sh
```

`install.sh` akan:

1. memasang `python`, `git`, `expat`, dan dependency Python
   (`prompt_toolkit`) dari `requirements.txt`
2. menjalankan wizard: **Base URL** + **API key**; model diambil otomatis dari
   `{base_url}/models` lalu dipilih dari daftar
3. membuat launcher `perseus` di `$PREFIX/bin`

Setelah itu:

```bash
perseus
```

## Setup manual

```bash
python3 perseus.py --init      # wizard provider pertama kali
python3 perseus.py model       # ubah provider / model / API key
python3 perseus.py             # REPL
python3 perseus.py -p "halo"   # satu perintah
```

Kalau sudah di-install, cukup:

```bash
perseus model
```

Konfigurasi disimpan di `~/.perseus/config.json` (0600). API key boleh disimpan
di situ, atau dikosongkan dan pakai environment:

```bash
export PERSEUS_API_KEY='...'
```

## Tampilan

- Pesan Perseus dan garis pemisah antar-turn berwarna cyan/biru (sama dengan logo).
- Blok `[think]` tetap abu-abu/dim.
- Tool call ditandai `⟡` biru.
- Prompt `❯` dengan status bar: model, pemakaian context, durasi respons,
  durasi sesi, dan hint `/ commands · @ files · ! shell`.
- `/usage` menampilkan token perkiraan, context, durasi, reasoning, steps.
- `!perintah` menjalankan shell langsung; `@file` melampirkan isi file dari
  workspace ke pesan.

## Perintah REPL

Ketik `/` — daftar perintah muncul otomatis (completion `prompt_toolkit`,
butuh TTY). Tab/arah untuk memilih, Enter untuk menjalankan.

```
/help                      bantuan
/tools                     daftar tool
/new                       reset percakapan
/mode ask|auto|read-only   mode izin
/model [id]                lihat provider + pilih model + reasoning
/queue [tugas|run|rm N|clear]  antrean tugas
/reasoning [level]         default|low|medium|high
/steps [N]                 batas langkah tool (0/default = unlimited)
/sessions                  daftar sesi tersimpan
/resume <N|id|title>       lanjutkan sesi
/title [teks]              atur judul sesi
/session                   info sesi aktif
/learn                     auto-belajar on/off
/agents [on|off|max N]     subagent paralel
/exit
```

`max_steps` default **0 = unlimited** (seperti agent utama Hermes). Loop tetap
aman karena panggilan tool identik 3x otomatis dilewati. Set batas manual dengan
`/steps 40` (0–500). Kalau batas tercapai, Perseus diminta memberi ringkasan
progres, bukan berhenti dengan pesan kosong.

`/model` tanpa argumen menampilkan provider, model aktif, dan daftar model dari
endpoint `/v1/models`; pilih nomor atau ketik id sendiri. Setelah model dipilih,
wizard menanyakan level reasoning (`default/low/medium/high`) yang dikirim sebagai
`reasoning_effort` — hanya untuk model yang mendukung. Bisa juga langsung:
`/reasoning high`.

`/queue <tugas>` menambah tugas, `/queue` melihat daftar, `/queue run`
menjalankannya berurutan (sesi sama), `/queue rm N` dan `/queue clear` mengelola.
Antrean tersimpan di `~/.perseus/queue.json`, jadi tidak hilang saat CLI ditutup.

## Sesi

Sesi disimpan di **SQLite + FTS5**: `~/.perseus/state.db`
(tabel `sessions`, `messages`, `messages_fts`).

- `/sessions` — tabel: nomor | title | terakhir dipakai | obrolan pertama
- `/sessions <kata>` — cari isi percakapan lewat FTS5
- `/resume N` / `/resume <id>` / `/resume <title>` — muat konteks sesi dan
  tampilkan 6 pesan terakhir (kamu/perseus)
- `/title <teks>` — atur judul sesi (tampil di `/sessions` dan `/exit`)
- `/session` — ID sesi aktif
- Saat `/exit`, Perseus menampilkan ringkasan sesi + perintah resume

Resume dari shell:

```bash
perseus -c 20261118-204418-715     # id penuh
perseus -c "ngobrol kopi"          # title sesi
# saat resume, 6 pesan terakhir ikut ditampilkan
perseus -c 20261118               # awalan id (yang terbaru cocok)
perseus -resume 20261118-204418-715
perseus -c <id> -p "lanjutkan tugas tadi"

perseus sessions list              # daftar sesi
perseus sessions search <kata>     # cari isi percakapan
perseus sessions <id|title>        # buka sesi (detail + 6 pesan terakhir)
perseus resume <id|title>          # langsung lanjut sesi
```

File JSONL lama di `~/.perseus/sessions/` dimigrasikan otomatis sekali saat
pertama kali DB dibuka, lalu tidak ditulis lagi.

## Belajar & berpikir

- Respons di-stream (SSE): teks muncul token demi token, tidak menunggu selesai.
- Saat menunggu token pertama, muncul spinner `⠋ thinking…` (hanya di TTY).
- Blok `[think]` ditampilkan abu-abu/dim saat model mengirim `reasoning_content`;
  toggle `/think`.
- `auto_learn` (default on): setelah jawaban selesai, satu panggilan ringan
  mengekstrak maksimal 2 fakta tahan lama → disimpan ke SQLite. Fakta ini
  diinjeksi ke system prompt sesi berikutnya. Matikan dengan `/learn`.
- `skill_save` menyimpan prosedur ke `~/.perseus/skills/`; daftar skill otomatis
  muncul di system prompt dan dimuat penuh lewat `skill_view`.
- Percakapan panjang diringkas otomatis (`context_messages`, default 36).

## Subagent paralel

Model dapat memanggil tool `delegate_task` untuk menjalankan beberapa subagent
sekaligus. Tiap subagent punya konteks/percakapan sendiri, model yang sama, dan
sesi terpisah — jadi bisa "berpikir sendiri" lalu hasilnya digabung.

Konfigurasi di `~/.perseus/config.json`:

```json
"subagents": {"enabled": true, "max_parallel": 3, "permission": "auto"}
```

Atau lewat REPL: `/agents`, `/agents on|off`, `/agents max N`,
`/agents permission auto|read-only`. Batas aman 1–8 subagent; subagent tidak
boleh mendelegasikan lagi (anti-rekursif).

## Tool

- **File**: `read_file`, `write_file`, `patch_file`, `list_dir`, `search_files`
- **Sistem**: `shell`, `python_exec`, `http_fetch`
- **Memori**: `memory_save`, `memory_search` (SQLite + FTS5)
- **Android**: `android_list_apps`, `android_app_info`, `android_install`,
  `android_uninstall`, `android_launch`, `android_logcat`
- **Skill**: `skill_list`, `skill_view` (folder `skills/*.md`)
  - `android-apps`, `android-logs`, `android-files`, `android-build`, `termux-device`
  - `android-root`, `android-magisk`, `android-lsposed`, `android-frida`,
    `android-network`, `android-system`, `android-backup`, `termux-services`
  - `android-dump`, `frida-variants`, `android-re-sdk`, `android-re-runtime`

## Keamanan

- Workspace jail: default `~/perseus-workspace`, path di luar itu ditolak
- Mode `ask`: tool berisiko (tulis/hapus/install/uninstall) minta konfirmasi
- Backup otomatis file yang ditimpa ke `.perseus/backups/`
- Audit trail: `~/.perseus/sessions/*.jsonl`

## Error provider

Kalau upstream gagal (network, timeout, 429, 5xx), Perseus mencoba ulang
**3x dengan jeda 15 detik** (`retries`, `retry_delay` di config). Error
400/401/403/404 tidak di-retry karena itu kesalahan konfigurasi/model.
Setelah semua percobaan gagal, balasan error ditampilkan tetapi **sesi tetap
hidup** — prompt kembali dan percakapan bisa dilanjutkan.

## Batasan

- Butuh koneksi ke provider; tidak ada mode offline
- `pm install` dapat ditolak PackageManager tertentu → fallback installer UI / SAI
- Tanpa root, install/uninstall mengikuti izin shell Android
- Proses dapat dibunuh Doze; gunakan `termux-wake-lock` bila perlu

## Lisensi

MIT
