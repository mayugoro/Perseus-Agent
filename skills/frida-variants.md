# Frida — variants & gadget (hluda, Florida, Arida)

Use when plain frida-server is detected by anti-tamper.

## Common variants
- **frida-server** official: easiest to detect (process name/port/maps).
- **hluda-server**: renamed frida-server (strings/port changed) to reduce signature
  detection; API behavior is the same.
- **Florida**: a Frida fork with stealth patches (name/port/paths), good for apps
  with basic Frida detection. Clients remain frida-tools.
- **Arida**: another fork/rename; verify `--version` and client-protocol
  compatibility first — don't assume.
- **frida-gadget**: `libfrida-gadget.so` embedded into the APK; loaded via
  `System.loadLibrary` or `libfrida-gadget.config`. No frida-server process.

## Gadget (repack)
1. Put `libfrida-gadget.so` in `lib/<abi>/`.
2. Add `libfrida-gadget.config` (listen/interaction).
3. Make sure code loads it (`System.loadLibrary("frida-gadget")` or `dlopen`), repack + re-sign.
4. Attach: `frida -U -n Gadget`.

## Pitfalls
- Repacking changes the signature → integrity checks may reject.
- Some apps scan `maps` for `frida`/`gadget`; renaming the file is not enough.
- Stop Frida-variant processes when done; don't leave them on for production apps.
- Frida 17 without Java bridge: compile with frida-compile when needed.
