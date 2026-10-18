from __future__ import annotations

import math
import uuid
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    CheckInLog,
    CheckInResult,
    CoachIntensity,
    GoalNode,
    GoalStatus,
    HorizonLevel,
    MetricType,
    User,
)
from backend.schemas import (
    BargainActionResponse,
    CascadeProposal,
    CheckInToggleResponse,
    GoalTreeNodeDTO,
    HorizonAuditItemDTO,
    MomentumSummaryDTO,
    ScorecardDayDTO,
    ScorecardResponse,
    TodayGoalCardDTO,
    TodayViewResponse,
)

EARNED_SILENCE_STREAK = 5
COACH_BARGAIN_MISS_THRESHOLD = 2


def is_earned_silence(goal: GoalNode) -> bool:
    """Rule 1: Earned Silence when a Daily goal hits a >= 5-day streak."""
    return goal.horizon == HorizonLevel.DAILY and goal.streak_count >= EARNED_SILENCE_STREAK


def needs_coach_bargain(goal: GoalNode) -> bool:
    """Rule 3: The Coach's Bargain when a Daily goal hits >= 2 consecutive misses."""
    return (
        goal.horizon == HorizonLevel.DAILY
        and goal.status == GoalStatus.ACTIVE
        and goal.consecutive_misses >= COACH_BARGAIN_MISS_THRESHOLD
    )


