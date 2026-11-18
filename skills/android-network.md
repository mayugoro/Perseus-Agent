# Android — jaringan & diagnostik

Gunakan saat cek koneksi, port, DNS, proxy, atau traffic.

## Status
- `ip addr`, `ip route`, `getprop | grep -i dns`.
- `ss -ltnp` (root) untuk port listening + proses.
- `ping -c 3 8.8.8.8`, `curl -I https://...`.

## Tangkap traffic (root)
- `su -c "tcpdump -i any -w /sdcard/cap.pcap"` (butuh tcpdump).
- Proxy lokal: `settings put global http_proxy 127.0.0.1:8080` (hapus dengan `:0`).
- iptables redirect butuh root dan hati-hati; simpan aturan asli sebelum mengubah.

## Pitfall
- Android 10+ membatasi akses `/proc/net`; gunakan `ss` dengan root.
- VPN/proxy sistem bisa membuat tcpdump tidak melihat plaintext.
- Jangan menyalakan proxy global tanpa memberi tahu user; bisa memutus koneksi app.
