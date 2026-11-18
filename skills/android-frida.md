# Android — Frida for dynamic analysis

Use when runtime inspection is needed (not HAR capture).

## Install
- Root: push `frida-server` for the right ABI to `/data/local/tmp`, `chmod 755`, run `su -c "/data/local/tmp/frida-server -D &"`.
- Client: `pip install frida-tools`; check `frida-ps -U`.
- Spawn: `frida -U -f <pkg> -l hook.js --no-pause`.

## Hook patterns
- Java: `Java.perform(() => { const C = Java.use('...'); C.method.implementation = function(...) {...}; });`
- Native: `Interceptor.attach(Module.findExportByName('libx.so','func'), {...})`.
- Enumerate classes: `Java.enumerateLoadedClasses({onMatch: n => ...})`.
- SSL unpin: hook `X509TrustManager` / `SSLContext`; Flutter needs a native BoringSSL patch, not a Java hook.

## Pitfalls
- Anti-tamper detects frida-server (process name/port/maps); stop it and reboot when done.
- Frida 17 has no Java bridge by default; compile with frida-compile for Java scripts.
- Don't leave frida-server running while a production app is in use.
