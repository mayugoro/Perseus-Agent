# Android — manage apps

Use when the user asks to list/install/uninstall/launch apps.

## List
- `android_list_apps` → `pm list packages -3` (third-party). `all=true` for all.
- `android_app_info {"package":"..."}` → version, signature, codePath, split, userId.
- Manual: `dumpsys package <pkg> | grep -E 'versionName|signatures|codePath|splitName'`.

## Install
1. `android_install {"path":"/storage/emulated/0/Download/app.apk"}`.
2. On `Failed transaction (2147483646)` or `INSTALL_FAILED_*`:
   - `termux-open "<path>"` then the user taps Install.
   - Split/XAPK/APKS → open with SAI (Split APKs Installer).
3. Don't repeat the same `pm install`; switch path.

## Uninstall / launch
- `android_uninstall {"package":"..."}` (confirm first).
- `android_launch {"package":"..."}` → `monkey -p <pkg> -c android.intent.category.LAUNCHER 1`.

## Pitfalls
- Shell `pm install` can be rejected by some ROMs; the UI installer is more reliable.
- Split APKs need every part (base + config.abi + density) with the same signature.
- Put APK files meant for other apps under `/storage/emulated/0/Download/`.
