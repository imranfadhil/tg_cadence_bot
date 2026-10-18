from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from backend.database import AsyncSessionLocal, seed_demo_data
from backend.services.streak_engine import ensure_user


class DatabaseAndUserMiddleware(BaseMiddleware):
    """Injects an AsyncSession (`db`) and current `db_user` into aiogram handler data."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        tg_user = data.get("event_from_user")
        async with AsyncSessionLocal() as session:
            data["db"] = session
            if tg_user:
                user = await ensure_user(
                    session,
                    user_id=tg_user.id,
                    first_name=tg_user.first_name or "Athlete",
                    username=tg_user.username,
                )
                await seed_demo_data(session, user_id=tg_user.id)
                data["db_user"] = user
            return await handler(event, data)

