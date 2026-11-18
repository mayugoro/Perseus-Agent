# Android — modul LSPosed (Xposed)

Gunakan saat membuat/mendebug modul Xposed untuk app tertentu.

## Struktur modul
```
AndroidManifest.xml  # meta-data xposedmodule, xposeddescription, xposedminversion
assets/xposed_init   # nama kelas implementasi IXposedHookLoadPackage
classes.dex          # compile dengan android.jar + stub API
```
- Build tanpa Gradle: `aapt2 link` → tambah classes.dex + assets → zipalign → apksigner.
- Stub API LSPosed diperlukan saat compile; runtime disediakan LSPosed.

## Pola hook
- Filter package: `if (!lpp.packageName.equals(TARGET)) return;`
- `XposedBridge.hookAllMethods(cls, "nama", cb)`; log via `XposedBridge.log`.
- Hook method native sering tidak stabil → utamakan Java, hindari hook native.
- Jangan hook terlalu awal sebelum classloader siap.

## Pitfall
- Modul harus di-enable + scope dicentang; force-stop app setelah mengubah scope.
- DenyList + Enforce ON membuat Zygisk tidak menyuntik → modul tidak muncul di log.
- Log modul: `logcat | grep -E 'LSPosed|NamaModul'`.
- Signature APK modul tidak perlu sama dengan target.
