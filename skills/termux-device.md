# Termux — kontrol perangkat

Gunakan saat user minta baterai, notifikasi, clipboard, lokasi, getar, atau TTS.

## Perintah (butuh `pkg install termux-api` + app Termux:API)
- Baterai: `termux-battery-status`
- Notifikasi: `termux-notification --title "..." --content "..."`
- Clipboard: `termux-clipboard-get` / `termux-clipboard-set "..."`
- Getar: `termux-vibrate -d 300`
- Toast: `termux-toast "pesan"`
- Lokasi: `termux-location -p network` (izin lokasi)
- TTS: `termux-tts-speak "teks"`
- Wake lock: `termux-wake-lock` / `termux-wake-unlock`
- Buka file/URL: `termux-open <path|url>`

## Aturan
- Cek dulu `command -v termux-battery-status`; kalau tidak ada, sarankan
  `pkg install termux-api` dan pasang app Termux:API.
- Izin Android (lokasi, SMS, kontak) tidak bisa diberikan lewat shell; user harus
  menyetujui di dialog.
- Untuk tugas panjang, sarankan `termux-wake-lock` agar tidak dibunuh Doze.
