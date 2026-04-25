# 🛍 Market Mega

Telegram Mini App'li online do'kon boti. Mijozlar bot orqali ro'yxatdan o'tadi, Telegram ichidagi mini appda kategoriya→mahsulot tanlab, buyurtma beradi. Admin panel orqali mahsulotlar boshqariladi va yangi buyurtmalar lokatsiya bilan ko'rinadi.

---

## ✨ Imkoniyatlar

- 📱 **Telegram Mini App** — mobile-first, Telegram mavzusiga moslashgan (light/dark)
- 🔐 **Xavfsiz auth** — har bir mini app so'rovi Telegram `initData` bilan HMAC orqali tekshiriladi
- 🛒 **Kategoriya → mahsulot** — +/- counter, lokal savat, "Tanladim" tugmasi
- 📍 **Lokatsiya bilan buyurtma** — mini app yopilgach, bot lokatsiya so'raydi
- 🧑‍💼 **Admin panel** — kategoriyalar/mahsulotlar CRUD (rasm upload), buyurtmalar statusi
- 🔔 **Admin xabarnomasi** — yangi buyurtma kelsa adminga Telegram orqali xabar
- 🐘 **PostgreSQL + SQLAlchemy async + Alembic**

---

## 📂 Loyiha tuzilishi

```
market-mega/
├── app/
│   ├── main.py              # FastAPI + bot lifespan
│   ├── config.py            # Pydantic settings (.env)
│   ├── database.py          # Async SQLAlchemy engine
│   ├── models/              # User, Category, Product, Order, OrderItem
│   ├── schemas/             # Pydantic IO sxemalari
│   ├── routers/
│   │   ├── webapp.py        # Mini App JSON API
│   │   └── admin.py         # Admin panel (HTML + forms)
│   ├── bot/
│   │   ├── bot.py           # Aiogram Bot/Dispatcher
│   │   ├── handlers.py      # /start, contact, web_app_data, location
│   │   └── keyboards.py
│   ├── utils/
│   │   ├── telegram_auth.py # initData tekshirish
│   │   ├── security.py      # Admin session
│   │   └── deps.py          # FastAPI dependencies
│   ├── templates/           # Jinja2 (admin panel)
│   └── static/
│       ├── admin/           # Admin panel CSS
│       ├── webapp/          # Mini App (HTML/CSS/JS)
│       └── uploads/         # Yuklangan rasmlar
├── alembic/                 # DB migratsiyalari
├── docker-compose.yml       # Postgres uchun
├── requirements.txt
├── run.py                   # Entrypoint
└── .env.example
```

---

## 🚀 Tezkor boshlash (lokal)

### 1. Bot yaratish
1. Telegram'da [@BotFather](https://t.me/BotFather) ga yozing → `/newbot`
2. Bot tokenini oling
3. `/setmenubutton` yoki `/newapp` orqali mini app URL'ni belgilang (lokal testda ngrok URL)

### 2. Lokal o'rnatish
```bash
# 1. Repository klonlash
git clone <repo-url>
cd market-mega

# 2. Virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# 3. Kutubxonalar
pip install -r requirements.txt

# 4. PostgreSQL'ni docker bilan ishga tushirish
docker compose up -d

# 5. .env fayl yaratish
cp .env.example .env
# .env ichidagi qiymatlarni to'ldiring (BOT_TOKEN, WEBAPP_URL va h.k.)

# 6. DB migratsiyasi
alembic upgrade head

# 7. Ngrok bilan HTTPS tunnel (lokal test uchun)
# Yangi terminalda:
ngrok http 8000
# Olingan HTTPS URL'ni .env -> WEBAPP_URL ga yozing

# 8. Ishga tushirish
python run.py
```

Endi:
- **Bot:** Telegramda botingizga `/start` yuboring
- **Admin panel:** `http://localhost:8000/admin` (login: `nodirbek`, parol: `zxcv1234`)
- **Mini App test:** botdagi "🛍 Do'konni ochish" tugmasi orqali

---

## 🔧 Konfiguratsiya (.env)

