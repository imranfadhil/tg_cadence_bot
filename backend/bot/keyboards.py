from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from backend.config import settings
from backend.models import GoalStatus
from backend.schemas import TodayGoalCardDTO


def _studio_button(label: str) -> InlineKeyboardButton:
    """Returns a native Telegram WebApp button if HTTPS is configured, or callback fallback for HTTP localhost."""
    url = (settings.MINI_APP_URL or "").strip()
    if url.startswith("https://"):
        return InlineKeyboardButton(text=label, web_app=WebAppInfo(url=url))
    return InlineKeyboardButton(text=label, callback_data="studio:open_url")


def build_onboarding_preview_keyboard() -> InlineKeyboardMarkup:
    """Section 3.1 Preview & Calibration keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Lock In Cadence", callback_data="onboarding:lock_in"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📉 Make Less Aggressive",
                    callback_data="onboarding:less_aggressive",
                )
            ],
            [_studio_button("🎛️ Edit in Studio (Mini App)")],
        ]
    )


def build_morning_brief_keyboard() -> InlineKeyboardMarkup:
    """Section 3.2 Morning Brief keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_studio_button("⚡ Open Today's View")],
        ]
    )


def build_evening_pulse_keyboard(goals: list[TodayGoalCardDTO]) -> InlineKeyboardMarkup:
    """Section 3.2 & Phase 3: Interactive 1-tap inline keyboard per daily goal (`checkin:<goal_id>:<status>`)."""
    rows: list[list[InlineKeyboardButton]] = []
    for g in goals:
        if g.status != GoalStatus.ACTIVE:
            continue
        short_title = g.title if len(g.title) <= 28 else g.title[:25] + "..."
        silence_prefix = "🔕 " if g.earned_silence else ""
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{silence_prefix}{short_title} ({g.streak_count}d)",
                    callback_data=f"goal_info:{g.id}",
                )
            ]
        )
        done_label = "✅ Done •" if g.today_result == "DONE" else "✅ Done"
        part_label = "⚠️ Partial •" if g.today_result == "PARTIAL" else "⚠️ Partial"
        miss_label = "❌ Missed •" if g.today_result == "MISSED" else "❌ Missed"
        rows.append(
            [
                InlineKeyboardButton(
                    text=done_label, callback_data=f"checkin:{g.id}:DONE"
                ),
                InlineKeyboardButton(
                    text=part_label, callback_data=f"checkin:{g.id}:PARTIAL"
                ),
                InlineKeyboardButton(
                    text=miss_label, callback_data=f"checkin:{g.id}:MISSED"
                ),
            ]
        )
    rows.append([_studio_button("⚡ Open Today's View")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_diagnostic_keyboard() -> InlineKeyboardMarkup:
    """Section 3.3 Rule 2: 10:00 next-morning Diagnostic Check inline buttons."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Log Yesterday All ✅",
                    callback_data="diagnostic:LOG_YESTERDAY_ALL",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Crazy Day - Resume Today",
                    callback_data="diagnostic:CRAZY_DAY_RESUME",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Adjust Weekly Load",
                    callback_data="diagnostic:ADJUST_WEEKLY_LOAD",
                )
            ],
        ]
    )


def build_coach_bargain_keyboard(goal_id: str) -> InlineKeyboardMarkup:
    """Section 3.3 Rule 3: The Coach's Bargain (2x Snooze/Miss) tactical trade-off buttons."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Do a 5-min micro-version now",
                    callback_data=f"bargain:{goal_id}:MICRO_5M",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Scale back weekly target by 25%",
                    callback_data=f"bargain:{goal_id}:SCALE_BACK_25",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Pause habit until Monday",
                    callback_data=f"bargain:{goal_id}:PAUSE_MONDAY",
                )
            ],
        ]
    )

