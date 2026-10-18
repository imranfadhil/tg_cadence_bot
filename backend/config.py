import hmac
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
FRONTEND_DIST_DIR = ROOT_DIR / "frontend" / "dist"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_ENV: str = "development"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    MINI_APP_URL: str = "http://localhost:8000"

    ACCESS_PASSPHRASE: str = ""

    DATABASE_URL: str = f"sqlite+aiosqlite:///{(DATA_DIR / 'cadence.db').as_posix()}"

    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_USE_WEBHOOK: bool = False
    TELEGRAM_WEBHOOK_URL: str = ""

    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str = "openai/gpt-4o-mini"
    OPENROUTER_AUDIO_MODEL: str = "google/gemini-2.0-flash-001"

    GROQ_API_KEY: str = ""
    GROQ_WHISPER_MODEL: str = "whisper-large-v3-turbo"

    DEFAULT_TIMEZONE: str = "Asia/Kuala_Lumpur"
    DEFAULT_MORNING_BRIEF: str = "08:00"
    DEFAULT_EVENING_PULSE: str = "21:00"
    DEMO_USER_ID: int = 777000

    @property
    def sync_database_url(self) -> str:
        """Synchronous SQLite URL used by APScheduler's SQLAlchemyJobStore on the same ./data/cadence.db file."""
        if self.DATABASE_URL.startswith("sqlite+aiosqlite://"):
            return self.DATABASE_URL.replace("sqlite+aiosqlite://", "sqlite://", 1)
        return self.DATABASE_URL

    @property
    def is_passphrase_enabled(self) -> bool:
        return bool((self.ACCESS_PASSPHRASE or "").strip())

    def verify_passphrase(self, candidate: str) -> bool:
        """Constant-time verification of the user-supplied passphrase or PIN."""
        expected = (self.ACCESS_PASSPHRASE or "").strip()
        if not expected:
            return True
        provided = (candidate or "").strip()
        if not provided:
            return False
        return hmac.compare_digest(expected.encode("utf-8"), provided.encode("utf-8"))


settings = Settings()
