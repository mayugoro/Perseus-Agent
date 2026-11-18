# Termux — services, cron, background tasks

Use for periodic processes or a small server on the phone.

## Wake lock & services
- `termux-wake-lock` before long tasks; `termux-wake-unlock` after.
- `pkg install termux-services`; `sv-enable <service>`, `sv up <service>`.
- Service scripts live in `~/.termux/service/<name>/run`.

## Scheduling
- `pkg install cronie`; `crond` then `crontab -e`.
- Android alternative: `termux-job-scheduler --script <path> --period-ms 900000`.
- Job-scheduler survives reboot; plain cron does not auto-start.

## Pitfalls
- Doze kills processes; wake-lock + a foreground notification help.
- Log to a file (`>> ~/logs/task.log 2>&1`) since service output is invisible.
- Don't loop without a delay; battery and heat rise.
