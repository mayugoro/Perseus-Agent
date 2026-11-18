# Android — runtime instrumentation (hooks & anti-detection)

Use to read an app's runtime behavior.

## Java hooks
- Enumerate: `Java.enumerateLoadedClasses`, `Java.choose('cls', {onMatch})`.
- Method: `C.method.overload('java.lang.String').implementation = function(s){...}`.
- Constructor, static fields, and `ClassLoader` (app vs boot) are common error sources.

## Native hooks
- `Module.findExportByName(lib, sym)`, `Interceptor.attach`.
- For static/stripped functions: `Module.enumerateSymbols` or offsets from
  `readelf`/IDA; verify the base address in maps.
- Hook `dlopen`/`dlsym` to see loaded libraries.

## Anti-detection
- Root: check `su` paths, `Build.TAGS`, `ro.debuggable`, mounts; hook consistently.
- Frida: checks process/port/maps; renamed variants (hluda/Florida) help, not guarantee.
- Debugger: `Debug.isDebuggerConnected`, `ptrace`; hook both Java and native.
- Integrity: signature/dex/so hashes; don't patch resources randomly.

## Pitfalls
- Hook after the lib is loaded; wait for `dlopen` or finish `Java.perform`.
- One wrong argument type crashes the app; start with logging only.
- Always log stack/errno; don't guess return values.
