# Android — Magisk modules

Use when creating/installing systemless Magisk modules.

## Minimal layout
```
modul/
  module.prop          # id, name, version, versionCode, author, description
  post-fs-data.sh      # optional, runs early boot
  service.sh           # optional, after boot
  system/              # systemless files (mirror of /system)
  customize.sh         # installer (optional)
```
Zip the folder contents (not the parent): `cd modul && zip -r ../modul.zip .`

## Install / manage
- `su -c "magisk --install-module /path/modul.zip"`
- `su -c "magisk --remove-modules"` (removes all, careful)
- Enable/disable: create/remove `disable` in `/data/adb/modules/<id>/`
- Logs: `/data/adb/magisk.log`, `logcat | grep magisk`
- Reboot is required to apply.

## Pitfalls
- `module.prop` id must be unique, no spaces.
- Scripts must be LF (not CRLF) and `chmod 755`.
- A wrong `system/` path can cause a bootloop; keep a `uninstall.sh` and recovery access.
- Don't store big files; /data adb quota is limited.
