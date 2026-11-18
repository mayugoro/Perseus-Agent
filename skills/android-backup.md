# Android — backup & restore

Gunakan sebelum flashing, patch sistem, atau operasi berisiko.

## Backup file
- `tar -czf /sdcard/backup.tar.gz /data/data/<pkg>` (root).
- `adb backup` sudah tidak andal di Android baru; utamakan tar root.
- Backup aplikasi + data: `pm path <pkg>`, copy APK + tar data dir.

## Partisi (hati-hati)
- Cari nama: `ls -l /dev/block/by-name/`.
- Backup: `su -c "dd if=/dev/block/by-name/boot of=/sdcard/boot.img"`.
- Jangan `dd` ke partisi kecuali yakin; salah target = brick.

## Aturan
- Konfirmasi user sebelum menulis partisi.
- Simpan backup di luar /data (mis. /sdcard atau tarik ke PC).
- Catat checksum: `sha256sum`.
