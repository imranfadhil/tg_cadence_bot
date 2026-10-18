from __future__ import annotations

import uuid
from datetime import date, timedelta
from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.config import DATA_DIR, settings
from backend.models import (
    Base,
    CheckInLog,
    CheckInResult,
    CoachIntensity,
    CoachState,
    GoalNode,
    HorizonLevel,
    MetricType,
    User,
)

# Ensure ./data directory exists before SQLite opens ./data/cadence.db
DATA_DIR.mkdir(parents=True, exist_ok=True)
if "///./data/" in settings.DATABASE_URL:
    Path("./data").mkdir(parents=True, exist_ok=True)

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)


# --- Section 6.1: Enforce WAL mode and busy_timeout on every SQLite connection ---
@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA synchronous=NORMAL;")
    cursor.execute("PRAGMA busy_timeout=5000;")
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.close()


AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def seed_demo_data(session: AsyncSession, user_id: int = settings.DEMO_USER_ID) -> User:
    """Seeds a realistic multi-horizon Cascade Goal Tree if the user has no goals yet."""
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        user = User(
            id=user_id,
            username="cadence_athlete",
            first_name="Alex",
            timezone=settings.DEFAULT_TIMEZONE,
            morning_brief_time=settings.DEFAULT_MORNING_BRIEF,
            evening_pulse_time=settings.DEFAULT_EVENING_PULSE,
            coach_intensity=CoachIntensity.STANDARD,
        )
        session.add(user)
        await session.flush()

    state_res = await session.execute(select(CoachState).where(CoachState.user_id == user_id))
    existing_state = state_res.scalar_one_or_none()

    goals_res = await session.execute(select(GoalNode).where(GoalNode.user_id == user_id))
    existing_goals = goals_res.scalars().all()
    if existing_goals or existing_state:
        if not existing_state:
            session.add(CoachState(user_id=user_id))
        await session.commit()
        return user

    session.add(CoachState(user_id=user_id))

    # --- Tree 1: Engineering (Ship v2 Library & Core Systems) ---
    annual_eng = GoalNode(
        id=str(uuid.uuid4()),
        user_id=user_id,
        horizon=HorizonLevel.ANNUAL,
        category="Engineering",
        title="Ship v2 Open-Source Core & Scale Architecture",
        metric_type=MetricType.NUMERIC,
        target_value=100.0,
        current_value=74.0,
        streak_count=12,
    )
    monthly_eng = GoalNode(
        id=str(uuid.uuid4()),
        user_id=user_id,
        parent_id=annual_eng.id,
        horizon=HorizonLevel.MONTHLY,
        category="Engineering",
        title="Q4: Ship v2 Library Release Candidate",
        metric_type=MetricType.NUMERIC,
        target_value=100.0,
        current_value=82.0,
        streak_count=8,
    )
    weekly_eng = GoalNode(
        id=str(uuid.uuid4()),
        user_id=user_id,
        parent_id=monthly_eng.id,
        horizon=HorizonLevel.WEEKLY,
        category="Engineering",
        title="5x Deep Architecture & Benchmark Sessions",
        metric_type=MetricType.NUMERIC,
        target_value=5.0,
        current_value=4.0,
        streak_count=6,
    )
    daily_eng_1 = GoalNode(
        id=str(uuid.uuid4()),
        user_id=user_id,
        parent_id=weekly_eng.id,
        horizon=HorizonLevel.DAILY,
        category="Engineering",
        title="60m Uninterrupted Deep Code Block (Pre-09:30)",
        metric_type=MetricType.DURATION,
        target_value=5.0,
        current_value=5.0,
        streak_count=6,  # >= 5 triggers Earned Silence badge
        consecutive_misses=0,
    )
    daily_eng_2 = GoalNode(
        id=str(uuid.uuid4()),
        user_id=user_id,
        parent_id=weekly_eng.id,
        horizon=HorizonLevel.DAILY,
        category="Engineering",
        title="Write 1 Architecture RFC Section / PR Review",
        metric_type=MetricType.BOOLEAN,
        target_value=5.0,
        current_value=3.5,
        streak_count=3,
        consecutive_misses=0,
    )

    # --- Tree 2: Athletic Performance (Sub-20m 5K & Strength Rhythm) ---
    annual_fit = GoalNode(
        id=str(uuid.uuid4()),
        user_id=user_id,
        horizon=HorizonLevel.ANNUAL,
        category="Fitness",
        title="Sub-20m 5K & 1.8x BW Deadlift Conditioning",
        metric_type=MetricType.NUMERIC,
        target_value=100.0,
        current_value=68.0,
        streak_count=9,
    )
    monthly_fit = GoalNode(
        id=str(uuid.uuid4()),
        user_id=user_id,
        parent_id=annual_fit.id,
        horizon=HorizonLevel.MONTHLY,
        category="Fitness",
        title="October: 120km Aerobic Base + 12 Strength Lifts",
        metric_type=MetricType.NUMERIC,
        target_value=100.0,
        current_value=70.0,
        streak_count=5,
    )
    weekly_fit = GoalNode(
        id=str(uuid.uuid4()),
        user_id=user_id,
        parent_id=monthly_fit.id,
        horizon=HorizonLevel.WEEKLY,
        category="Fitness",
        title="4x Zone-2 Run + 3x Compound Strength",
        metric_type=MetricType.NUMERIC,
        target_value=7.0,
        current_value=5.0,
        streak_count=5,
    )
    daily_fit_1 = GoalNode(
        id=str(uuid.uuid4()),
        user_id=user_id,
        parent_id=weekly_fit.id,
        horizon=HorizonLevel.DAILY,
        category="Fitness",
        title="45m Zone-2 Aerobic Run or Strength Protocol",
        metric_type=MetricType.DURATION,
        target_value=6.0,
        current_value=5.0,
        streak_count=5,  # Earned Silence
        consecutive_misses=0,
    )
    daily_fit_2 = GoalNode(
        id=str(uuid.uuid4()),
        user_id=user_id,
        parent_id=weekly_fit.id,
        horizon=HorizonLevel.DAILY,
        category="Fitness",
        title="15m Evening Thoracic & Hip Mobility Flow",
        metric_type=MetricType.DURATION,
        target_value=7.0,
        current_value=2.0,
        streak_count=0,
        consecutive_misses=2,  # >= 2 triggers Coach's Bargain
    )

    # --- Tree 3: Synthesis & Reading ---
    annual_read = GoalNode(
        id=str(uuid.uuid4()),
        user_id=user_id,
        horizon=HorizonLevel.ANNUAL,
        category="Reading",
        title="Read 24 Foundational Systems & History Books",
        metric_type=MetricType.NUMERIC,
        target_value=24.0,
        current_value=19.0,
        streak_count=14,
    )
    monthly_read = GoalNode(
        id=str(uuid.uuid4()),
        user_id=user_id,
        parent_id=annual_read.id,
        horizon=HorizonLevel.MONTHLY,
        category="Reading",
        title="Complete 2 Technical Monographs + Synthesis Notes",
        metric_type=MetricType.NUMERIC,
        target_value=2.0,
        current_value=1.6,
        streak_count=7,
    )
    weekly_read = GoalNode(
        id=str(uuid.uuid4()),
        user_id=user_id,
        parent_id=monthly_read.id,
        horizon=HorizonLevel.WEEKLY,
        category="Reading",
        title="150 Pages + Sunday Zettelkasten Digest",
        metric_type=MetricType.NUMERIC,
        target_value=7.0,
        current_value=6.0,
        streak_count=7,
    )
    daily_read = GoalNode(
        id=str(uuid.uuid4()),
        user_id=user_id,
        parent_id=weekly_read.id,
        horizon=HorizonLevel.DAILY,
        category="Reading",
        title="25 Pages Analog Reading (Phone Outside Bedroom)",
        metric_type=MetricType.NUMERIC,
        target_value=7.0,
        current_value=6.0,
        streak_count=7,  # Earned Silence
        consecutive_misses=0,
    )

    all_nodes = [
        annual_eng,
        monthly_eng,
        weekly_eng,
        daily_eng_1,
        daily_eng_2,
        annual_fit,
        monthly_fit,
        weekly_fit,
        daily_fit_1,
        daily_fit_2,
        annual_read,
        monthly_read,
        weekly_read,
        daily_read,
    ]
    session.add_all(all_nodes)
    await session.flush()

    today = date.today()
    daily_nodes = [daily_eng_1, daily_eng_2, daily_fit_1, daily_fit_2, daily_read]
    for offset in range(6, 0, -1):
        day = today - timedelta(days=offset)
        for idx, dnode in enumerate(daily_nodes):
            if dnode.id == daily_fit_2.id and offset <= 2:
                res = CheckInResult.MISSED
                val = 0.0
            elif idx == 1 and offset == 3:
                res = CheckInResult.PARTIAL
                val = 0.5
            else:
                res = CheckInResult.DONE
                val = 1.0
            session.add(
                CheckInLog(
                    goal_id=dnode.id,
                    user_id=user_id,
                    logged_date=day,
                    result=res,
                    value_logged=val,
                )
            )

    session.add(
        CheckInLog(
            goal_id=daily_eng_1.id,
            user_id=user_id,
            logged_date=today,
            result=CheckInResult.DONE,
            value_logged=1.0,
            user_note="Completed benchmark suite refactor before 09:00.",
        )
    )
    session.add(
        CheckInLog(
            goal_id=daily_fit_1.id,
            user_id=user_id,
            logged_date=today,
            result=CheckInResult.DONE,
            value_logged=1.0,
        )
    )

    await session.commit()
    return user


async def init_db() -> None:
    from sqlalchemy import text

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        try:
            await conn.execute(
                text("ALTER TABLE users ADD COLUMN is_authorized INTEGER DEFAULT 0")
            )
        except Exception:
            pass
    async with AsyncSessionLocal() as session:
        await seed_demo_data(session, settings.DEMO_USER_ID)

