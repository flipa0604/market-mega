#!/usr/bin/env bash
# ============================================================
# Market Mega — Ubuntu serverda avtomatik deploy
# ============================================================
# Server talablari: Ubuntu 22.04+ / Debian 12+
# Root yoki sudo huquqi kerak.
#
# Foydalanish:
#   1. Repository'ni klonlang:    git clone <repo> /opt/marketmega
#   2. .env yarating:              cp /opt/marketmega/.env.example /opt/marketmega/.env
#   3. .env'ni to'ldiring:         nano /opt/marketmega/.env
#   4. Skriptni ishga tushiring:   sudo bash /opt/marketmega/deploy/deploy.sh
#   5. SSL o'rnating:              sudo bash /opt/marketmega/deploy/deploy.sh ssl
# ============================================================
set -euo pipefail

# ---------- Sozlamalar ----------
APP_USER="marketmega"
APP_DIR="/opt/marketmega"
DB_NAME="marketmega"
DB_USER="marketmega"
PYTHON="python3"

# Rang
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${GREEN}==>${NC} $1"; }
warn() { echo -e "${YELLOW}!!${NC} $1"; }
err() { echo -e "${RED}xx${NC} $1"; exit 1; }

# Root tekshirish
if [ "$(id -u)" -ne 0 ]; then
    err "Bu skript root yoki sudo bilan ishga tushirilishi kerak"
fi

# Ish katalogi tekshirish
if [ ! -d "$APP_DIR" ]; then
    err "$APP_DIR mavjud emas. Avval kodni klonlang: git clone <repo> $APP_DIR"
fi

if [ ! -f "$APP_DIR/.env" ]; then
    err ".env fayl topilmadi: $APP_DIR/.env. Avval .env.example'dan nusxa oling."
fi


# ============================================================
# SSL alohida buyruq (deploy.sh ssl)
# ============================================================
if [ "${1:-}" = "ssl" ]; then
    log "Let's Encrypt SSL sertifikatini olish..."

    DOMAIN=$(grep -E '^WEBAPP_URL=' "$APP_DIR/.env" | sed -E 's|.*://||; s|/.*||' | head -1)
    if [ -z "$DOMAIN" ]; then
        err "WEBAPP_URL'dan domain'ni o'qiy olmadim. .env'ni tekshiring."
    fi

    log "Domain: $DOMAIN"

    apt-get install -y certbot python3-certbot-nginx
    mkdir -p /var/www/certbot

    certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email --redirect

    systemctl reload nginx
    log "SSL muvaffaqiyatli o'rnatildi: https://$DOMAIN"
    exit 0
fi


# ============================================================
# 1. Tizim paketlari
# ============================================================
log "Tizim paketlarini o'rnatish..."
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y \
    python3 python3-venv python3-dev \
    postgresql postgresql-contrib \
    nginx \
    build-essential libpq-dev \
    git curl


# ============================================================
# 2. PostgreSQL DB va user
# ============================================================
log "PostgreSQL sozlash..."

DB_PASS=$(grep -E '^DATABASE_URL=' "$APP_DIR/.env" | sed -E 's|.*://[^:]+:([^@]+)@.*|\1|')
if [ -z "$DB_PASS" ] || [ "$DB_PASS" = "STRONG_PASSWORD" ]; then
    err "DATABASE_URL parolda STRONG_PASSWORD turibdi. .env'ni tahrirlang!"
fi

# DB user yaratish (agar mavjud bo'lmasa)
sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASS';"

# Parolni yangilash (agar o'zgargan bo'lsa)
sudo -u postgres psql -c "ALTER USER $DB_USER WITH PASSWORD '$DB_PASS';" >/dev/null

# Database yaratish
sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"


# ============================================================
# 3. App user va papka huquqlari
# ============================================================
log "App user yaratish: $APP_USER"
id -u "$APP_USER" &>/dev/null || useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin "$APP_USER"

mkdir -p "$APP_DIR/app/static/uploads"
chown -R "$APP_USER:$APP_USER" "$APP_DIR"
chmod 600 "$APP_DIR/.env"
chmod 750 "$APP_DIR/app/static/uploads"


# ============================================================
# 4. Python virtual environment + paketlar
# ============================================================
log "Python virtual environment..."

if [ ! -d "$APP_DIR/venv" ]; then
    sudo -u "$APP_USER" $PYTHON -m venv "$APP_DIR/venv"
fi

sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install --upgrade pip
sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt"


# ============================================================
# 5. Database migratsiyasi
# ============================================================
log "Alembic migratsiyalarini ishga tushirish..."
cd "$APP_DIR"
sudo -u "$APP_USER" "$APP_DIR/venv/bin/alembic" upgrade head


# ============================================================
# 6. Systemd service
# ============================================================
log "Systemd service o'rnatish..."
cp "$APP_DIR/deploy/marketmega.service" /etc/systemd/system/marketmega.service
systemctl daemon-reload
systemctl enable marketmega
systemctl restart marketmega

sleep 3
if systemctl is-active --quiet marketmega; then
    log "Systemd service ishlayapti ✓"
else
    warn "Service ishga tushmadi. Logni ko'ring: journalctl -u marketmega -n 50"
fi


# ============================================================
# 7. Nginx konfiguratsiya
# ============================================================
log "Nginx sozlash..."

DOMAIN=$(grep -E '^WEBAPP_URL=' "$APP_DIR/.env" | sed -E 's|.*://||; s|/.*||' | head -1)
if [ -z "$DOMAIN" ]; then
    err "WEBAPP_URL'dan domain'ni o'qiy olmadim"
fi

# Nginx config'ni domain bilan to'ldirish
sed "s|your-domain.com|$DOMAIN|g" "$APP_DIR/deploy/nginx.conf" > /etc/nginx/sites-available/marketmega

# SSL bloki Let's Encrypt sertifikati bo'lmasa nginx -t xato beradi
# Shuning uchun avval HTTP-only versiyasini qo'yamiz
if [ ! -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
    log "SSL sertifikati hali yo'q — HTTP-only nginx config ishlatamiz"
    cat > /etc/nginx/sites-available/marketmega <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN;

    client_max_body_size 15M;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location /static/ {
        alias $APP_DIR/app/static/;
        expires 7d;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF
fi

ln -sf /etc/nginx/sites-available/marketmega /etc/nginx/sites-enabled/marketmega
rm -f /etc/nginx/sites-enabled/default

mkdir -p /var/www/certbot

if nginx -t; then
    systemctl reload nginx
    log "Nginx qayta yuklandi ✓"
else
    err "Nginx config xatosi"
fi


# ============================================================
# 8. Yakuniy
# ============================================================
echo
log "==============================================="
log "  Deploy MUVAFFAQIYATLI tugadi"
log "==============================================="
echo
echo "Sayt:        http://$DOMAIN"
echo "Admin panel: http://$DOMAIN/admin"
echo
echo "Keyingi qadamlar:"
echo "  1. Domain DNS A-record server IP'siga yo'naltirilganligini tekshiring"
echo "  2. SSL o'rnating:   sudo bash $APP_DIR/deploy/deploy.sh ssl"
echo "  3. BotFather'da Mini App URL'ini yangilang: https://$DOMAIN"
echo "  4. Loglarni kuzating: sudo journalctl -u marketmega -f"
echo
