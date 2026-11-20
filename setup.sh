#!/usr/bin/env bash
# Setup Bot Ular Tangga: venv + dependensi + .env + (opsional) nginx & HTTPS.
# Jalankan:  bash setup.sh
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
DIR="$(pwd)"

c() { printf '\033[%sm%s\033[0m\n' "$1" "$2"; }
log() { c 36 "▶ $*"; }
ok() { c 32 "✅ $*"; }
warn() { c 33 "⚠️  $*"; }
die() { c 31 "❌ $*"; exit 1; }
ask() { local p="$1" d="${2:-}" v; read -rp "$p${d:+ [$d]}: " v; echo "${v:-$d}"; }

[ "$(id -u)" -eq 0 ] || die "Jalankan sebagai root: sudo bash setup.sh"

# ── 1. Paket sistem ──────────────────────────────────────────
log "Memasang paket sistem..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip curl >/dev/null
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' \
  || die "Butuh Python 3.10+ (Ubuntu 22.04/24.04 cocok)."

# ── 2. Virtualenv + dependensi ───────────────────────────────
log "Membuat venv & memasang dependensi (venv terpisah dari bot lain)..."
[ -d venv ] || python3 -m venv venv
venv/bin/pip install -q --upgrade pip
venv/bin/pip install -q -r requirements.txt
ok "Dependensi terpasang."

# ── 3. File .env ─────────────────────────────────────────────
if [ -f .env ] && [ "$(ask 'File .env sudah ada. Timpa? (y/n)' n)" != "y" ]; then
  ok ".env dipertahankan."
else
  echo; log "Isi konfigurasi bot (API_ID/API_HASH dari my.telegram.org, token dari @BotFather)"
  API_ID=$(ask "API_ID")
  API_HASH=$(ask "API_HASH")
  BOT_TOKEN=$(ask "BOT_TOKEN")
  DOMAIN=$(ask "Domain mini app (KOSONGKAN jika tidak punya domain -> otomatis pakai IP VPS via sslip.io)" "")
  [ -n "$API_ID" ] && [ -n "$API_HASH" ] && [ -n "$BOT_TOKEN" ] || die "API_ID, API_HASH, dan BOT_TOKEN wajib diisi."
  if [ -z "$DOMAIN" ]; then
    VPSIP=$(curl -fsS4 https://api.ipify.org 2>/dev/null) || die "Gagal mendeteksi IP publik VPS."
    DOMAIN="${VPSIP//./-}.sslip.io"
    ok "Memakai alamat otomatis: $DOMAIN (mengarah ke $VPSIP)"
  fi
  DOMAIN="${DOMAIN#http://}"; DOMAIN="${DOMAIN#https://}"; DOMAIN="${DOMAIN%%/*}"
  PORT=8095
  while ss -ltn "sport = :$PORT" 2>/dev/null | grep -q LISTEN; do PORT=$((PORT+1)); done
  warn "Port $PORT dipakai bot ini (otomatis memilih port yang kosong)."
  SHORT=$(ask "MINIAPP_SHORTNAME dari BotFather /newapp (kosongkan jika belum ada)" "")
  MINP=$(ask "Minimal pemain untuk mulai" 2)
  umask 077
  cat > .env <<ENV
API_ID=$API_ID
API_HASH=$API_HASH
BOT_TOKEN=$BOT_TOKEN
BASE_URL=https://$DOMAIN
PORT=$PORT
MINIAPP_SHORTNAME=$SHORT
MIN_PLAYERS=$MINP
ENV
  ok ".env dibuat."
fi

set -a; . ./.env; set +a
DOMAIN="${BASE_URL#https://}"

# ── 4. nginx + HTTPS (opsional) ──────────────────────────────
if [ "$(ask "Pasang nginx + sertifikat HTTPS untuk $DOMAIN sekarang? (y/n)" y)" = "y" ]; then
  MYIP=$(curl -fsS4 https://api.ipify.org 2>/dev/null || true)
  DNSIP=$(getent ahostsv4 "$DOMAIN" 2>/dev/null | awk 'NR==1{print $1}' || true)
  if [ -n "$MYIP" ] && [ "$MYIP" != "$DNSIP" ]; then
    warn "DNS $DOMAIN -> '${DNSIP:-belum ada}', IP VPS ini $MYIP."
    [ "$(ask 'Lanjut juga? (y/n)' n)" = "y" ] || die "Arahkan DNS dulu, lalu jalankan bash setup.sh lagi."
  fi
  log "Memasang nginx & certbot..."
  apt-get install -y -qq nginx certbot python3-certbot-nginx >/dev/null
  CONF="/etc/nginx/sites-available/ulartangga-$DOMAIN"
  cat > "$CONF" <<NGX
server {
    listen 80;
    server_name $DOMAIN;
    location / {
        proxy_pass http://127.0.0.1:$PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-For \$remote_addr;
        proxy_read_timeout 60s;
    }
}
NGX
  ln -sf "$CONF" "/etc/nginx/sites-enabled/ulartangga-$DOMAIN"
  nginx -t || die "Konfigurasi nginx error, cek $CONF"
  systemctl reload nginx
  EMAIL=$(ask "Email untuk sertifikat Let's Encrypt")
  certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m "$EMAIL" --redirect \
    && ok "HTTPS aktif: https://$DOMAIN" \
    || warn "Certbot gagal. Pastikan DNS sudah mengarah ke VPS & port 80/443 terbuka, lalu ulangi: certbot --nginx -d $DOMAIN"
else
  warn "Lewati nginx. Pastikan $BASE_URL (https) sudah diarahkan ke 127.0.0.1:$PORT."
fi

# ── 5. Selesai ───────────────────────────────────────────────
echo; ok "Setup selesai."
if [ "$(ask 'Jalankan sebagai service systemd sekarang? (y/n)' y)" = "y" ]; then
  bash systemd.sh
else
  echo "Nanti jalankan:  bash systemd.sh   (atau tes manual: venv/bin/python bot.py)"
fi
