# Android — dump dex / native dari memori

Gunakan saat APK terproteksi (packer) dan dex asli hanya ada di memori.

## Prasyarat
- Root + process target hidup.
- `PID=$(pidof <pkg>)`; cek `cat /proc/$PID/maps | grep -E 'dex|oat|so'`.

## Dump dex manual
1. Lihat mapping: `grep -E '\.dex|dalvik' /proc/$PID/maps`.
2. Ambil rentang `start-end` yang relevan:
   `dd if=/proc/$PID/mem of=/sdcard/dump.bin bs=1 skip=$((0xSTART)) count=$((0xEND-0xSTART))`
   (butuh root; `skip` desimal).
3. Cari magic `dex\n035` di hasil, potong per header dex (offset+size di header).
4. Validasi: `dexdump`/jadx; dex rusak bisa diperbaiki header checksum.

## Tool praktis
- Frida script dump dex (cari `DexDump`, `frida-dexdump`): `pip install frida-dexdump`,
  `frida-dexdump -U -f <pkg>`.
- Native lib dump: cari `r-xp` segment `.so` di maps, `dd` rentang, simpan `.so`,
  lalu `readelf -h` untuk validasi.
- `gcore` (gdb) bisa membuat core dump penuh; berat di HP.

## Pitfall
- Packer sering menghapus dex dari disk; dump harus saat app sudah decrypt.
- Jangan dump saat app background (memori bisa di-reclaim).
- File dump besar: taruh di `/sdcard` atau tarik ke PC, bukan workspace.
