from __future__ import annotations

import io
from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.bot.keyboards import (
    build_coach_bargain_keyboard,
    build_diagnostic_keyboard,
    build_evening_pulse_keyboard,
    build_morning_brief_keyboard,
    build_onboarding_preview_keyboard,
)
from backend.config import settings
from backend.models import CheckInResult, CoachState, User
from backend.schemas import CascadeProposal
from backend.services.coach_ai import (
    decompose_goals_to_cascade,
    generate_coach_reply,
    scale_down_proposal,
    transcribe_voice_note,
)
from backend.services.scheduler import (
    format_evening_pulse_text,
    format_morning_brief_text,
)
from backend.services.streak_engine import (
    apply_cascade_proposal,
    apply_coach_bargain,
    get_scorecard,
    get_today_view,
    handle_diagnostic_action,
    toggle_checkin,
)

router = Router()
bot_router = router


def format_cascade_preview(proposal: CascadeProposal) -> str:
    """Formats a clean multi-horizon summary of the AI-decomposed CascadeProposal."""
    lines = [
        "🧭 <b>Cadence Goal Cascade Proposal</b>",
        f"<i>{proposal.coach_summary}</i>",
        "",
    ]
    for ag in proposal.annual_goals:
        lines.append(f"🏔️ <b>ANNUAL [{ag.category}]: {ag.title}</b>")
        for mg in ag.monthly_targets:
            lines.append(f"  ↳ 🗓️ <b>Monthly:</b> {mg.title}")
            for wg in mg.weekly_milestones:
                lines.append(
                    f"    ↳ 📈 <b>Weekly:</b> {wg.title} (<code>{wg.target_metric}</code>)"
                )
                for dg in wg.daily_actions:
                    lines.append(
                        f"      • ⚡ <b>Daily:</b> {dg.title} <code>[{dg.frequency_per_week}x/wk]</code>"
                    )
        lines.append("")
    lines.append("Select how to proceed:")
    return "\n".join(lines)


async def _get_or_create_coach_state(db: AsyncSession, user_id: int) -> CoachState:
    res = await db.execute(select(CoachState).where(CoachState.user_id == user_id))
    state = res.scalar_one_or_none()
    if not state:
        state = CoachState(user_id=user_id)
        db.add(state)
        await db.flush()
    return state


@router.message(CommandStart())
async def cmd_start(message: Message, db: AsyncSession, db_user: User) -> None:
    view = await get_today_view(db, db_user.id)
    text = (
        f"<b>Cadence — Performance & Multi-Horizon Accountability</b>\n\n"
        f"Welcome, <b>{db_user.first_name}</b>. Rhythm: <code>{view.summary.cadence_score}% On Cadence</code>.\n\n"
        f"• Send a <b>voice note</b> or run <code>/setup</code> to decompose your Annual goals into Daily Lead Measures.\n"
        f"• Run <code>/today</code> for zero-friction 1-tap check-ins.\n"
        f"• Run <code>/brief</code>, <code>/pulse</code>, or <code>/strategy</code> to test scheduled rituals."
    )
    await message.answer(
        text, parse_mode="HTML", reply_markup=build_morning_brief_keyboard()
    )


@router.message(Command("setup"))
async def cmd_setup(message: Message, db: AsyncSession, db_user: User) -> None:
    state = await _get_or_create_coach_state(db, db_user.id)
    raw_args = (message.text or "").partition(" ")[2].strip()

    if not raw_args:
        state.awaiting_onboarding_input = 1
        await db.commit()
        await message.answer(
            "🎙️ <b>The Cascade Onboarding</b>\n\n"
            "Send a <b>voice note</b> or a <b>text paragraph</b> describing your main goals for the year.\n\n"
            "I will map your <b>Lag Measures</b> (Annual → Monthly) to controllable <b>Lead Measures</b> (Weekly → Daily actions).",
            parse_mode="HTML",
        )
        return

    status_msg = await message.answer(
        "⚙️ <i>Decomposing goals into Multi-Horizon Cascade...</i>", parse_mode="HTML"
    )
    proposal = await decompose_goals_to_cascade(raw_args, less_aggressive=False)
    state.pending_proposal_json = proposal.model_dump_json()
    state.awaiting_onboarding_input = 0
    await db.commit()

    await status_msg.edit_text(
        format_cascade_preview(proposal),
        parse_mode="HTML",
        reply_markup=build_onboarding_preview_keyboard(),
    )