| O'zgaruvchi | Tavsif |
|---|---|
| `BOT_TOKEN` | BotFather'dan olingan token |
| `BOT_USERNAME` | Bot username (masalan `market_mega_bot`) |
| `WEBAPP_URL` | Mini App URL (HTTPS majburiy) |
| `DATABASE_URL` | `postgresql+asyncpg://user:pass@host:port/dbname` |
| `ADMIN_USERNAME` | Admin login (default: `nodirbek`) |
| `ADMIN_PASSWORD` | Admin parol (default: `zxcv1234`) |
| `ADMIN_TELEGRAM_ID` | Admin TG ID — yangi buyurtma xabarnomasi uchun |
| `SECRET_KEY` | Session cookie uchun tasodifiy satr |
| `HOST`, `PORT` | Server manzili (default `0.0.0.0:8000`) |
| `DEBUG` | `true` bo'lsa `/api/docs` ochiq, auto-reload yoqiladi |

---

## 🌐 Productionga deploy

### 1. Serverga kirish va kodni ko'chirib olish
```bash
git clone <repo-url> /opt/market-mega
cd /opt/market-mega
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

### 2. `.env` yaratish
```bash
cp .env.example .env
nano .env
# WEBAPP_URL ni o'zingizning HTTPS domeningizga o'zgartiring
# DEBUG=false
# SECRET_KEY=$(openssl rand -hex 32)
```

### 3. PostgreSQL o'rnatish (Ubuntu)
```bash
sudo apt install postgresql
sudo -u postgres psql
CREATE DATABASE marketmega;
CREATE USER mm WITH PASSWORD 'strongpass';
GRANT ALL ON DATABASE marketmega TO mm;
\q
```

### 4. Migratsiya
```bash
alembic upgrade head
```

### 5. systemd service
`/etc/systemd/system/marketmega.service`:
```ini
[Unit]
Description=Market Mega Bot
After=network.target postgresql.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/market-mega
Environment="PATH=/opt/market-mega/venv/bin"
ExecStart=/opt/market-mega/venv/bin/python run.py
Restart=always

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now marketmega
sudo systemctl status marketmega
```

### 6. Nginx reverse proxy + SSL
`/etc/nginx/sites-available/marketmega`:
```nginx
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate     /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    client_max_body_size 15M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```
```bash
sudo ln -s /etc/nginx/sites-available/marketmega /etc/nginx/sites-enabled/
sudo certbot --nginx -d your-domain.com
sudo systemctl reload nginx
```

### 7. BotFather'da Mini App URL'ni yangilang
`@BotFather` → `/mybots` → `Bot Settings` → `Menu Button` → `https://your-domain.com/`

---

## 🧪 Test qilish

1. **Bot:** `/start` → telefon so'raydi → "Do'konni ochish"
2. **Mini App:** Kategoriya tanlang → mahsulotlarga `+` bosing → "Tanladim"
3. **Bot:** Lokatsiya yuboring
4. **Admin:** `/admin` → `Buyurtmalar` — buyurtma ro'yxatda ko'rinadi

---

## 🛡 Xavfsizlik

- Parollar `.env` da, `.gitignore` orqali git'dan chiqarilgan
- Admin session cookie `itsdangerous` + `SECRET_KEY` bilan imzolangan
- Mini App so'rovlari HMAC-SHA256 orqali `BOT_TOKEN` bilan tekshiriladi (oxirgi 24 soat ichida)
- Production'da parolni va `SECRET_KEY`ni albatta o'zgartiring!

---

## 🧰 Foydali buyruqlar

```bash
# Bot loglarini ko'rish (systemd)
sudo journalctl -u marketmega -f

# Yangi migratsiya yaratish (model o'zgargandan keyin)
alembic revision --autogenerate -m "add something"
alembic upgrade head

# DB rollback
alembic downgrade -1
```

---

## ❓ Muammolar

- **"Mini App ochilmayapti"** — `WEBAPP_URL` HTTPS bo'lishi shart. Lokal testda `ngrok http 8000`.
- **"Auth xato: hash mos kelmadi"** — `.env`'dagi `BOT_TOKEN` bilan BotFather'dagi token bir xil bo'lishi kerak.
- **"Database connection refused"** — `docker compose up -d` yoki postgres xizmati ishlab turibdimi tekshiring.
- **"Rasm yuklanmayapti"** — `app/static/uploads/` yoziladigan huquqqa ega bo'lishi kerak (prod'da `chown www-data`).

---

## 📝 Litsenziya

MIT — xohlagancha foydalaning.
