# Android/Termux — files & permissions

Use when moving files, installing APKs, or accessing storage.

## Locations
- Files run by Termux: `~/downloads/<project>/`.
- Files for other apps (APK, ZIP, media): `/storage/emulated/0/Download/`.
- Perseus workspace: `~/perseus-workspace` (file-tool jail).

## Permissions
- `termux-setup-storage` (once) for storage access.
- `/data/local/tmp` and root ops require explicit `su -c "..."`.
- Example: `su -c "cp /storage/emulated/0/Download/app.apk /data/local/tmp/app.apk"` then `su -c "chmod 644 /data/local/tmp/app.apk"`.
- Don't assume a root shell persists; prefix every root command with `su -c`.

## Inspect
- `ls -l`, `stat`, `sha256sum`, `file`, `unzip -l`.
- Read large files in chunks (`head`, `sed -n`) to avoid blowing context.

## Pitfalls
- Termux `/tmp` can be small; put big files in `~/downloads` or Download.
- Quote paths with spaces: `"/storage/emulated/0/Download/Gojek Gopay/"`.
