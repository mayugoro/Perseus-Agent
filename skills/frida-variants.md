# Frida — varian & gadget (hluda, Florida, Arida)

Gunakan saat frida-server biasa terdeteksi anti-tamper.

## Varian umum
- **frida-server** resmi: paling mudah dideteksi (nama proses/port/maps).
- **hluda-server**: frida-server yang di-rename (string/port diganti) untuk mengurangi
  deteksi signature; perilaku API sama.
- **Florida**: fork Frida dengan patch stealth (nama/port/paths), cocok untuk app
  dengan deteksi frida dasar. Klien tetap frida-tools.
- **Arida**: fork/rename lain; verifikasi dulu `--version` dan apakah protokol klien
  cocok. Jangan asumsikan kompatibel.
- **frida-gadget**: `libfrida-gadget.so` ditanam ke APK; load via `System.loadLibrary`
  atau config `libfrida-gadget.config`. Tanpa proses frida-server.

## Gadget (repack)
1. Taruh `libfrida-gadget.so` di `lib/<abi>/`.
2. Tambah `libfrida-gadget.config` (listen/interaction).
3. Pastikan code memuat library (smali `System.loadLibrary("frida-gadget")` atau
   `dlopen`), lalu repack + sign ulang.
4. Attach: `frida -U -n Gadget`.

## Pitfall
- Repack mengubah signature → integrity check bisa menolak.
- Beberapa app memeriksa `maps` untuk `frida`/`gadget`; rename file tidak cukup.
- Hentikan proses varian Frida setelah selesai; jangan biarkan aktif saat app produksi.
- Frida 17 tanpa Java bridge: compile script dengan `frida-compile` bila perlu.