@router.message(F.voice)
async def handle_voice_onboarding(
    message: Message, bot: Bot, db: AsyncSession, db_user: User
) -> None:
    """Downloads the `.ogg` voice buffer in memory and transcribes via Groq Whisper / OpenRouter."""
    status_msg = await message.answer(
        "🎙️ <i>Transcribing voice note & building Cascade Tree...</i>",
        parse_mode="HTML",
    )
    voice = message.voice
    buf = io.BytesIO()
    if voice:
        file_info = await bot.get_file(voice.file_id)
        if file_info.file_path:
            await bot.download_file(file_info.file_path, destination=buf)

    transcript = await transcribe_voice_note(buf.getvalue(), mime_type="audio/ogg")
    proposal = await decompose_goals_to_cascade(transcript, less_aggressive=False)

    state = await _get_or_create_coach_state(db, db_user.id)
    state.pending_proposal_json = proposal.model_dump_json()
    state.awaiting_onboarding_input = 0
    await db.commit()

    await status_msg.edit_text(
        f'📝 <b>Transcript:</b> <i>"{transcript}"</i>\n\n'
        + format_cascade_preview(proposal),
        parse_mode="HTML",
        reply_markup=build_onboarding_preview_keyboard(),
    )


@router.callback_query(F.data == "onboarding:lock_in")
async def cb_onboarding_lock_in(
    callback: CallbackQuery, db: AsyncSession, db_user: User
) -> None:
    state = await _get_or_create_coach_state(db, db_user.id)
    if not state.pending_proposal_json:
        await callback.answer(
            "No pending proposal found. Run /setup first.", show_alert=True
        )
        return

    proposal = CascadeProposal.model_validate_json(state.pending_proposal_json)
    await apply_cascade_proposal(db, db_user.id, proposal, replace_existing=True)
    state.pending_proposal_json = None
    await db.commit()

    await callback.answer("Cadence Locked In!")
    if callback.message:
        await callback.message.edit_text(
            "✅ <b>Cadence Locked In.</b>\n\n"
            "Your Annual → Monthly → Weekly → Daily hierarchy is now live. "
            "Use <code>/today</code> for 1-tap check-ins or open the Studio below.",
            parse_mode="HTML",
            reply_markup=build_morning_brief_keyboard(),
        )


@router.callback_query(F.data == "onboarding:less_aggressive")
async def cb_onboarding_less_aggressive(
    callback: CallbackQuery, db: AsyncSession, db_user: User
) -> None:
    state = await _get_or_create_coach_state(db, db_user.id)
    if not state.pending_proposal_json:
        await callback.answer("No pending proposal found.", show_alert=True)
        return

    current_proposal = CascadeProposal.model_validate_json(state.pending_proposal_json)
    calibrated = scale_down_proposal(current_proposal)
    state.pending_proposal_json = calibrated.model_dump_json()
    await db.commit()

    await callback.answer("Target load reduced by 25%.")
    if callback.message:
        await callback.message.edit_text(
            format_cascade_preview(calibrated),
            parse_mode="HTML",
            reply_markup=build_onboarding_preview_keyboard(),
        )


@router.message(Command("today", "pulse"))
async def cmd_today(message: Message, db: AsyncSession, db_user: User) -> None:
    view = await get_today_view(db, db_user.id)
    text = format_evening_pulse_text(
        db_user.first_name, view.goals, view.summary.cadence_score
    )
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=build_evening_pulse_keyboard(view.goals),
    )


@router.message(Command("brief"))
async def cmd_brief(message: Message, db: AsyncSession, db_user: User) -> None:
    view = await get_today_view(db, db_user.id)
    text = format_morning_brief_text(
        db_user.first_name, view.goals, view.summary.cadence_score
    )
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=build_morning_brief_keyboard(),
    )


@router.message(Command("diagnostic"))
async def cmd_diagnostic(message: Message) -> None:
    await message.answer(
        "🔍 <b>Diagnostic Check</b>\n\n"
        "Missed yesterday's pulse. Crazy day, or did we hit friction on the plan?",
        parse_mode="HTML",
        reply_markup=build_diagnostic_keyboard(),
    )


@router.message(Command("strategy", "audit"))
async def cmd_strategy(message: Message, db: AsyncSession, db_user: User) -> None:
    scorecard = await get_scorecard(db, db_user.id)
    audit_lines = [
        f"• <b>{h.monthly_title}</b>: Weekly Exec <code>{h.weekly_execution_pct}%</code> → Monthly Milestone <code>{h.monthly_milestone_pct}%</code>"
        for h in scorecard.horizon_audit
    ]
    text = (
        f"📊 <b>Sunday Strategy & Horizon Audit</b>\n"
        f"7-Day Rhythm: <code>{scorecard.summary.cadence_score}% On Cadence</code>\n\n"
        + "\n".join(audit_lines)
        + f"\n\n<b>Diagnostic Question:</b>\n<i>{scorecard.diagnostic_question}</i>"
    )
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=build_morning_brief_keyboard(),
    )


