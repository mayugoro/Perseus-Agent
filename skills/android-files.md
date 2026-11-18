# Android/Termux — file & izin

Gunakan saat memindahkan file, install APK, atau akses storage.

## Lokasi
- File yang dijalankan Termux: `~/downloads/<projek>/`.
- File untuk aplikasi lain (APK, ZIP, media): `/storage/emulated/0/Download/`.
- Workspace Perseus: `~/perseus-workspace` (jail tool file).

## Izin
- Akses storage: `termux-setup-storage` (sekali).
- `/data/local/tmp` dan operasi root wajib `su -c "..."` eksplisit.
- Contoh aman:
  `su -c "cp /storage/emulated/0/Download/app.apk /data/local/tmp/app.apk"`
  `su -c "chmod 644 /data/local/tmp/app.apk"`
- Jangan mengandalkan shell root dari perintah sebelumnya; tiap perintah pakai `su -c`.

## Cek file
- `ls -l`, `stat`, `sha256sum`, `file`, `unzip -l`.
- Baca file besar bertahap (`head`, `sed -n`) agar context tidak meledak.

## Pitfall
- `/tmp` Termux bisa kecil; file besar taruh di `~/downloads` atau Download.
- Path dengan spasi harus dikutip: `"/storage/emulated/0/Download/Gojek Gopay/"`.
