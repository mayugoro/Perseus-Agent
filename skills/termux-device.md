# Termux — device control

Use for battery, notifications, clipboard, location, vibration, or TTS.

## Commands (need `pkg install termux-api` + the Termux:API app)
- Battery: `termux-battery-status`
- Notification: `termux-notification --title "..." --content "..."`
- Clipboard: `termux-clipboard-get` / `termux-clipboard-set "..."`
- Vibrate: `termux-vibrate -d 300`
- Toast: `termux-toast "message"`
- Location: `termux-location -p network` (location permission)
- TTS: `termux-tts-speak "text"`
- Wake lock: `termux-wake-lock` / `termux-wake-unlock`
- Open file/URL: `termux-open <path|url>`

## Rules
- Check `command -v termux-battery-status` first; if missing, suggest
  `pkg install termux-api` and installing the Termux:API app.
- Android permissions (location, SMS, contacts) can't be granted from shell; the
  user must approve the dialog.
- For long tasks, suggest `termux-wake-lock` to avoid Doze killing them.
