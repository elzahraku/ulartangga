#!/usr/bin/env bash
# Buat & jalankan service systemd untuk Bot Ular Tangga.
#   bash systemd.sh [nama-service]     -> pasang & start (default: ulartangga)
#   bash systemd.sh remove [nama]      -> hapus service
#   DRY_RUN=1 bash systemd.sh          -> hanya tampilkan isi unit
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
DIR="$(pwd)"

ACTION="install"
if [ "${1:-}" = "remove" ]; then ACTION="remove"; shift; fi
NAME="${1:-ulartangga}"
NAME="$(echo "$NAME" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9_-' '-' | sed 's/^-*//; s/-*$//')"
[ -n "$NAME" ] || NAME="ulartangga"
UNIT="/etc/systemd/system/$NAME.service"

if [ "$ACTION" = "remove" ]; then
  [ "$(id -u)" -eq 0 ] || { echo "❌ Jalankan sebagai root."; exit 1; }
  systemctl disable --now "$NAME" 2>/dev/null || true
  rm -f "$UNIT"; systemctl daemon-reload
  echo "✅ Service $NAME dihapus."; exit 0
fi

[ -x venv/bin/python ] || { echo "❌ venv belum ada. Jalankan dulu: bash setup.sh"; exit 1; }
[ -f .env ] || { echo "❌ .env belum ada. Jalankan dulu: bash setup.sh"; exit 1; }

CONTENT="[Unit]
Description=Bot Ular Tangga ($NAME)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$DIR
ExecStart=$DIR/venv/bin/python $DIR/bot.py
Restart=always
RestartSec=5
KillSignal=SIGINT

[Install]
WantedBy=multi-user.target"

if [ "${DRY_RUN:-0}" = "1" ]; then echo "# $UNIT"; echo "$CONTENT"; exit 0; fi
[ "$(id -u)" -eq 0 ] || { echo "❌ Jalankan sebagai root: sudo bash systemd.sh"; exit 1; }

echo "$NAME" > .service_name
echo "$CONTENT" > "$UNIT"
systemctl daemon-reload
systemctl enable "$NAME" >/dev/null 2>&1
systemctl restart "$NAME"
sleep 3
systemctl --no-pager --lines=0 status "$NAME" || true
echo
echo "✅ Service '$NAME' berjalan."
echo "   Log     : journalctl -u $NAME -f"
echo "   Restart : systemctl restart $NAME"
echo "   Hapus   : bash systemd.sh remove $NAME"
