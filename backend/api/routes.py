from __future__ import annotations

import json
import urllib.parse
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import get_db, seed_demo_data
from backend.models import GoalNode, MetricType
from backend.schemas import (
    BargainActionRequest,
    BargainActionResponse,
    CascadeProposal,
    CheckInToggleRequest,
    CheckInToggleResponse,
    GoalCreateOrUpdateRequest,
    GoalTreeNodeDTO,
    OnboardingBrainDumpRequest,
    ScorecardResponse,
    TodayViewResponse,
)
from backend.services.coach_ai import decompose_goals_to_cascade, scale_down_proposal
from backend.services.streak_engine import (
    apply_cascade_proposal,
    apply_coach_bargain,
    ensure_user,
    get_cascade_tree,
    get_scorecard,
    get_today_view,
    handle_diagnostic_action,
    reset_user_cadence,
    toggle_checkin,
)

router = APIRouter(tags=["cadence"])


class AuthUnlockRequest(BaseModel):
    passphrase: str


async def _extract_user_id_from_headers(
    x_telegram_init_data: Optional[str],
    x_user_id: Optional[int],
) -> int:
    if x_user_id:
        return x_user_id
    if x_telegram_init_data:
        try:
            parsed = dict(urllib.parse.parse_qsl(x_telegram_init_data))
            user_raw = parsed.get("user")
            if user_raw:
                user_obj = json.loads(user_raw)
                return int(user_obj["id"])
        except Exception:
            pass
    return settings.DEMO_USER_ID


async def resolve_current_user_id(
    x_telegram_init_data: Optional[str] = Header(default=None),
    x_user_id: Optional[int] = Header(default=None),
    x_access_passphrase: Optional[str] = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> int:
    """Extracts the Telegram user ID and enforces ACCESS_PASSPHRASE / PIN gate."""
    uid = await _extract_user_id_from_headers(x_telegram_init_data, x_user_id)
    user = await ensure_user(db, uid)

    if settings.is_passphrase_enabled:
        header_valid = bool(
            x_access_passphrase and settings.verify_passphrase(x_access_passphrase)
        )
        # If opened inside Telegram WebApp by an already-unlocked Telegram user, allow automatically
        telegram_user_unlocked = bool(x_telegram_init_data and user.is_authorized == 1)

        if header_valid and not user.is_authorized:
            user.is_authorized = 1
            await db.commit()

        if not (header_valid or telegram_user_unlocked):
            raise HTTPException(
                status_code=401,
                detail="Access restricted. Valid passphrase or PIN required.",
            )

    await seed_demo_data(db, uid)
    return uid


@router.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "cadence-featherweight-api"}


@router.post("/auth/unlock")
async def api_auth_unlock(
    payload: AuthUnlockRequest,
    x_telegram_init_data: Optional[str] = Header(default=None),
    x_user_id: Optional[int] = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, bool | str]:
    if not settings.verify_passphrase(payload.passphrase):
        raise HTTPException(status_code=401, detail="Invalid passphrase or PIN.")

    uid = await _extract_user_id_from_headers(x_telegram_init_data, x_user_id)
    user = await ensure_user(db, uid)
    user.is_authorized = 1
    await db.commit()
    await seed_demo_data(db, uid)
    return {"authorized": True, "message": "Access granted."}


