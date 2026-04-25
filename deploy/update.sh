#!/usr/bin/env bash
# ============================================================
# Market Mega — Yangilanishni serverga tortish
# ============================================================
# Foydalanish: sudo bash /opt/marketmega/deploy/update.sh
# ============================================================
set -euo pipefail

APP_DIR="/opt/marketmega"
APP_USER="marketmega"

GREEN='\033[0;32m'
NC='\033[0m'
log() { echo -e "${GREEN}==>${NC} $1"; }

if [ "$(id -u)" -ne 0 ]; then
    echo "Sudo bilan ishga tushiring"; exit 1
fi

cd "$APP_DIR"

log "Git'dan yangi kodni tortish..."
sudo -u "$APP_USER" git fetch origin
sudo -u "$APP_USER" git reset --hard origin/main

log "Dependency'larni yangilash..."
sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install -r requirements.txt --quiet

log "Migratsiyalarni qo'llash..."
sudo -u "$APP_USER" "$APP_DIR/venv/bin/alembic" upgrade head

log "Servisni qayta ishga tushirish..."
systemctl restart marketmega
sleep 3
systemctl is-active --quiet marketmega && log "✓ Yangilash muvaffaqiyatli" || {
    echo "Service ishga tushmadi:"
    journalctl -u marketmega -n 30 --no-pager
    exit 1
}
