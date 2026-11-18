# Android — dump dex / native from memory

Use for protected (packed) apps whose original dex only exists in memory.

## Prerequisites
- Root + a running target process.
- `PID=$(pidof <pkg>)`; `cat /proc/$PID/maps | grep -E 'dex|oat|so'`.

## Manual dex dump
1. `grep -E '\.dex|dalvik' /proc/$PID/maps`.
2. Copy a range: `dd if=/proc/$PID/mem of=/sdcard/dump.bin bs=1 skip=$((0xSTART)) count=$((0xEND-0xSTART))` (root; skip is decimal).
3. Find `dex\n035` magic, split per dex header (offset+size in header).
4. Validate with `dexdump`/jadx; repair header checksums if broken.

## Practical tools
- Frida dex dump scripts (`frida-dexdump`): `pip install frida-dexdump`, `frida-dexdump -U -f <pkg>`.
- Native lib dump: find the `r-xp` `.so` segment in maps, `dd` the range, save `.so`, `readelf -h` to validate.
- `gcore` (gdb) makes a full core dump; heavy on phones.

## Pitfalls
- Packers often remove dex from disk; dump only after decryption.
- Don't dump while backgrounded (memory may be reclaimed).
- Write large dumps to /sdcard and pull to PC, not the workspace.