@router.get("/checkins/today", response_model=TodayViewResponse)
async def api_get_today_checkins(
    user_id: int = Depends(resolve_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> TodayViewResponse:
    return await get_today_view(db, user_id)


@router.post("/checkins/toggle", response_model=CheckInToggleResponse)
async def api_toggle_checkin(
    payload: CheckInToggleRequest,
    user_id: int = Depends(resolve_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> CheckInToggleResponse:
    try:
        return await toggle_checkin(
            session=db,
            user_id=user_id,
            goal_id=payload.goal_id,
            result=payload.result,
            user_note=payload.user_note,
            logged_date=payload.logged_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/checkins/bargain", response_model=BargainActionResponse)
async def api_resolve_bargain(
    payload: BargainActionRequest,
    user_id: int = Depends(resolve_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> BargainActionResponse:
    try:
        return await apply_coach_bargain(
            session=db,
            user_id=user_id,
            goal_id=payload.goal_id,
            action=payload.action,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/checkins/diagnostic")
async def api_resolve_diagnostic(
    payload: dict[str, str],
    user_id: int = Depends(resolve_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    action = payload.get("action", "CRAZY_DAY_RESUME")
    msg = await handle_diagnostic_action(db, user_id, action)
    return {"message": msg}


@router.get("/goals/tree", response_model=list[GoalTreeNodeDTO])
async def api_get_goals_tree(
    user_id: int = Depends(resolve_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[GoalTreeNodeDTO]:
    return await get_cascade_tree(db, user_id)


@router.post("/goals", response_model=list[GoalTreeNodeDTO])
async def api_create_goal(
    payload: GoalCreateOrUpdateRequest,
    user_id: int = Depends(resolve_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[GoalTreeNodeDTO]:
    node = GoalNode(
        id=str(uuid.uuid4()),
        user_id=user_id,
        parent_id=payload.parent_id,
        horizon=payload.horizon,
        category=payload.category or "General",
        title=payload.title,
        metric_type=MetricType.NUMERIC,
        target_value=payload.target_value,
        current_value=0.0,
        status=payload.status,
    )
    db.add(node)
    await db.commit()
    return await get_cascade_tree(db, user_id)


@router.patch("/goals/{goal_id}", response_model=list[GoalTreeNodeDTO])
async def api_update_goal(
    goal_id: str,
    payload: GoalCreateOrUpdateRequest,
    user_id: int = Depends(resolve_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[GoalTreeNodeDTO]:
    res = await db.execute(
        select(GoalNode).where(GoalNode.id == goal_id, GoalNode.user_id == user_id)
    )
    node = res.scalar_one_or_none()
    if not node:
        raise HTTPException(status_code=404, detail="Goal node not found")

    node.title = payload.title
    node.target_value = payload.target_value
    node.status = payload.status
    if payload.category:
        node.category = payload.category
    await db.commit()
    return await get_cascade_tree(db, user_id)


@router.get("/scorecard", response_model=ScorecardResponse)
async def api_get_scorecard(
    user_id: int = Depends(resolve_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> ScorecardResponse:
    return await get_scorecard(db, user_id)


@router.post("/onboarding/decompose", response_model=CascadeProposal)
async def api_onboarding_decompose(
    payload: OnboardingBrainDumpRequest,
    _user_id: int = Depends(resolve_current_user_id),
) -> CascadeProposal:
    from backend.services.coach_ai import generate_goal_cascade
    import base64

    ogg_bytes = (
        base64.b64decode(payload.ogg_audio_base64)
        if payload.ogg_audio_base64
        else None
    )
    proposal = await generate_goal_cascade(
        user_text=payload.text,
        ogg_audio_bytes=ogg_bytes,
        less_aggressive=payload.less_aggressive,
    )
    return proposal


@router.post("/onboarding/scale-down", response_model=CascadeProposal)
async def api_onboarding_scale_down(
    proposal: CascadeProposal,
    _user_id: int = Depends(resolve_current_user_id),
) -> CascadeProposal:
    return scale_down_proposal(proposal)


@router.post("/onboarding/lock-in", response_model=list[GoalTreeNodeDTO])
async def api_onboarding_lock_in(
    proposal: CascadeProposal,
    user_id: int = Depends(resolve_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[GoalTreeNodeDTO]:
    return await apply_cascade_proposal(db, user_id, proposal, replace_existing=True)


@router.post("/onboarding/reset")
async def api_onboarding_reset(
    user_id: int = Depends(resolve_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    await reset_user_cadence(db, user_id)
    return {"message": "All template goals and check-in history cleared."}

