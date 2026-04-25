"""
Ishga tushirish: `python run.py`

Bu bir vaqtning o'zida:
- FastAPI (admin panel + mini app API + mini app frontend)
- Telegram bot (aiogram polling)
ni ishga tushiradi.
"""
import uvicorn

from app.config import settings


def main() -> None:
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info",
    )


if __name__ == "__main__":
    main()
