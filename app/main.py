"""
FastAPI ilovasi + aiogram botni bitta jarayonda ishga tushirish.

Bot polling rejimida parallel task sifatida ishlaydi.
Mini App staticdan `/` yoki `/webapp` orqali beriladi.
Admin panel `/admin` da.
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.bot.bot import bot, dp
from app.bot.handlers import register_handlers
from app.config import settings
from app.routers import admin as admin_router
from app.routers import webapp as webapp_router

logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("marketmega")


async def run_bot() -> None:
    """Aiogram polling taskini ishga tushiradi."""
    dp.include_router(register_handlers())
    log.info("Bot polling boshlandi (@%s)", settings.BOT_USERNAME or "unknown")
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    bot_task = asyncio.create_task(run_bot(), name="telegram-bot-polling")
    log.info("FastAPI lifespan: bot task yaratildi")
    try:
        yield
    finally:
        log.info("FastAPI o'chirilmoqda, botni to'xtatamiz")
        bot_task.cancel()
        try:
            await bot_task
        except (asyncio.CancelledError, Exception):
            pass


app = FastAPI(
    title="Market Mega",
    description="Telegram Mini App + Admin Panel",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url=None,
)


# Static fayllar
app.mount(
    "/static",
    StaticFiles(directory=str(settings.static_dir)),
    name="static",
)

# Routerlar
app.include_router(webapp_router.router)
app.include_router(admin_router.router)


# ---------- Routing ----------
# Brauzerdan kirgan foydalanuvchilar admin panelga yo'naltiriladi
@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse("/admin", status_code=302)


# Mini App — faqat Telegram uchun (WEBAPP_URL bu yerga ko'rsatadi)
@app.get("/app", include_in_schema=False)
async def webapp_page():
    return FileResponse(settings.static_dir / "webapp" / "index.html")


# Eski URL'lar bilan moslik (agar kimdir ulanib qolgan bo'lsa)
@app.get("/webapp", include_in_schema=False)
async def webapp_legacy():
    return RedirectResponse("/app", status_code=301)


@app.get("/admin-login", include_in_schema=False)
async def admin_login_shortcut():
    return RedirectResponse("/admin/login")


@app.get("/healthz", include_in_schema=False)
async def healthz():
    return {"status": "ok"}
