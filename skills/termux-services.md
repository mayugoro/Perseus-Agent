# Termux — service, cron, dan tugas latar

Gunakan saat menjalankan proses periodik atau server kecil di HP.

## Wake lock & service
- `termux-wake-lock` sebelum tugas panjang; `termux-wake-unlock` setelah.
- `pkg install termux-services`; `sv-enable <service>`, `sv up <service>`.
- Service script di `~/.termux/service/<nama>/run`.

## Jadwal
- `pkg install cronie`; `crond` lalu `crontab -e`.
- Alternatif Android: `termux-job-scheduler --script <path> --period-ms 900000`.
- Job scheduler bertahan setelah reboot; cron biasa tidak otomatis.

## Pitfall
- Doze membunuh proses; wake-lock + notification foreground membantu.
- Log ke file (`>> ~/logs/task.log 2>&1`) karena output service tidak terlihat.
- Jangan menjalankan loop tanpa jeda; baterai dan suhu naik.
