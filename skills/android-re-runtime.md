# Android — instrumentasi runtime (hook & anti-detection)

Gunakan saat perlu membaca perilaku app saat berjalan.

## Java hook
- Enumerasi: `Java.enumerateLoadedClasses`, `Java.choose('cls', {onMatch})`.
- Method: `C.method.overload('java.lang.String').implementation = function(s){...}`.
- Constructor, field statis, dan `ClassLoader` (app vs boot) sering jadi sumber error.

## Native hook
- `Module.findExportByName(lib, sym)`, `Interceptor.attach`.
- Untuk fungsi statis/stripped: cari via `Module.enumerateSymbols` atau offset dari
  `readelf`/IDA; verifikasi base address di maps.
- `dlopen`/`dlsym` hook untuk melihat library yang dimuat.

## Anti-detection
- Root: cek `su` path, `Build.TAGS`, `ro.debuggable`, mounts; hook konsisten.
- Frida: cek proses/port/maps; varian rename (hluda/Florida) membantu, bukan jaminan.
- Debugger: `Debug.isDebuggerConnected`, `ptrace`; hook di Java dan native.
- Integrity: signature/hash dex/so; jangan patch resource sembarangan.

## Pitfall
- Hook native saat lib belum dimuat → tunggu `dlopen` atau `Java.perform` selesai.
- Satu hook salah tipe argumen membuat app crash; mulai dari log saja.
- Selalu log stack/errno; jangan menebak nilai balik.
