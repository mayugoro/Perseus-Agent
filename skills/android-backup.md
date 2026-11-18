# Android — backup & restore

Use before flashing, patching system, or any risky operation.

## File backup
- `tar -czf /sdcard/backup.tar.gz /data/data/<pkg>` (root).
- `adb backup` is unreliable on modern Android; prefer root tar.
- Back up app + data: `pm path <pkg>`, copy the APK and tar the data dir.

## Partitions (careful)
- Find names: `ls -l /dev/block/by-name/`.
- Back up: `su -c "dd if=/dev/block/by-name/boot of=/sdcard/boot.img"`.
- Never `dd` to a partition unless sure; wrong target = brick.

## Rules
- Confirm with the user before writing a partition.
- Keep backups outside /data (e.g. /sdcard or pull to PC).
- Record checksums: `sha256sum`.