@router.callback_query(F.data.startswith("checkin:"))
async def cb_checkin_toggle(
    callback: CallbackQuery, db: AsyncSession, db_user: User
) -> None:
    """Phase 3: `checkin:<goal_id>:<status>` 1-tap handler."""
    parts = (callback.data or "").split(":")
    if len(parts) != 3:
        await callback.answer("Invalid check-in payload")
        return

    _, goal_id, status_str = parts
    try:
        result_enum = CheckInResult(status_str)
    except ValueError:
        await callback.answer("Unknown check-in status")
        return

    toggle_res = await toggle_checkin(
        session=db,
        user_id=db_user.id,
        goal_id=goal_id,
        result=result_enum,
    )
    view = await get_today_view(db, db_user.id)

    await callback.answer(toggle_res.coach_feedback[:180])

    if callback.message:
        updated_text = format_evening_pulse_text(
            db_user.first_name, view.goals, view.summary.cadence_score
        )
        try:
            await callback.message.edit_text(
                updated_text,
                parse_mode="HTML",
                reply_markup=build_evening_pulse_keyboard(view.goals),
            )
        except Exception:
            pass

        if toggle_res.bargain_triggered:
            await callback.message.answer(
                f"⚖️ <b>The Coach's Bargain — {toggle_res.goal.title}</b>\n\n"
                f"Two consecutive misses detected. Instead of forcing a broken target, pick a tactical trade-off:",
                parse_mode="HTML",
                reply_markup=build_coach_bargain_keyboard(toggle_res.goal.id),
            )


@router.callback_query(F.data.startswith("bargain:"))
async def cb_coach_bargain(
    callback: CallbackQuery, db: AsyncSession, db_user: User
) -> None:
    parts = (callback.data or "").split(":")
    if len(parts) != 3:
        await callback.answer("Invalid bargain payload")
        return

    _, goal_id, action = parts
    res = await apply_coach_bargain(db, db_user.id, goal_id, action)
    await callback.answer("Bargain locked in.")
    if callback.message:
        await callback.message.edit_text(
            f"✅ <b>Coach's Bargain Applied</b>\n\n{res.coach_message}",
            parse_mode="HTML",
        )


@router.callback_query(F.data.startswith("diagnostic:"))
async def cb_diagnostic_action(
    callback: CallbackQuery, db: AsyncSession, db_user: User
) -> None:
    action = (callback.data or "").partition(":")[2]
    msg = await handle_diagnostic_action(db, db_user.id, action)
    await callback.answer("Diagnostic logged.")
    if callback.message:
        await callback.message.edit_text(
            f"✅ <b>Diagnostic Complete</b>\n\n{msg}",
            parse_mode="HTML",
        )


@router.callback_query(F.data.startswith("goal_info:"))
async def cb_goal_info(
    callback: CallbackQuery, db: AsyncSession, db_user: User
) -> None:
    goal_id = (callback.data or "").partition(":")[2]
    view = await get_today_view(db, db_user.id)
    card = next((g for g in view.goals if g.id == goal_id), None)
    if not card:
        await callback.answer("Goal not found.")
        return
    await callback.answer(
        f"{card.title} | Streak: {card.streak_count}d | {card.breadcrumb}",
        show_alert=True,
    )


@router.callback_query(F.data == "studio:open_url")
async def cb_studio_open_url(callback: CallbackQuery) -> None:
    await callback.answer("Studio URL sent below.")
    if callback.message:
        await callback.message.answer(
            f"🎛️ <b>Cadence Studio (Telegram Mini App)</b>\n"
            f"Open in browser: {settings.MINI_APP_URL}\n"
            f"<i>(Tip: Set MINI_APP_URL to an https:// URL in .env to launch inline inside Telegram WebApp)</i>",
            parse_mode="HTML",
        )


@router.message(F.text & ~F.text.startswith("/"))
async def handle_free_text(message: Message, db: AsyncSession, db_user: User) -> None:
    state = await _get_or_create_coach_state(db, db_user.id)
    text_input = (message.text or "").strip()

    if state.awaiting_onboarding_input == 1 or len(text_input) >= 90:
        status_msg = await message.answer(
            "⚙️ <i>Mapping Lag Measures → Daily Lead Measures...</i>",
            parse_mode="HTML",
        )
        proposal = await decompose_goals_to_cascade(text_input, less_aggressive=False)
        state.pending_proposal_json = proposal.model_dump_json()
        state.awaiting_onboarding_input = 0
        await db.commit()

        await status_msg.edit_text(
            format_cascade_preview(proposal),
            parse_mode="HTML",
            reply_markup=build_onboarding_preview_keyboard(),
        )
        return

    view = await get_today_view(db, db_user.id)
    context_str = (
        f"Cadence score {view.summary.cadence_score}%, "
        f"{view.summary.completed_today}/{view.summary.total_today} daily goals done today, "
        f"max streak {view.summary.active_streak_days}d."
    )
    reply = await generate_coach_reply(text_input, context_str)
    await message.answer(reply)

