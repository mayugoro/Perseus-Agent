# Android — logs, crashes, process status

Use when an app force-closes, "exits", or the user asks for a diagnosis.

## Basic logs
- `android_logcat {"lines":200}` → `logcat -d -t 200`.
- Filter: `android_logcat {"filter":"neobiz|FATAL|AndroidRuntime","lines":300}`.
- Crash buffer: `logcat -b crash -d | tail -80` via `shell`.
- System kills: `logcat -b system -d | grep -i "Killing <pkg>"`.

## Crash vs self-exit
- `dumpsys activity exit-info <pkg> | head -30`
  - `reason=1 (EXIT_SELF)` → code exited itself.
  - `reason=5 (APP CRASH(NATIVE))` + `status=11` → native SIGSEGV.
  - `reason=4 (CRASH)` → Java exception (see crash buffer).
- Tombstone: `ls -lt /data/tombstones | head -3`, then `head -60` of the newest
  (root; look for `name: ... >>> <pkg> <<<` and the lib backtrace).

## Pitfalls
- `logcat -d` may truncate; also grab `-b crash` separately.
- The `FATAL EXCEPTION` first line often lacks the cause; look for `Caused by:` or
  the line after `Process:`.
- Don't conclude "root detection" before seeing reason + backtrace.
