from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Enum as SqlEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class HorizonLevel(str, Enum):
    ANNUAL = "ANNUAL"
    MONTHLY = "MONTHLY"
    WEEKLY = "WEEKLY"
    DAILY = "DAILY"


class GoalStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"


class CheckInResult(str, Enum):
    DONE = "DONE"
    PARTIAL = "PARTIAL"
    MISSED = "MISSED"
    REST_DAY = "REST_DAY"


class CoachIntensity(str, Enum):
    STANDARD = "STANDARD"
    HIGH_RIGOR = "HIGH_RIGOR"
    RECOVERY_MODE = "RECOVERY_MODE"


class MetricType(str, Enum):
    BOOLEAN = "BOOLEAN"
    NUMERIC = "NUMERIC"
    DURATION = "DURATION"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    first_name: Mapped[str] = mapped_column(String(128), default="Athlete")
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kuala_Lumpur")
    morning_brief_time: Mapped[str] = mapped_column(String(8), default="08:00")
    evening_pulse_time: Mapped[str] = mapped_column(String(8), default="21:00")
    coach_intensity: Mapped[CoachIntensity] = mapped_column(
        SqlEnum(CoachIntensity), default=CoachIntensity.STANDARD
    )
    is_authorized: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    goals: Mapped[list["GoalNode"]] = relationship(
        "GoalNode", back_populates="user", cascade="all, delete-orphan"
    )
    checkins: Mapped[list["CheckInLog"]] = relationship(
        "CheckInLog", back_populates="user", cascade="all, delete-orphan"
    )
    coach_state: Mapped[Optional["CoachState"]] = relationship(
        "CoachState",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )


class GoalNode(Base):
    __tablename__ = "goal_nodes"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    parent_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("goal_nodes.id", ondelete="CASCADE"), nullable=True, index=True
    )
    horizon: Mapped[HorizonLevel] = mapped_column(SqlEnum(HorizonLevel), index=True)
    category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    title: Mapped[str] = mapped_column(String(255))
    metric_type: Mapped[MetricType] = mapped_column(
        SqlEnum(MetricType), default=MetricType.BOOLEAN
    )
    target_value: Mapped[float] = mapped_column(Float, default=1.0)
    current_value: Mapped[float] = mapped_column(Float, default=0.0)
    streak_count: Mapped[int] = mapped_column(Integer, default=0)
    consecutive_misses: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[GoalStatus] = mapped_column(
        SqlEnum(GoalStatus), default=GoalStatus.ACTIVE
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship("User", back_populates="goals")
    parent: Mapped[Optional["GoalNode"]] = relationship(
        "GoalNode", remote_side=[id], back_populates="children"
    )
    children: Mapped[list["GoalNode"]] = relationship(
        "GoalNode", back_populates="parent", cascade="all, delete-orphan"
    )
    checkins: Mapped[list["CheckInLog"]] = relationship(
        "CheckInLog", back_populates="goal", cascade="all, delete-orphan"
    )


class CheckInLog(Base):
    __tablename__ = "checkin_logs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    goal_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("goal_nodes.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    logged_date: Mapped[date] = mapped_column(Date, index=True)
    result: Mapped[CheckInResult] = mapped_column(SqlEnum(CheckInResult))
    value_logged: Mapped[float] = mapped_column(Float, default=1.0)
    user_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    goal: Mapped["GoalNode"] = relationship("GoalNode", back_populates="checkins")
    user: Mapped["User"] = relationship("User", back_populates="checkins")


class CoachState(Base):
    """Stores pending onboarding cascade drafts and anti-nag state per user."""

    __tablename__ = "coach_states"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    pending_proposal_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_pulse_sent_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    last_diagnostic_sent_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    awaiting_onboarding_input: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship("User", back_populates="coach_state")
