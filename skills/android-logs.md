# Android — log, crash, dan status proses

Gunakan saat app force close, “mental”, atau user minta diagnosis.

## Log dasar
- `android_logcat {"lines":200}` → `logcat -d -t 200`.
- Filter: `android_logcat {"filter":"neobiz|FATAL|AndroidRuntime","lines":300}`.
- Crash buffer: `logcat -b crash -d | tail -80` lewat `shell`.
- System kill: `logcat -b system -d | grep -i "Killing <pkg>"`.

## Crash vs self-exit
- `dumpsys activity exit-info <pkg> | head -30`
  - `reason=1 (EXIT_SELF)` → kode memanggil exit sendiri.
  - `reason=5 (APP CRASH(NATIVE))` + `status=11` → SIGSEGV native.
  - `reason=4 (CRASH)` → exception Java (lihat crash buffer).
- Tombstone: `ls -lt /data/tombstones | head -3`, lalu `head -60` file terbaru
  (butuh root; cari baris `name: ... >>> <pkg> <<<` dan backtrace lib).

## Pitfall
- `logcat -d` buffer bisa terpotong; ambil `-b crash` terpisah.
- Awal baris `FATAL EXCEPTION` sering tidak memuat penyebab; cari `Caused by:` atau
  baris pertama setelah `Process:`.
- Jangan menyimpulkan “deteksi root” sebelum lihat reason + backtrace.
