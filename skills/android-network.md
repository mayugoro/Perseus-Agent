# Android — network & diagnostics

Use to check connectivity, ports, DNS, proxy, or traffic.

## Status
- `ip addr`, `ip route`, `getprop | grep -i dns`.
- `ss -ltnp` (root) for listening ports + process.
- `ping -c 3 8.8.8.8`, `curl -I https://...`.

## Traffic capture (root)
- `su -c "tcpdump -i any -w /sdcard/cap.pcap"` (needs tcpdump).
- Proxy: `settings put global http_proxy 127.0.0.1:8080` (clear with `:0`).
- iptables redirect needs root and care; save original rules first.

## Pitfalls
- Android 10+ restricts `/proc/net`; use `ss` as root.
- A system VPN/proxy may stop tcpdump from seeing plaintext.
- Don't enable a global proxy without telling the user; it can cut app connectivity.
