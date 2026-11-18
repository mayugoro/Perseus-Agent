# Perseus Agent

AI agent ringan untuk **Termux (Android)**. Semua reasoning lewat provider API
(OpenAI-compatible) — tidak ada model lokal, GGUF, ONNX, atau inferensi CPU.

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

1. memasang `python` dan `git`
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

## Perintah REPL

```
/help                      bantuan
/tools                     daftar tool
/new                       reset percakapan
/mode ask|auto|read-only   mode izin
/model [id]                lihat provider + pilih model + reasoning
/queue [tugas|run|rm N|clear]  antrean tugas
/reasoning [level]         default|low|medium|high
/sessions                  daftar sesi tersimpan
/resume N                  lanjutkan sesi ke-N
/session                   info sesi aktif
/learn                     auto-belajar on/off
/agents [on|off|max N]     subagent paralel
/exit
```

`/model` tanpa argumen menampilkan provider, model aktif, dan daftar model dari
endpoint `/v1/models`; pilih nomor atau ketik id sendiri. Setelah model dipilih,
wizard menanyakan level reasoning (`default/low/medium/high`) yang dikirim sebagai
`reasoning_effort` — hanya untuk model yang mendukung. Bisa juga langsung:
`/reasoning high`.

`/queue <tugas>` menambah tugas, `/queue` melihat daftar, `/queue run`
menjalankannya berurutan (sesi sama), `/queue rm N` dan `/queue clear` mengelola.
Antrean tersimpan di `~/.perseus/queue.json`, jadi tidak hilang saat CLI ditutup.

## Sesi

Setiap percakapan disimpan otomatis ke `~/.perseus/sessions/*.jsonl`.
`/sessions` menampilkan daftar (waktu, jumlah turn, cuplikan), `/resume N`
memuat kembali konteks sesi itu, dan `/session` menunjukkan file aktif.
Percakapan yang di-resume tetap memakai memory dan skill yang sama.

## Belajar & berpikir

- Sebelum menjawab, Perseus menentukan tujuan/batasan/langkah dulu (dan menampilkan
  `[think]` bila model mengirim `reasoning_content`; toggle `/think`).
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

## Keamanan

- Workspace jail: default `~/perseus-workspace`, path di luar itu ditolak
- Mode `ask`: tool berisiko (tulis/hapus/install/uninstall) minta konfirmasi
- Backup otomatis file yang ditimpa ke `.perseus/backups/`
- Audit trail: `~/.perseus/sessions/*.jsonl`

## Batasan

- Butuh koneksi ke provider; tidak ada mode offline
- `pm install` dapat ditolak PackageManager tertentu → fallback installer UI / SAI
- Tanpa root, install/uninstall mengikuti izin shell Android
- Proses dapat dibunuh Doze; gunakan `termux-wake-lock` bila perlu

## Lisensi

MIT
