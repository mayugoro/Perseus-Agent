# Android — root basics & safe operations

Use when root access, Magisk checks, or system operations are needed.

## Status
- `su -c id` → must be `uid=0`.
- `magisk -V`, `magisk --sqlite "select * from settings"` (denylist_enforce).
- `getprop ro.build.version.release`, `getprop ro.product.model`.
- `ls /data/adb` → magisk, modules, lspd.

## Hard rules
- Prefix every root command: `su -c "..."`; don't assume a persistent root shell.
- Destructive ops (`rm -rf /data`, `dd of=/dev/block`, `pm clear`, format)
  require user confirmation and stated risk.
- Back up files/partitions before overwriting.
- Don't touch `/system` directly; prefer systemless (Magisk module).

## Diagnosis
- `dmesg | tail`, `logcat -b all -d | tail`, `dumpsys` for service state.
- `ps -A -o PID,NAME,ARGS | grep <name>`.
- `ss -ltnp` / `netstat -ltnp` for ports.