async def ensure_user(
    session: AsyncSession,
    user_id: int,
    first_name: str = "Athlete",
    username: Optional[str] = None,
) -> User:
    res = await session.execute(select(User).where(User.id == user_id))
    user = res.scalar_one_or_none()
    if not user:
        user = User(
            id=user_id,
            first_name=first_name or "Athlete",
            username=username,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


async def _load_user_nodes(session: AsyncSession, user_id: int) -> dict[str, GoalNode]:
    res = await session.execute(
        select(GoalNode)
        .where(GoalNode.user_id == user_id)
        .order_by(GoalNode.created_at.asc())
    )
    nodes = res.scalars().all()
    return {n.id: n for n in nodes}


async def _load_date_logs(
    session: AsyncSession, user_id: int, target_date: date
) -> dict[str, CheckInLog]:
    res = await session.execute(
        select(CheckInLog).where(
            and_(
                CheckInLog.user_id == user_id,
                CheckInLog.logged_date == target_date,
            )
        )
    )
    logs = res.scalars().all()
    return {log.goal_id: log for log in logs}


def _build_breadcrumb(node: GoalNode, node_map: dict[str, GoalNode]) -> tuple[str, Optional[str], Optional[str], Optional[str]]:
    weekly_title = None
    monthly_title = None
    annual_title = None

    curr = node_map.get(node.parent_id) if node.parent_id else None
    while curr:
        if curr.horizon == HorizonLevel.WEEKLY:
            weekly_title = curr.title
        elif curr.horizon == HorizonLevel.MONTHLY:
            monthly_title = curr.title
        elif curr.horizon == HorizonLevel.ANNUAL:
            annual_title = curr.title
        curr = node_map.get(curr.parent_id) if curr.parent_id else None

    if monthly_title:
        breadcrumb = f"↳ {monthly_title}"
    elif weekly_title:
        breadcrumb = f"↳ {weekly_title}"
    elif annual_title:
        breadcrumb = f"↳ {annual_title}"
    else:
        breadcrumb = f"↳ {node.category or 'Core Cadence'}"

    return breadcrumb, weekly_title, monthly_title, annual_title


def _build_today_card(
    node: GoalNode,
    node_map: dict[str, GoalNode],
    today_logs: dict[str, CheckInLog],
) -> TodayGoalCardDTO:
    breadcrumb, w_title, m_title, a_title = _build_breadcrumb(node, node_map)
    log = today_logs.get(node.id)
    return TodayGoalCardDTO(
        id=node.id,
        title=node.title,
        category=node.category,
        parent_weekly_title=w_title,
        parent_monthly_title=m_title,
        parent_annual_title=a_title,
        breadcrumb=breadcrumb,
        target_value=node.target_value,
        current_value=node.current_value,
        streak_count=node.streak_count,
        consecutive_misses=node.consecutive_misses,
        earned_silence=is_earned_silence(node),
        needs_bargain=needs_coach_bargain(node),
        status=node.status,
        today_result=log.result if log else None,
        today_note=log.user_note if log else None,
    )


async def compute_momentum_summary(
    session: AsyncSession, user: User, target_date: Optional[date] = None
) -> MomentumSummaryDTO:
    today = target_date or date.today()
    node_map = await _load_user_nodes(session, user.id)
    today_logs = await _load_date_logs(session, user.id, today)

    daily_nodes = [
        n
        for n in node_map.values()
        if n.horizon == HorizonLevel.DAILY and n.status != GoalStatus.ARCHIVED
    ]
    active_daily = [n for n in daily_nodes if n.status == GoalStatus.ACTIVE]

    completed_today = 0
    for n in active_daily:
        log = today_logs.get(n.id)
        if log and log.result in (CheckInResult.DONE, CheckInResult.PARTIAL):
            completed_today += 1

    # Calculate 7-day rolling Cadence Score
    seven_days_ago = today - timedelta(days=6)
    res_logs = await session.execute(
        select(CheckInLog).where(
            and_(
                CheckInLog.user_id == user.id,
                CheckInLog.logged_date >= seven_days_ago,
                CheckInLog.logged_date <= today,
            )
        )
    )
    week_logs = res_logs.scalars().all()
    if week_logs:
        points = 0.0
        for lg in week_logs:
            if lg.result == CheckInResult.DONE:
                points += 1.0
            elif lg.result == CheckInResult.PARTIAL:
                points += 0.65
            elif lg.result == CheckInResult.REST_DAY:
                points += 1.0
        cadence_score = min(100, max(0, int(round((points / len(week_logs)) * 100))))
    else:
        cadence_score = 88

    max_streak = max((n.streak_count for n in daily_nodes), default=0)
    earned_silence_count = sum(1 for n in active_daily if is_earned_silence(n))
    bargain_count = sum(1 for n in active_daily if needs_coach_bargain(n))

    yesterday = today - timedelta(days=1)
    yesterday_logs = await _load_date_logs(session, user.id, yesterday)
    missed_yesterday_unlogged = len(active_daily) > 0 and len(yesterday_logs) == 0

    return MomentumSummaryDTO(
        user_id=user.id,
        first_name=user.first_name,
        timezone=user.timezone,
        coach_intensity=user.coach_intensity,
        morning_brief_time=user.morning_brief_time,
        evening_pulse_time=user.evening_pulse_time,
        cadence_score=cadence_score,
        active_streak_days=max_streak,
        completed_today=completed_today,
        total_today=len(active_daily),
        earned_silence_count=earned_silence_count,
        bargain_active_count=bargain_count,
        missed_yesterday_unlogged=missed_yesterday_unlogged,
    )


async def get_today_view(
    session: AsyncSession, user_id: int, target_date: Optional[date] = None
) -> TodayViewResponse:
    today = target_date or date.today()
    user = await ensure_user(session, user_id)
    node_map = await _load_user_nodes(session, user_id)
    today_logs = await _load_date_logs(session, user_id, today)

    daily_nodes = [
        n
        for n in node_map.values()
        if n.horizon == HorizonLevel.DAILY and n.status != GoalStatus.ARCHIVED
    ]
    cards = [_build_today_card(n, node_map, today_logs) for n in daily_nodes]
    summary = await compute_momentum_summary(session, user, today)
    return TodayViewResponse(summary=summary, date=today, goals=cards)


async def get_cascade_tree(
    session: AsyncSession, user_id: int, target_date: Optional[date] = None
) -> list[GoalTreeNodeDTO]:
    today = target_date or date.today()
    await ensure_user(session, user_id)
    node_map = await _load_user_nodes(session, user_id)
    today_logs = await _load_date_logs(session, user_id, today)

    dto_map: dict[str, GoalTreeNodeDTO] = {}
    for n in node_map.values():
        if n.status == GoalStatus.ARCHIVED:
            continue
        pct = (
            min(100, int(round((n.current_value / n.target_value) * 100)))
            if n.target_value > 0
            else 0
        )
        log = today_logs.get(n.id)
        dto_map[n.id] = GoalTreeNodeDTO(
            id=n.id,
            parent_id=n.parent_id,
            horizon=n.horizon,
            category=n.category,
            title=n.title,
            metric_type=n.metric_type,
            target_value=n.target_value,
            current_value=n.current_value,
            progress_pct=pct,
            streak_count=n.streak_count,
            consecutive_misses=n.consecutive_misses,
            earned_silence=is_earned_silence(n),
            needs_bargain=needs_coach_bargain(n),
            status=n.status,
            today_result=log.result if log else None,
            children=[],
        )

    roots: list[GoalTreeNodeDTO] = []
    for dto in dto_map.values():
        if dto.parent_id and dto.parent_id in dto_map:
            dto_map[dto.parent_id].children.append(dto)
        else:
            roots.append(dto)

    return roots


async def _cascade_parent_progress(
    node: GoalNode, node_map: dict[str, GoalNode], delta: float
) -> None:
    """Propagates daily execution deltas upward to Weekly, Monthly, and Annual nodes."""
    curr = node_map.get(node.parent_id) if node.parent_id else None
    while curr:
        if curr.horizon == HorizonLevel.WEEKLY:
            curr.current_value = max(0.0, min(curr.target_value, curr.current_value + delta))
        elif curr.horizon in (HorizonLevel.MONTHLY, HorizonLevel.ANNUAL):
            step = delta * 2.5
            curr.current_value = max(0.0, min(curr.target_value, curr.current_value + step))
        curr = node_map.get(curr.parent_id) if curr.parent_id else None


async def toggle_checkin(
    session: AsyncSession,
    user_id: int,
    goal_id: str,
    result: CheckInResult,
    user_note: Optional[str] = None,
    logged_date: Optional[date] = None,
) -> CheckInToggleResponse:
    today = logged_date or date.today()
    user = await ensure_user(session, user_id)
    node_map = await _load_user_nodes(session, user_id)
    goal = node_map.get(goal_id)
    if not goal:
        raise ValueError(f"GoalNode {goal_id} not found for user {user_id}")

    existing_res = await session.execute(
        select(CheckInLog).where(
            and_(
                CheckInLog.user_id == user_id,
                CheckInLog.goal_id == goal_id,
                CheckInLog.logged_date == today,
            )
        )
    )
    existing_log = existing_res.scalar_one_or_none()
    previous_result = existing_log.result if existing_log else None

    val_map = {
        CheckInResult.DONE: 1.0,
        CheckInResult.PARTIAL: 0.5,
        CheckInResult.MISSED: 0.0,
        CheckInResult.REST_DAY: 0.0,
    }
    new_val = val_map.get(result, 0.0)
    old_val = val_map.get(previous_result, 0.0) if previous_result else 0.0
    delta = new_val - old_val

    if existing_log:
        existing_log.result = result
        existing_log.value_logged = new_val
        if user_note is not None:
            existing_log.user_note = user_note
    else:
        existing_log = CheckInLog(
            goal_id=goal_id,
            user_id=user_id,
            logged_date=today,
            result=result,
            value_logged=new_val,
            user_note=user_note,
        )
        session.add(existing_log)

    # Update streak & consecutive misses only when result changes
    if previous_result != result:
        if result == CheckInResult.DONE:
            if previous_result == CheckInResult.MISSED and goal.consecutive_misses > 0:
                goal.consecutive_misses = max(0, goal.consecutive_misses - 1)
            goal.streak_count += 1
            goal.consecutive_misses = 0
        elif result == CheckInResult.PARTIAL:
            goal.consecutive_misses = 0
            if goal.streak_count == 0:
                goal.streak_count = 1
        elif result == CheckInResult.MISSED:
            if previous_result == CheckInResult.DONE and goal.streak_count > 0:
                goal.streak_count = max(0, goal.streak_count - 1)
            goal.streak_count = 0
            goal.consecutive_misses += 1

        goal.current_value = max(0.0, min(goal.target_value, goal.current_value + delta))
        await _cascade_parent_progress(goal, node_map, delta)

    await session.commit()

    today_logs = await _load_date_logs(session, user_id, today)
    card = _build_today_card(goal, node_map, today_logs)
    summary = await compute_momentum_summary(session, user, today)
    bargain_triggered = card.needs_bargain

    if result == CheckInResult.DONE:
        if card.earned_silence:
            feedback = (
                f"Locked in ({goal.streak_count}d streak). Earned Silence active — "
                f"morning reminders suppressed for '{goal.title}'."
            )
        else:
            feedback = (
                f"Logged Done. {goal.streak_count}d rhythm compounding into "
                f"{card.parent_monthly_title or 'your Monthly target'}."
            )
    elif result == CheckInResult.PARTIAL:
        feedback = (
            f"Partial rep recorded for '{goal.title}'. Continuity preserved; "
            f"zero-day avoided."
        )
    elif result == CheckInResult.MISSED:
        if bargain_triggered:
            feedback = (
                f"2 consecutive misses on '{goal.title}'. Coach's Bargain triggered: "
                f"choose a tactical adjustment rather than forcing a broken scope."
            )
        else:
            feedback = (
                f"Logged Missed as a clean data point. Resume rhythm tomorrow at "
                f"{user.morning_brief_time}."
            )
    else:
        feedback = f"Rest day logged for '{goal.title}'."

    return CheckInToggleResponse(
        goal=card,
        summary=summary,
        coach_feedback=feedback,
        bargain_triggered=bargain_triggered,
    )


async def apply_coach_bargain(
    session: AsyncSession,
    user_id: int,
    goal_id: str,
    action: str,
) -> BargainActionResponse:
    """Rule 3: Resolves the Coach's Bargain (2x Snooze/Miss tactical trade-off)."""
    node_map = await _load_user_nodes(session, user_id)
    goal = node_map.get(goal_id)
    if not goal:
        raise ValueError(f"Goal {goal_id} not found")

    if action == "MICRO_5M":
        # Convert today's check-in into a PARTIAL micro-rep & clear miss counter
        await toggle_checkin(
            session=session,
            user_id=user_id,
            goal_id=goal_id,
            result=CheckInResult.PARTIAL,
            user_note="Completed 5-min Coach's Bargain micro-version",
        )
        goal.consecutive_misses = 0
        msg = (
            f"5-minute micro-version logged as Partial for '{goal.title}'. "
            f"Friction broken and momentum preserved."
        )
    elif action == "SCALE_BACK_25":
        new_target = max(1.0, float(math.floor(goal.target_value * 0.75 * 10) / 10))
        goal.target_value = new_target
        goal.consecutive_misses = 0
        if goal.parent_id and goal.parent_id in node_map:
            parent = node_map[goal.parent_id]
            parent.target_value = max(1.0, round(parent.target_value * 0.75, 1))
        msg = (
            f"Weekly load scaled back by 25% (new target: {goal.target_value}/wk). "
            f"Consistency beats over-scoping."
        )
    elif action == "PAUSE_MONDAY":
        goal.status = GoalStatus.PAUSED
        goal.consecutive_misses = 0
        msg = (
            f"'{goal.title}' paused until Monday. Focus bandwidth on your remaining "
            f"active Lead Measures."
        )
    else:
        raise ValueError(f"Unknown bargain action: {action}")

    await session.commit()
    return BargainActionResponse(
        goal_id=goal.id,
        action=action,
        coach_message=msg,
        updated_title=goal.title,
        updated_target=goal.target_value,
        updated_status=goal.status,
    )


async def handle_diagnostic_action(
    session: AsyncSession,
    user_id: int,
    action: str,
) -> str:
    """Rule 2: Resolves the 10:00 next-morning Diagnostic Check without nagging."""
    yesterday = date.today() - timedelta(days=1)
    node_map = await _load_user_nodes(session, user_id)
    daily_nodes = [
        n
        for n in node_map.values()
        if n.horizon == HorizonLevel.DAILY and n.status == GoalStatus.ACTIVE
    ]

    if action == "LOG_YESTERDAY_ALL":
        for node in daily_nodes:
            await toggle_checkin(
                session=session,
                user_id=user_id,
                goal_id=node.id,
                result=CheckInResult.DONE,
                user_note="Batch logged via morning Diagnostic Check",
                logged_date=yesterday,
            )
        return f"Logged all {len(daily_nodes)} daily Lead Measures as Done for yesterday. Streaks updated."
    elif action == "CRAZY_DAY_RESUME":
        for node in daily_nodes:
            await toggle_checkin(
                session=session,
                user_id=user_id,
                goal_id=node.id,
                result=CheckInResult.REST_DAY,
                user_note="Crazy day — grace rest day applied",
                logged_date=yesterday,
            )
        return "Yesterday marked as an unplanned Rest Day. Zero streak penalty. Eyes on today's cadence."
    elif action == "ADJUST_WEEKLY_LOAD":
        for node in daily_nodes:
            node.target_value = max(1.0, round(node.target_value * 0.8, 1))
            node.consecutive_misses = 0
        await session.commit()
        return "Weekly target load reduced by 20% across active Daily habits to restore sustainable rhythm."
    return "Diagnostic check acknowledged."


async def apply_cascade_proposal(
    session: AsyncSession,
    user_id: int,
    proposal: CascadeProposal,
    replace_existing: bool = True,
) -> list[GoalTreeNodeDTO]:
    """Persists an AI-generated CascadeProposal hierarchy into GoalNode adjacency rows."""
    await ensure_user(session, user_id)
    if replace_existing:
        existing = await _load_user_nodes(session, user_id)
        for node in existing.values():
            node.status = GoalStatus.ARCHIVED
        await session.flush()

    for annual in proposal.annual_goals:
        annual_node = GoalNode(
            id=str(uuid.uuid4()),
            user_id=user_id,
            horizon=HorizonLevel.ANNUAL,
            category=annual.category,
            title=annual.title,
            metric_type=MetricType.NUMERIC,
            target_value=100.0,
            current_value=0.0,
        )
        session.add(annual_node)
        await session.flush()

        for monthly in annual.monthly_targets:
            monthly_node = GoalNode(
                id=str(uuid.uuid4()),
                user_id=user_id,
                parent_id=annual_node.id,
                horizon=HorizonLevel.MONTHLY,
                category=annual.category,
                title=monthly.title,
                metric_type=MetricType.NUMERIC,
                target_value=100.0,
                current_value=0.0,
            )
            session.add(monthly_node)
            await session.flush()

            for weekly in monthly.weekly_milestones:
                weekly_node = GoalNode(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    parent_id=monthly_node.id,
                    horizon=HorizonLevel.WEEKLY,
                    category=annual.category,
                    title=f"{weekly.title} ({weekly.target_metric})",
                    metric_type=MetricType.NUMERIC,
                    target_value=float(
                        sum(d.frequency_per_week for d in weekly.daily_actions) or 5.0
                    ),
                    current_value=0.0,
                )
                session.add(weekly_node)
                await session.flush()

                for daily in weekly.daily_actions:
                    daily_node = GoalNode(
                        id=str(uuid.uuid4()),
                        user_id=user_id,
                        parent_id=weekly_node.id,
                        horizon=HorizonLevel.DAILY,
                        category=annual.category,
                        title=daily.title,
                        metric_type=MetricType.BOOLEAN,
                        target_value=float(daily.frequency_per_week),
                        current_value=0.0,
                    )
                    session.add(daily_node)

    await session.commit()
    return await get_cascade_tree(session, user_id)


async def get_scorecard(session: AsyncSession, user_id: int) -> ScorecardResponse:
    today = date.today()
    user = await ensure_user(session, user_id)
    summary = await compute_momentum_summary(session, user, today)
    node_map = await _load_user_nodes(session, user_id)

    weekly_days: list[ScorecardDayDTO] = []
    for offset in range(6, -1, -1):
        d = today - timedelta(days=offset)
        logs = await _load_date_logs(session, user_id, d)
        done_c = sum(1 for lg in logs.values() if lg.result == CheckInResult.DONE)
        part_c = sum(1 for lg in logs.values() if lg.result == CheckInResult.PARTIAL)
        miss_c = sum(1 for lg in logs.values() if lg.result == CheckInResult.MISSED)
        total = max(1, summary.total_today)
        pct = min(100, int(round(((done_c + part_c * 0.5) / total) * 100)))
        weekly_days.append(
            ScorecardDayDTO(
                date=d.isoformat(),
                label=d.strftime("%a"),
                completion_pct=pct,
                done_count=done_c,
                partial_count=part_c,
                missed_count=miss_c,
            )
        )

    horizon_audit: list[HorizonAuditItemDTO] = []
    monthly_nodes = [
        n
        for n in node_map.values()
        if n.horizon == HorizonLevel.MONTHLY and n.status != GoalStatus.ARCHIVED
    ]
    for mnode in monthly_nodes:
        parent_annual = node_map.get(mnode.parent_id) if mnode.parent_id else None
        weekly_children = [
            n for n in node_map.values() if n.parent_id == mnode.id and n.status != GoalStatus.ARCHIVED
        ]
        if weekly_children:
            w_pct = int(
                round(
                    sum(
                        min(100.0, (w.current_value / max(1.0, w.target_value)) * 100.0)
                        for w in weekly_children
                    )
                    / len(weekly_children)
                )
            )
        else:
            w_pct = 75
        m_pct = min(100, int(round((mnode.current_value / max(1.0, mnode.target_value)) * 100)))
        if m_pct >= 75:
            status_label = "ON_TRACK"
        elif m_pct >= 50:
            status_label = "SLIPPING"
        else:
            status_label = "BLOCKER"

        horizon_audit.append(
            HorizonAuditItemDTO(
                monthly_goal_id=mnode.id,
                monthly_title=mnode.title,
                annual_title=parent_annual.title if parent_annual else "Annual North Star",
                category=mnode.category or "General",
                weekly_execution_pct=w_pct,
                monthly_milestone_pct=m_pct,
                status_label=status_label,
            )
        )

    slipping = [h for h in horizon_audit if h.status_label != "ON_TRACK"]
    if summary.bargain_active_count > 0:
        diag_q = (
            "Evening Mobility has hit 2 consecutive misses while morning blocks remain at 100%. "
            "Should we anchor mobility immediately after your Zone-2 run or scale its weekly target by 25%?"
        )
    elif slipping:
        diag_q = (
            f"Weekly execution on '{slipping[0].monthly_title}' is at {slipping[0].weekly_execution_pct}%, "
            f"while the Monthly milestone sits at {slipping[0].monthly_milestone_pct}%. "
            f"Are the daily Lead Measures moving the needle, or do we need to rescope?"
        )
    else:
        diag_q = (
            f"You are operating at {summary.cadence_score}% Cadence across {summary.total_today} daily Lead Measures. "
            f"Which single bottleneck, if removed this week, would accelerate your Q4 Monthly milestones?"
        )

    return ScorecardResponse(
        summary=summary,
        weekly_days=weekly_days,
        horizon_audit=horizon_audit,
        diagnostic_question=diag_q,
    )

