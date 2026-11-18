# Android — kelola aplikasi

Gunakan saat user minta lihat/install/uninstall/buka aplikasi di HP.

## Lihat
- `android_list_apps` → `pm list packages -3` (third-party). `all=true` untuk semua.
- `android_app_info {"package":"..."}` → versi, signature, codePath, split, userId.
- Detail manual: `dumpsys package <pkg> | grep -E 'versionName|signatures|codePath|splitName'`.

## Install
1. Coba `android_install {"path":"/storage/emulated/0/Download/app.apk"}`.
2. Kalau `Failed transaction (2147483646)` atau `INSTALL_FAILED_*`:
   - `termux-open "/storage/emulated/0/Download/app.apk"` → user ketuk Install.
   - Split/XAPK/APKS → buka dengan SAI (Split APKs Installer).
3. Jangan ulangi `pm install` yang sama berkali-kali; pindah jalur.

## Uninstall / buka
- `android_uninstall {"package":"..."}` (konfirmasi dulu).
- `android_launch {"package":"..."}` → `monkey -p <pkg> -c android.intent.category.LAUNCHER 1`.

## Pitfall
- `pm install` dari shell kadang ditolak PackageManager ROM tertentu; installer UI lebih pasti.
- APK split wajib semua bagian (base + config.abi + density) dengan signature sama.
- File APK untuk dipakai di luar Termux taruh di `/storage/emulated/0/Download/`.
