# Android — Frida untuk analisis dinamis

Gunakan saat perlu inspeksi runtime (bukan capture HAR).

## Pasang
- Root: push `frida-server` sesuai ABI ke `/data/local/tmp`, `chmod 755`, jalankan
  `su -c "/data/local/tmp/frida-server -D &"`.
- Klien: `pip install frida-tools`; cek `frida-ps -U`.
- Spawn: `frida -U -f <pkg> -l hook.js --no-pause`.

## Pola hook
- Java: `Java.perform(() => { const C = Java.use('...'); C.method.implementation = function(...) {...}; });`
- Native: `Interceptor.attach(Module.findExportByName('libx.so','func'), {...})`.
- Cari class: `Java.enumerateLoadedClasses({onMatch: n => ...})`.
- Bypass SSL pinning: hook `X509TrustManager` / `SSLContext`; untuk Flutter butuh
  patch native BoringSSL, bukan hook Java.

## Pitfall
- App anti-tamper mendeteksi frida-server (nama proses/port/maps); hentikan setelah
  selesai, reboot bila perlu.
- Frida 17 tidak bundle Java bridge; compile dengan frida-compile bila script Java.
- Jangan tinggalkan frida-server jalan saat app produksi dipakai.
