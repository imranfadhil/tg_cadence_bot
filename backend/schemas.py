from __future__ import annotations

from datetime import date
from typing import Optional
from pydantic import BaseModel, Field

from backend.models import CheckInResult, CoachIntensity, GoalStatus, HorizonLevel, MetricType


# --- Section 6.2: Goal Cascade Decomposition Schema (LLM Structured Output) ---
class DailyNodeDraft(BaseModel):
    title: str = Field(..., description="Specific controllable daily action, e.g. '45m Deep Code Block'")
    frequency_per_week: int = Field(
        default=5, ge=1, le=7, description="e.g., 5 for weekdays, 7 for daily"
    )


class WeeklyNodeDraft(BaseModel):
    title: str = Field(..., description="Weekly execution lead milestone")
    target_metric: str = Field(..., description="Measurable weekly target, e.g. '4 sessions / week'")
    daily_actions: list[DailyNodeDraft]


class MonthlyNodeDraft(BaseModel):
    title: str = Field(..., description="Monthly lag/lead bridge target")
    weekly_milestones: list[WeeklyNodeDraft]


class AnnualGoalDraft(BaseModel):
    title: str = Field(..., description="North Star annual objective")
    category: str = Field(..., description="e.g., 'Engineering', 'Fitness', 'Reading'")
    monthly_targets: list[MonthlyNodeDraft]


class CascadeProposal(BaseModel):
    coach_summary: str = Field(
        ...,
        description="Calm, analytical coach note (<90 words) connecting daily lead actions to annual lag outcomes.",
    )
    annual_goals: list[AnnualGoalDraft]


# --- REST API Schemas for Telegram Mini App ---
class GoalTreeNodeDTO(BaseModel):
    id: str
    parent_id: Optional[str] = None
    horizon: HorizonLevel
    category: Optional[str] = None
    title: str
    metric_type: MetricType
    target_value: float
    current_value: float
    progress_pct: int
    streak_count: int
    consecutive_misses: int
    earned_silence: bool = False
    needs_bargain: bool = False
    status: GoalStatus
    today_result: Optional[CheckInResult] = None
    children: list["GoalTreeNodeDTO"] = Field(default_factory=list)


GoalTreeNodeDTO.model_rebuild()


class TodayGoalCardDTO(BaseModel):
    id: str
    title: str
    category: Optional[str] = None
    parent_weekly_title: Optional[str] = None
    parent_monthly_title: Optional[str] = None
    parent_annual_title: Optional[str] = None
    breadcrumb: str
    target_value: float
    current_value: float
    streak_count: int
    consecutive_misses: int
    earned_silence: bool
    needs_bargain: bool
    status: GoalStatus
    today_result: Optional[CheckInResult] = None
    today_note: Optional[str] = None


class MomentumSummaryDTO(BaseModel):
    user_id: int
    first_name: str
    timezone: str
    coach_intensity: CoachIntensity
    morning_brief_time: str
    evening_pulse_time: str
    cadence_score: int
    active_streak_days: int
    completed_today: int
    total_today: int
    earned_silence_count: int
    bargain_active_count: int
    missed_yesterday_unlogged: bool = False


class TodayViewResponse(BaseModel):
    summary: MomentumSummaryDTO
    date: date
    goals: list[TodayGoalCardDTO]


class CheckInToggleRequest(BaseModel):
    goal_id: str
    result: CheckInResult
    user_note: Optional[str] = None
    logged_date: Optional[date] = None


class CheckInToggleResponse(BaseModel):
    goal: TodayGoalCardDTO
    summary: MomentumSummaryDTO
    coach_feedback: str
    bargain_triggered: bool = False


class BargainActionRequest(BaseModel):
    goal_id: str
    action: str  # "MICRO_5M" | "SCALE_BACK_25" | "PAUSE_MONDAY"


class BargainActionResponse(BaseModel):
    goal_id: str
    action: str
    coach_message: str
    updated_title: str
    updated_target: float
    updated_status: GoalStatus


class GoalCreateOrUpdateRequest(BaseModel):
    title: str
    horizon: HorizonLevel = HorizonLevel.DAILY
    parent_id: Optional[str] = None
    category: Optional[str] = None
    target_value: float = 5.0
    status: GoalStatus = GoalStatus.ACTIVE


class OnboardingBrainDumpRequest(BaseModel):
    text: Optional[str] = None
    ogg_audio_base64: Optional[str] = None
    less_aggressive: bool = False


class ScorecardDayDTO(BaseModel):
    date: str
    label: str
    completion_pct: int
    done_count: int
    partial_count: int
    missed_count: int


class HorizonAuditItemDTO(BaseModel):
    monthly_goal_id: str
    monthly_title: str
    annual_title: str
    category: str
    weekly_execution_pct: int
    monthly_milestone_pct: int
    status_label: str  # "ON_TRACK" | "SLIPPING" | "BLOCKER"


class ScorecardResponse(BaseModel):
    summary: MomentumSummaryDTO
    weekly_days: list[ScorecardDayDTO]
    horizon_audit: list[HorizonAuditItemDTO]
    diagnostic_question: str

