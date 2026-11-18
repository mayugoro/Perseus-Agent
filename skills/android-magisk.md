# Android — modul Magisk

Gunakan saat membuat/memasang modul Magisk systemless.

## Struktur minimal
```
modul/
  module.prop          # id, name, version, versionCode, author, description
  post-fs-data.sh      # opsional, jalan awal boot
  service.sh           # opsional, setelah boot
  system/              # file systemless (mirror /system)
  customize.sh         # installer (opsional)
```
Zip isi folder (bukan folder induk): `cd modul && zip -r ../modul.zip .`

## Pasang / kelola
- `su -c "magisk --install-module /path/modul.zip"`
- `su -c "magisk --remove-modules"` (hapus semua, hati-hati)
- Enable/disable: buat/hapus `disable` di `/data/adb/modules/<id>/`
- Log: `/data/adb/magisk.log`, `logcat | grep magisk`
- Reboot diperlukan untuk apply.

## Pitfall
- `module.prop` id harus unik, tanpa spasi.
- Script harus LF (bukan CRLF) dan `chmod 755`.
- Salah path di system/ bisa bootloop; sediakan `uninstall.sh` dan akses recovery.
- Jangan menaruh file besar; /data adb quota terbatas.
