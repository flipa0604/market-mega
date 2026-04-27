from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Telegram
    BOT_TOKEN: str
    BOT_USERNAME: str = ""
    WEBAPP_URL: str

    # Database
    DATABASE_URL: str

    # Admin
    ADMIN_USERNAME: str = "nodirbek"
    ADMIN_PASSWORD: str = "zxcv1234"
    # Bir nechta admin ID vergul bilan kiritilishi mumkin: 123,456,789
    ADMIN_TELEGRAM_ID: list[int] = []
    # @username (without @) — bot bu username bilan kelgan foydalanuvchini admin deb hisoblaydi
    ADMIN_TG_USERNAME: str | None = None

    # Security / session
    SECRET_KEY: str

    @field_validator("ADMIN_TELEGRAM_ID", mode="before")
    @classmethod
    def _parse_admin_ids(cls, v):
        """`.env`'dan int, vergul bilan ajratilgan str, yoki bo'sh qiymatni qabul qiladi."""
        if v in ("", None):
            return []
        if isinstance(v, int):
            return [v]
        if isinstance(v, list):
            return [int(x) for x in v]
        if isinstance(v, str):
            parts = [p.strip() for p in v.split(",") if p.strip()]
            return [int(p) for p in parts]
        return v

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False

    # Derived paths
    @property
    def base_url(self) -> str:
        """WEBAPP_URL'dan domen qismini ajratib olish.
        WEBAPP_URL=https://nodirmega.uz/app  ->  https://nodirmega.uz
        """
        url = self.WEBAPP_URL.rstrip("/")
        for suffix in ("/app", "/webapp"):
            if url.endswith(suffix):
                return url[: -len(suffix)]
        return url

    @property
    def admin_url(self) -> str:
        """Admin panel URL: https://nodirmega.uz/admin"""
        return f"{self.base_url}/admin"

    @property
    def uploads_dir(self) -> Path:
        path = BASE_DIR / "app" / "static" / "uploads"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def static_dir(self) -> Path:
        return BASE_DIR / "app" / "static"

    @property
    def templates_dir(self) -> Path:
        return BASE_DIR / "app" / "templates"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
