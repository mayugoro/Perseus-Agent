# Android — dasar root & keamanan operasi

Gunakan saat butuh akses root, cek Magisk, atau operasi sistem.

## Cek status
- `su -c id` → harus `uid=0`.
- `magisk -V`, `magisk --sqlite "select * from settings"` (denylist_enforce).
- `getprop ro.build.version.release`, `getprop ro.product.model`.
- `ls /data/adb` → magisk, modules, lspd.

## Aturan wajib
- Setiap perintah root eksplisit: `su -c "..."`; jangan berharap shell root bertahan.
- Operasi destruktif (`rm -rf /data`, `dd of=/dev/block`, `pm clear`, format)
  **wajib konfirmasi user** dan sebutkan risikonya.
- Backup dulu file/partisi sebelum menimpa.
- Jangan mengubah `/system` langsung; utamakan systemless (Magisk module).

## Diagnosa
- `dmesg | tail`, `logcat -b all -d | tail`, `dumpsys` untuk status service.
- `ps -A -o PID,NAME,ARGS | grep <nama>`.
- `ss -ltnp` / `netstat -ltnp` untuk port.
