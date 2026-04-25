# 🚀 Market Mega — Server'ga deploy qilish (Ubuntu)

To'liq qadamma-qadam ko'rsatma. Server: **Ubuntu 22.04+** yoki **Debian 12+**.

---

## 📋 Talablar

- ✅ Ubuntu/Debian server (root yoki sudo huquqi)
- ✅ Domain (yoki bepul subdomain — pastga qarang)
- ✅ Telegram bot (BotFather'dan token)
- ✅ Server'ga SSH orqali kirish

> **Domain'ingiz bo'lmasa**, [DuckDNS](https://www.duckdns.org/) yoki [No-IP](https://www.noip.com/) orqali bepul subdomain oling (masalan `marketmega.duckdns.org`), uni server IP'siga yo'naltiring.

---

## ⚡ Tezkor deploy (avtomatik skript bilan)

### 1-qadam — Server'ga kirish

```bash
ssh root@SERVER_IP
# yoki: ssh ubuntu@SERVER_IP
```

### 2-qadam — Loyihani klonlash

```bash
sudo git clone https://github.com/flipa0604/market-mega /opt/marketmega
cd /opt/marketmega
```

### 3-qadam — `.env` faylini yaratish va to'ldirish

```bash
sudo cp .env.example .env
sudo nano .env
```

To'ldirilishi kerak bo'lgan asosiy qiymatlar:

```env
BOT_TOKEN=8030051776:AAEbi9ARM-iJwI74QSZyPm_19rRF5tqfz8k
BOT_USERNAME=botmega_marketbot
WEBAPP_URL=https://shop.sizning-domeningiz.uz
DATABASE_URL=postgresql+asyncpg://marketmega:KUCHLI_PAROL@localhost:5432/marketmega
ADMIN_USERNAME=nodirbek
ADMIN_PASSWORD=KUCHLI_PAROL
ADMIN_TG_USERNAME=hotamov_n
SECRET_KEY=...
HOST=127.0.0.1
PORT=8000
DEBUG=false
```

> 💡 `SECRET_KEY`'ni yarating: `openssl rand -hex 32`

### 4-qadam — Avtomatik deploy

```bash
sudo bash /opt/marketmega/deploy/deploy.sh
```

Bu skript hammasini avtomatik qiladi:
- Python, PostgreSQL, Nginx o'rnatadi
- DB va user yaratadi
- Virtual env va paketlarni o'rnatadi
- Migratsiyani ishga tushiradi
- Systemd service yaratadi
- Nginx'ni sozlaydi (HTTP'da)

### 5-qadam — Domain DNS'ni sozlash

Domain provayder paneliga kiring va **A record** qo'shing:
- **Type:** A
- **Name:** `shop` (yoki `@` agar root domain ishlatsangiz)
- **Value:** Server IP
- **TTL:** 600

DNS o'zgarishi 5-30 daqiqa olishi mumkin. Tekshirish:
```bash
ping shop.sizning-domeningiz.uz
```

### 6-qadam — SSL sertifikat (HTTPS)

DNS yo'naltirilgach:
```bash
sudo bash /opt/marketmega/deploy/deploy.sh ssl
```

Bu Let's Encrypt'dan bepul SSL oladi va nginx'ni HTTPS'ga o'tkazadi.

### 7-qadam — BotFather'da Mini App URL

Telegram'da @BotFather → `/mybots` → botingiz → `Bot Settings` → `Menu Button` → `Configure menu button`:
- **Button text:** `Do'kon`
- **URL:** `https://shop.sizning-domeningiz.uz`

Yoki shu komanda bilan API orqali:
```bash
curl -X POST "https://api.telegram.org/bot<BOT_TOKEN>/setChatMenuButton" \
  -H "Content-Type: application/json" \
  -d '{"menu_button":{"type":"web_app","text":"Do'\''konni ochish","web_app":{"url":"https://shop.sizning-domeningiz.uz"}}}'
```

### 🎉 Tayyor!

- **Sayt:** `https://shop.sizning-domeningiz.uz`
- **Admin panel:** `https://shop.sizning-domeningiz.uz/admin`
- **Bot:** Telegramda @botingiz

---

## 🔧 Foydali buyruqlar

```bash
# Loglarni real-time kuzatish
sudo journalctl -u marketmega -f

# Servisni qayta ishga tushirish
sudo systemctl restart marketmega

# Holat tekshirish
sudo systemctl status marketmega

# Nginx loglarini ko'rish
sudo tail -f /var/log/nginx/marketmega-error.log
sudo tail -f /var/log/nginx/marketmega-access.log

# DB'ga ulanish
sudo -u postgres psql marketmega
```

---

## 🔄 Yangilash (kod o'zgargach)

GitHub'dan yangi versiyani server'ga olib kelish:
```bash
sudo bash /opt/marketmega/deploy/update.sh
```

Bu skript:
1. Git'dan yangi kodni tortadi
2. Dependency'larni yangilaydi
3. Migratsiyani qo'llaydi
4. Servisni qayta ishga tushiradi

---

## 🛡 Xavfsizlik

✅ Skript avtomatik ravishda qiladi:
- `marketmega` system user yaratadi (root emas)
- `.env` faylga 600 huquq qo'yadi (faqat owner o'qiy oladi)
- Systemd hardening: PrivateTmp, ProtectSystem, NoNewPrivileges va h.k.
- Nginx: HSTS, X-Frame-Options va h.k.

❗ Sizdan talab qilinadi:
- `.env`'da kuchli parol va `SECRET_KEY` ishlating
- SSH'ga key-based auth yoqing
- UFW yoqing: `sudo ufw allow OpenSSH 'Nginx Full'; sudo ufw enable`
- DB parolini hech kimga bermang

---

## ❓ Muammolar

### Service ishga tushmayapti
```bash
sudo journalctl -u marketmega -n 50 --no-pager
```
Ko'p uchraydigan xatolar:
- **`asyncpg.exceptions.InvalidPasswordError`** — `.env`'dagi DB parol noto'g'ri
- **`pydantic_core ... ValidationError`** — `.env`'da biror majburiy o'zgaruvchi yo'q
- **`Address already in use`** — port 8000 boshqa jarayonda. `sudo lsof -i:8000`

### Mini App ochilmayapti / "initData yo'q"
- Telegram'da botga **/start** ni qayta yuboring (eski keyboard cache'da)
- WEBAPP_URL .env'da to'g'ri yozilganini tekshiring
- BotFather'da Menu Button URL to'g'rimi

### Rasm yuklanmayapti
- `app/static/uploads/` huquqini tekshiring:
  ```bash
  sudo chown -R marketmega:marketmega /opt/marketmega/app/static/uploads
  sudo chmod 750 /opt/marketmega/app/static/uploads
  ```

### Nginx 502 Bad Gateway
- Bot ishlamayapti — `sudo systemctl status marketmega`
- Loglar: `sudo journalctl -u marketmega -n 50`

---

## 📊 Monitoring

Bot tushib qolsa avtomatik qayta ishga tushadi (systemd `Restart=always`).

Telegram orqali xabar olish uchun .env'da:
```env
ADMIN_TELEGRAM_ID=123456789
```
yoki:
```env
ADMIN_TG_USERNAME=hotamov_n
```

Yangi buyurtma va chat xabarlari shu user'ga keladi.

---

## 🆘 Qo'llab-quvvatlash

Muammo bo'lsa:
1. Loglarni ko'ring: `sudo journalctl -u marketmega -n 100`
2. Systemd holatini tekshiring: `sudo systemctl status marketmega`
3. Nginx loglarini ko'ring: `sudo tail -100 /var/log/nginx/marketmega-error.log`
