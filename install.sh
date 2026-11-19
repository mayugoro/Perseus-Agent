#!/data/data/com.termux/files/usr/bin/bash
set -e
cd "$(dirname "$0")"

echo "== Perseus installer =="
pkg update -y || true
pkg install -y python git expat nodejs

# dependency Python (prompt_toolkit untuk completion)
python3 -m pip install --quiet --upgrade pip || true
python3 -m pip install --quiet -r requirements.txt \
  || python3 -m pip install --quiet prompt_toolkit || true

# kunci ukuran font Termux agar tidak berubah (pinch/zoom)
mkdir -p "$HOME/.termux"
touch "$HOME/.termux/termux.properties"
grep -q "^terminal-font-size" "$HOME/.termux/termux.properties" || \
  echo "terminal-font-size = 12" >> "$HOME/.termux/termux.properties"
termux-reload-settings 2>/dev/null || true

# cek pyexpat (dipakai prompt_toolkit di sebagian build Termux)
if ! python3 -c "import pyexpat" >/dev/null 2>&1; then
  echo "PERINGATAN: pyexpat bermasalah. Jalankan: pkg reinstall python"
fi

# Web UI (TypeScript + Node.js)
if command -v npm >/dev/null 2>&1; then
  echo "== build Web UI =="
  ( cd desktop && npm install --silent && npm run build --silent ) \
    || echo "PERINGATAN: build Web UI gagal (cek: pkg install nodejs)"
fi

python3 perseus.py --init

PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
cat > "$PREFIX/bin/perseus" <<LAUNCH
#!/data/data/com.termux/files/usr/bin/bash
exec python3 "$(pwd)/perseus.py" "\$@"
LAUNCH
chmod +x "$PREFIX/bin/perseus"

cat > "$PREFIX/bin/perseus-web" <<LAUNCH
#!/data/data/com.termux/files/usr/bin/bash
cd "$(pwd)/desktop" || exit 1
if [ ! -f dist/server.js ]; then
  npm install --silent && npm run build --silent || exit 1
fi
exec node dist/server.js "\$@"
LAUNCH
chmod +x "$PREFIX/bin/perseus-web"

echo
echo "Selesai."
echo "  CLI   : perseus"
echo "  Web UI: perseus-web   →  http://127.0.0.1:8787"
