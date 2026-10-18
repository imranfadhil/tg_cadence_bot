from __future__ import annotations

import asyncio
import contextlib
import logging
import re
import shutil
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from aiogram import Bot, Dispatcher
from aiogram.types import MenuButtonWebApp, WebAppInfo
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api.routes import router as api_router
from backend.bot.handlers import router as bot_router
from backend.bot.middlewares import DatabaseAndUserMiddleware
from backend.config import FRONTEND_DIST_DIR, settings
from backend.database import engine, init_db
from backend.models import Base
from backend.services.scheduler import (
    scheduler,
    set_scheduler_bot,
    start_scheduler,
    stop_scheduler,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("cadence.main")

_TUNNEL_URL_RE = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")


def _has_valid_bot_token() -> bool:
    token = (settings.TELEGRAM_BOT_TOKEN or "").strip()
    return bool(token and ":" in token and not token.startswith("your_"))


async def _configure_bot_menu_button(bot: Optional[Bot], url: str) -> None:
    if not bot or not url.startswith("https://"):
        return
    with contextlib.suppress(Exception):
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="🎛️ Studio",
                web_app=WebAppInfo(url=url),
            )
        )
        logger.info("Configured Telegram Mini App Menu Button -> %s", url)


async def _start_cloudflare_quick_tunnel(
    port: int, bot: Optional[Bot]
) -> Optional[asyncio.subprocess.Process]:
    cloudflared_bin = shutil.which("cloudflared")
    if not cloudflared_bin:
        return None

    logger.info("Starting built-in Cloudflare HTTPS Quick Tunnel for Mini App...")
    proc = await asyncio.create_subprocess_exec(
        cloudflared_bin,
        "tunnel",
        "--no-autoupdate",
        "--url",
        f"http://127.0.0.1:{port}",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )

    async def _watch_tunnel_stderr() -> None:
        if not proc.stderr:
            return
        while True:
            line_bytes = await proc.stderr.readline()
            if not line_bytes:
                break
            line = line_bytes.decode("utf-8", errors="ignore")
            match = _TUNNEL_URL_RE.search(line)
            if match:
                tunnel_url = match.group(0)
                settings.MINI_APP_URL = tunnel_url
                settings.WEBAPP_PUBLIC_URL = tunnel_url
                logger.info("Cloudflare HTTPS Quick Tunnel ready: %s", tunnel_url)
                await _configure_bot_menu_button(bot, tunnel_url)

    asyncio.create_task(_watch_tunnel_stderr())
    return proc


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # 1. Initialize SQLite tables (WAL mode enforced via engine connect event) & seed demo data
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await init_db()

    # 2. Start in-process AsyncIOScheduler backed by SQLite SQLAlchemyJobStore
    start_scheduler()

    # 3. Start Telegram Bot polling as a background task in the SAME event loop
    bot: Optional[Bot] = None
    polling_task: Optional[asyncio.Task] = None
    tunnel_proc: Optional[asyncio.subprocess.Process] = None

    if _has_valid_bot_token():
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN.strip())
        dp = Dispatcher()
        dp.update.middleware(DatabaseAndUserMiddleware())
        dp.include_router(bot_router)
        set_scheduler_bot(bot)

        if not settings.TELEGRAM_USE_WEBHOOK:
            logger.info("Starting aiogram Telegram Bot polling in unified event loop...")
            await bot.delete_webhook(drop_pending_updates=True)
            polling_task = asyncio.create_task(
                dp.start_polling(bot, handle_signals=False)
            )
    else:
        logger.info(
            "TELEGRAM_BOT_TOKEN not set — running unified FastAPI + Static Mini App + SQLite WAL Scheduler."
        )

    # 4. Configure Mini App HTTPS URL (explicit domain or automatic Cloudflare Quick Tunnel)
    configured_url = settings.public_webapp_url
    if configured_url.startswith("https://"):
        await _configure_bot_menu_button(bot, configured_url)
    elif not configured_url or (
        settings.APP_ENV == "production" and "localhost" in configured_url
    ):
        tunnel_proc = await _start_cloudflare_quick_tunnel(settings.PORT, bot)

    try:
        yield
    finally:
        if tunnel_proc and tunnel_proc.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                tunnel_proc.terminate()
        if polling_task:
            polling_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await polling_task
        stop_scheduler()
        if bot:
            await bot.session.close()


app = FastAPI(title="Cadence Featherweight API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")

# Serve compiled React Mini App static files from the same process (0 MB extra server overhead)
if FRONTEND_DIST_DIR.exists():
    app.mount(
        "/",
        StaticFiles(directory=str(FRONTEND_DIST_DIR), html=True),
        name="static",
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        workers=1,
    )
