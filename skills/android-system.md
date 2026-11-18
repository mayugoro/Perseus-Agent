# Android — inspect the system with dumpsys/cmd

Use for battery, activity, package, wifi, or settings status.

## Common commands
- Battery: `dumpsys battery`
- Activity: `dumpsys activity activities | head -40`
- Package: `dumpsys package <pkg>`
- WiFi: `dumpsys wifi | head -40`
- Settings: `settings get global <key>`, `settings list global`
- Properties: `getprop | grep <key>`
- Services: `service list | head`, `cmd -l`

## Control
- `am start -n <pkg>/<activity>`, `am force-stop <pkg>`
- `pm disable-user --user 0 <pkg>` (bloatware; reversible with `pm enable`)
- `cmd package resolve-activity --brief <pkg>`

## Pitfalls
- `dumpsys` output is huge; always pipe `head`/`grep` to keep context safe.
- `pm disable-user` on a system package can break features; note the package first.
