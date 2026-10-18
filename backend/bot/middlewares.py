from __future__ import annotations

import contextlib
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, Update

from backend.bot.keyboards import build_morning_brief_keyboard
from backend.config import settings
from backend.database import AsyncSessionLocal, seed_demo_data
from backend.services.streak_engine import ensure_user, get_today_view


def _extract_candidate_pin(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return ""
    if raw.startswith("/"):
        parts = raw.split(maxsplit=1)
        if len(parts) == 2 and parts[0].lower() in ("/start", "/unlock", "/auth", "/pin"):
            return parts[1].strip()
        return ""
    return raw


class DatabaseAndUserMiddleware(BaseMiddleware):
    """Injects `db` & `db_user` and enforces the ACCESS_PASSPHRASE / PIN gate."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        tg_user = data.get("event_from_user")
        async with AsyncSessionLocal() as session:
            data["db"] = session
            if not tg_user:
                return await handler(event, data)

            user = await ensure_user(
                session,
                user_id=tg_user.id,
                first_name=tg_user.first_name or "Athlete",
                username=tg_user.username,
            )

            # Enforce Passphrase / PIN gate when ACCESS_PASSPHRASE is set
            if settings.is_passphrase_enabled and not user.is_authorized:
                msg: Message | None = None
                cb: CallbackQuery | None = None
                if isinstance(event, Update):
                    msg = event.message
                    cb = event.callback_query
                elif isinstance(event, Message):
                    msg = event
                elif isinstance(event, CallbackQuery):
                    cb = event

                if msg and msg.text:
                    candidate = _extract_candidate_pin(msg.text)
                    if candidate and settings.verify_passphrase(candidate):
                        user.is_authorized = 1
                        await session.commit()
                        await seed_demo_data(session, user_id=user.id)

                        # Delete the PIN message from chat history for privacy
                        with contextlib.suppress(Exception):
                            await msg.delete()

                        view = await get_today_view(session, user.id)
                        await msg.answer(
                            f"🔓 <b>Access Granted — Welcome, {user.first_name}</b>\n\n"
                            f"Rhythm: <code>{view.summary.cadence_score}% On Cadence</code>.\n"
                            f"• Send a <b>voice note</b> or run <code>/setup</code> to build your Goal Cascade.\n"
                            f"• Run <code>/today</code> for 1-tap check-ins.\n"
                            f"• Run <code>/lock</code> anytime to lock your session.",
                            parse_mode="HTML",
                            reply_markup=build_morning_brief_keyboard(),
                        )
                        return None

                    await msg.answer(
                        "🔒 <b>Cadence Access Restricted</b>\n\n"
                        "Please reply with your <b>access passphrase / PIN</b> (or send <code>/unlock &lt;PIN&gt;</code>) to unlock this bot.",
                        parse_mode="HTML",
                    )
                    return None

                if msg:
                    await msg.answer(
                        "🔒 <b>Cadence Access Restricted</b>\n\n"
                        "Please enter your text <b>access passphrase / PIN</b> first before sending voice notes or media.",
                        parse_mode="HTML",
                    )
                    return None

                if cb:
                    await cb.answer(
                        "🔒 Access restricted. Send your passphrase / PIN in chat first.",
                        show_alert=True,
                    )
                    return None

                return None

            await seed_demo_data(session, user_id=user.id)
            data["db_user"] = user
            return await handler(event, data)
