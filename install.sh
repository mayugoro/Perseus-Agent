#!/data/data/com.termux/files/usr/bin/bash
set -e
cd "$(dirname "$0")"

pkg install -y python git
python3 -m pip install --quiet --upgrade prompt_toolkit || true

python3 perseus.py --init

PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
cat > "$PREFIX/bin/perseus" <<LAUNCH
#!/data/data/com.termux/files/usr/bin/bash
exec python3 "$(pwd)/perseus.py" "\$@"
LAUNCH
chmod +x "$PREFIX/bin/perseus"

echo
echo "Selesai. Jalankan: perseus"
