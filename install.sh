#!/usr/bin/env bash
# CodinX installer — root atau user biasa. Memasang ke prefix lokal dan membuat perintah `codinx`.
set -e
command -v python3 >/dev/null || { echo "python3 tidak ditemukan (butuh >= 3.9)."; exit 1; }
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)' || { echo "Butuh Python >= 3.9"; exit 1; }

SRC="$(cd "$(dirname "$0")" && pwd)"
if [ -n "${CODINX_INSTALL_DIR:-}" ]; then
  DEST="$CODINX_INSTALL_DIR"
elif [ "$(id -u)" = "0" ]; then
  DEST=/opt/codinx
else
  DEST="${PREFIX:-$HOME/.local}/share/codinx"
fi
if [ -n "${CODINX_BIN_DIR:-}" ]; then
  BIN_DIR="$CODINX_BIN_DIR"
elif [ "$(id -u)" = "0" ]; then
  BIN_DIR=/usr/local/bin
else
  BIN_DIR="${PREFIX:-$HOME/.local}/bin"
fi
if [ "$SRC" != "$DEST" ]; then
  mkdir -p "$DEST"
  cp -a "$SRC"/. "$DEST"/
fi
chmod +x "$DEST/bin/codinx"
[ -f "$DEST/.env" ] && chmod 600 "$DEST/.env"
[ -f "$DEST/api.py" ] && chmod 600 "$DEST/api.py"
mkdir -p "$BIN_DIR"
# pembungkus (bukan symlink): jalan di Termux walau /usr/bin/env tidak ada
SH="$(command -v sh)"
printf '#!%s\nexec python3 "%s/bin/codinx" "$@"\n' "$SH" "$DEST" > "$BIN_DIR/codinx"
chmod +x "$BIN_DIR/codinx"
echo "✓ CodinX terpasang di $DEST. Jalankan: codinx"
case ":${PATH}:" in *":$BIN_DIR:"*) ;; *) echo "Tambahkan ke PATH jika perlu: export PATH=\"$BIN_DIR:\$PATH\"" ;; esac
