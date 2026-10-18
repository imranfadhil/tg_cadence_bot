from __future__ import annotations

import calendar
import logging
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from aiogram import Bot
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import create_engine, event, select

from backend.config import settings
from backend.database import AsyncSessionLocal
from backend.models import CoachState, GoalStatus, User
from backend.services.streak_engine import (
    get_scorecard,
    get_today_view,
)

logger = logging.getLogger(__name__)

# Persist APScheduler jobs inside the same SQLite database (./data/cadence.db) with WAL mode
_jobstore_engine = create_engine(
    settings.sync_database_url,
    connect_args={"check_same_thread": False, "timeout": 5},
)


@event.listens_for(_jobstore_engine, "connect")
def _set_jobstore_sqlite_pragma(dbapi_connection, connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA synchronous=NORMAL;")
    cursor.execute("PRAGMA busy_timeout=5000;")
    cursor.close()


scheduler = AsyncIOScheduler(
    jobstores={
        "default": SQLAlchemyJobStore(engine=_jobstore_engine, tablename="apscheduler_jobs")
    },
    job_defaults={"coalesce": True, "max_instances": 1},
)

_bot_instance: Optional[Bot] = None


def set_scheduler_bot(bot: Optional[Bot]) -> None:
    global _bot_instance
    _bot_instance = bot


def format_morning_brief_text(first_name: str, goals: list, cadence_score: int) -> str:
    """Rule 1: Suppresses morning reminders for habits that have Earned Silence (>= 5d streak)."""
    active_goals = [g for g in goals if g.status == GoalStatus.ACTIVE]
    unsilenced = [g for g in active_goals if not g.earned_silence]
    silenced_count = len(active_goals) - len(unsilenced)

    lines = [
        f"⚡ <b>Morning Brief — {first_name}</b>",
        f"Rhythm: <code>{cadence_score}% On Cadence</code>",
        "",
    ]
    if unsilenced:
        lines.append("<b>Today's Focus Lead Measures:</b>")
        for idx, g in enumerate(unsilenced[:3], start=1):
            lines.append(f"{idx}. <b>{g.title}</b>\n   <i>{g.breadcrumb}</i>")
    else:
        lines.append(
            "All active daily habits have achieved <b>Earned Silence (5d+ streak)</b>. "
            "Autonomous rhythm engaged."
        )

    if silenced_count > 0:
        lines.append(
            f"\n🔕 <i>{silenced_count} habit(s) suppressed via Earned Silence (5d+ streak).</i>"
        )
    return "\n".join(lines)


def format_evening_pulse_text(first_name: str, goals: list, cadence_score: int) -> str:
    lines = [
        f"🌙 <b>Evening Pulse — {first_name}</b>",
        f"Current Rhythm: <code>{cadence_score}% On Cadence</code>",
        "Tap once per Lead Measure below to log today's telemetry:",
        "",
    ]
    for g in goals:
        if g.status != GoalStatus.ACTIVE:
            continue
        status_icon = (
            "✅"
            if g.today_result == "DONE"
            else "⚠️"
            if g.today_result == "PARTIAL"
            else "❌"
            if g.today_result == "MISSED"
            else "⬜"
        )
        silence_badge = " <code>[🔕 5d+ Earned Silence]</code>" if g.earned_silence else ""
        streak_tag = f"<code>{g.streak_count}d</code>"
        lines.append(f"{status_icon} <b>{g.title}</b> ({streak_tag}){silence_badge}")
    return "\n".join(lines)


async def run_ritual_tick() -> None:
    """Runs every minute to check if any user is due for Morning Brief, Diagnostic Check, Evening Pulse, Sunday Strategy, or Monthly Horizon Audit."""
    if not _bot_instance:
        return

    from backend.bot.keyboards import (
        build_diagnostic_keyboard,
        build_evening_pulse_keyboard,
        build_morning_brief_keyboard,
    )

    async with AsyncSessionLocal() as session:
        res = await session.execute(select(User))
        users = res.scalars().all()

        for user in users:
            try:
                tz = ZoneInfo(user.timezone or "Asia/Kuala_Lumpur")
            except Exception:
                tz = ZoneInfo("Asia/Kuala_Lumpur")

            now_local = datetime.now(tz)
            hhmm = now_local.strftime("%H:%M")
            today_local = now_local.date()

            state_res = await session.execute(
                select(CoachState).where(CoachState.user_id == user.id)
            )
            state = state_res.scalar_one_or_none()
            if not state:
                state = CoachState(user_id=user.id)
                session.add(state)
                await session.flush()

            # 1. Morning Brief (Default 08:00 Local)
            if hhmm == user.morning_brief_time:
                view = await get_today_view(session, user.id, today_local)
                text = format_morning_brief_text(
                    user.first_name, view.goals, view.summary.cadence_score
                )
                await _bot_instance.send_message(
                    chat_id=user.id,
                    text=text,
                    parse_mode="HTML",
                    reply_markup=build_morning_brief_keyboard(),
                )

            # 2. Rule 2: 10:00 Diagnostic Check (only if yesterday was unlogged & not yet sent today)
            if hhmm == "10:00" and state.last_diagnostic_sent_date != today_local:
                view = await get_today_view(session, user.id, today_local)
                if view.summary.missed_yesterday_unlogged:
                    state.last_diagnostic_sent_date = today_local
                    await session.commit()
                    await _bot_instance.send_message(
                        chat_id=user.id,
                        text=(
                            "🔍 <b>Diagnostic Check</b>\n\n"
                            "Missed yesterday's pulse. Crazy day, or did we hit friction on the plan?"
                        ),
                        parse_mode="HTML",
                        reply_markup=build_diagnostic_keyboard(),
                    )

            # 3. Evening Pulse (Default 21:00 Local - never sent twice on the same day)
            if hhmm == user.evening_pulse_time and state.last_pulse_sent_date != today_local:
                state.last_pulse_sent_date = today_local
                await session.commit()
                view = await get_today_view(session, user.id, today_local)
                text = format_evening_pulse_text(
                    user.first_name, view.goals, view.summary.cadence_score
                )
                await _bot_instance.send_message(
                    chat_id=user.id,
                    text=text,
                    parse_mode="HTML",
                    reply_markup=build_evening_pulse_keyboard(view.goals),
                )

            # 4. Weekly Sunday Strategy (Sunday 18:00 Local)
            if now_local.weekday() == 6 and hhmm == "18:00":
                scorecard = await get_scorecard(session, user.id)
                last_day_of_month = calendar.monthrange(today_local.year, today_local.month)[1]
                is_last_sunday = (last_day_of_month - today_local.day) < 7

                header = (
                    "🧭 <b>Monthly Horizon Audit & Sunday Strategy</b>"
                    if is_last_sunday
                    else "📊 <b>Sunday Strategy — 7-Day Telemetry</b>"
                )
                audit_lines = [
                    f"• <b>{h.monthly_title}</b>: Weekly Exec <code>{h.weekly_execution_pct}%</code> → Monthly Milestone <code>{h.monthly_milestone_pct}%</code>"
                    for h in scorecard.horizon_audit
                ]
                body = (
                    f"{header}\n"
                    f"7-Day Rhythm: <code>{scorecard.summary.cadence_score}% On Cadence</code>\n\n"
                    + "\n".join(audit_lines)
                    + f"\n\n<b>Diagnostic Question:</b>\n<i>{scorecard.diagnostic_question}</i>"
                )
                await _bot_instance.send_message(
                    chat_id=user.id,
                    text=body,
                    parse_mode="HTML",
                    reply_markup=build_morning_brief_keyboard(),
                )


def start_scheduler() -> None:
    if not scheduler.running:
        scheduler.start()
        scheduler.add_job(
            "backend.services.scheduler:run_ritual_tick",
            trigger="interval",
            seconds=60,
            id="cadence_ritual_tick",
            replace_existing=True,
        )
        logger.info("Cadence APScheduler started with SQLite SQLAlchemyJobStore (WAL mode).")


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
