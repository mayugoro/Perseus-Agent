# Android — inspeksi sistem dengan dumpsys/cmd

Gunakan saat butuh status baterai, activity, package, wifi, settings.

## Perintah umum
- Baterai: `dumpsys battery`
- Activity: `dumpsys activity activities | head -40`
- Paket: `dumpsys package <pkg>`
- WiFi: `dumpsys wifi | head -40`
- Settings: `settings get global <key>`, `settings list global`
- Properti: `getprop | grep <key>`
- Service: `service list | head`, `cmd -l`

## Kontrol
- `am start -n <pkg>/<activity>`, `am force-stop <pkg>`
- `pm disable-user --user 0 <pkg>` (bloatware; reversible dengan `pm enable`)
- `cmd package resolve-activity --brief <pkg>`

## Pitfall
- `dumpsys` bisa sangat panjang; selalu pipe `head`/`grep` agar context aman.
- `pm disable-user` pada paket sistem bisa merusak fitur; catat paket sebelum disable.
