#!/data/data/com.termux/files/usr/bin/bash
set -e
cd "$(dirname "$0")"

echo "== Perseus installer =="
pkg update -y || true
pkg install -y python git expat

# dependency Python (prompt_toolkit untuk completion)
python3 -m pip install --quiet --upgrade pip || true
python3 -m pip install --quiet -r requirements.txt \
  || python3 -m pip install --quiet prompt_toolkit || true

# cek pyexpat (dipakai prompt_toolkit di sebagian build Termux)
if ! python3 -c "import pyexpat" >/dev/null 2>&1; then
  echo "PERINGATAN: pyexpat bermasalah. Jalankan: pkg reinstall python"
fi

python3 perseus.py --init

PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
cat > "$PREFIX/bin/perseus" <<LAUNCH
#!/data/data/com.termux/files/usr/bin/bash
exec python3 "$(pwd)/perseus.py" "\$@"
LAUNCH
chmod +x "$PREFIX/bin/perseus"

echo
echo "Selesai. Jalankan: perseus"
