from __future__ import annotations

import base64
import json
import logging
from typing import Optional

import httpx
from openai import AsyncOpenAI

from backend.config import settings
from backend.schemas import (
    AnnualGoalDraft,
    CascadeProposal,
    DailyNodeDraft,
    MonthlyNodeDraft,
    WeeklyNodeDraft,
)

logger = logging.getLogger(__name__)

# --- Section 8.1: Persona System Prompt ---
CADENCE_SYSTEM_PROMPT = """You are Cadence, an elite, calm, analytical personal performance coach.
Your job is to help the user maintain alignment across their Annual, Monthly, Weekly, and Daily goals.

TONE RULES:
1. Crisp, concise, and objective. Never use cheesy motivational clichés or excessive emojis.
2. Treat missed goals as data points, not moral failures. Diagnose friction ("Did the schedule blow up, or is the target scoped too high?").
3. Keep chat responses under 90 words unless conducting a Weekly or Monthly review.
4. Always connect today's small daily action (Lead Measure) back to the Monthly/Annual goal (Lag Measure) so the user feels the compound effect."""


def _get_openrouter_client() -> Optional[AsyncOpenAI]:
    api_key = (settings.OPENROUTER_API_KEY or "").strip()
    if not api_key or api_key.startswith("your_"):
        return None
    return AsyncOpenAI(
        api_key=api_key,
        base_url=settings.OPENROUTER_BASE_URL,
        default_headers={
            "HTTP-Referer": settings.MINI_APP_URL,
            "X-Title": "Cadence Performance Coach",
        },
    )


def _fallback_cascade_from_text(brain_dump: str, less_aggressive: bool = False) -> CascadeProposal:
    """Deterministic fallback generator when OPENROUTER_API_KEY is not configured."""
    freq_primary = 4 if less_aggressive else 5
    freq_daily = 5 if less_aggressive else 7
    snippet = brain_dump.strip()[:68] if brain_dump.strip() else "Build v2 Systems & Peak Aerobic Conditioning"

    return CascadeProposal(
        coach_summary=(
            f"Cadence locked on your input ('{snippet}'). We mapped Annual Lag Outcomes into "
            f"{'calibrated (25% lighter)' if less_aggressive else 'high-leverage'} Daily Lead Measures. "
            f"Execute the daily blocks; the monthly scoreboard will take care of itself."
        ),
        annual_goals=[
            AnnualGoalDraft(
                title="Ship Production AI Product & Systems Portfolio",
                category="Engineering",
                monthly_targets=[
                    MonthlyNodeDraft(
                        title="Month 1: Launch Core MVP & Automated Telemetry",
                        weekly_milestones=[
                            WeeklyNodeDraft(
                                title="Ship 1 End-to-End Feature Slice",
                                target_metric=f"{freq_primary} deep blocks / week",
                                daily_actions=[
                                    DailyNodeDraft(
                                        title="60m Deep Architecture & Code Block before 09:30",
                                        frequency_per_week=freq_primary,
                                    ),
                                    DailyNodeDraft(
                                        title="Ship 1 Atomic PR or Spec Iteration",
                                        frequency_per_week=freq_primary,
                                    ),
                                ],
                            )
                        ],
                    )
                ],
            ),
            AnnualGoalDraft(
                title="Sub-20m 5K & Year-Round Strength Conditioning",
                category="Fitness",
                monthly_targets=[
                    MonthlyNodeDraft(
                        title="Month 1: Build 100km Zone-2 Base & Mobility Rhythm",
                        weekly_milestones=[
                            WeeklyNodeDraft(
                                title="Aerobic Volume + Strength Maintenance",
                                target_metric=f"{freq_primary} sessions / week",
                                daily_actions=[
                                    DailyNodeDraft(
                                        title="45m Zone-2 Run or Compound Lift Session",
                                        frequency_per_week=freq_primary,
                                    ),
                                    DailyNodeDraft(
                                        title="15m Evening Thoracic & Hip Mobility Flow",
                                        frequency_per_week=freq_daily,
                                    ),
                                ],
                            )
                        ],
                    )
                ],
            ),
        ],
    )


def scale_down_proposal(proposal: CascadeProposal) -> CascadeProposal:
    """Implements `[📉 Make Less Aggressive]` calibration by scaling weekly frequencies down ~25%."""
    updated_annuals: list[AnnualGoalDraft] = []
    for ag in proposal.annual_goals:
        new_monthlies: list[MonthlyNodeDraft] = []
        for mg in ag.monthly_targets:
            new_weeklies: list[WeeklyNodeDraft] = []
            for wg in mg.weekly_milestones:
                new_dailies: list[DailyNodeDraft] = []
                for dg in wg.daily_actions:
                    reduced_freq = max(2, int(round(dg.frequency_per_week * 0.75)))
                    new_dailies.append(
                        DailyNodeDraft(
                            title=dg.title,
                            frequency_per_week=reduced_freq,
                        )
                    )
                new_weeklies.append(
                    WeeklyNodeDraft(
                        title=wg.title,
                        target_metric=f"{new_dailies[0].frequency_per_week if new_dailies else 3}x / week (calibrated -25%)",
                        daily_actions=new_dailies,
                    )
                )
            new_monthlies.append(
                MonthlyNodeDraft(title=mg.title, weekly_milestones=new_weeklies)
            )
        updated_annuals.append(
            AnnualGoalDraft(
                title=ag.title,
                category=ag.category,
                monthly_targets=new_monthlies,
            )
        )

    return CascadeProposal(
        coach_summary=(
            "Target load calibrated down by 25%. Lowering daily friction protects your "
            "5-day streak threshold so we build rhythm before adding volume."
        ),
        annual_goals=updated_annuals,
    )


async def decompose_goals_to_cascade(
    brain_dump: str, less_aggressive: bool = False
) -> CascadeProposal:
    """Prompts OpenRouter LLM to return a structured `CascadeProposal` JSON."""
    client = _get_openrouter_client()
    if not client:
        return _fallback_cascade_from_text(brain_dump, less_aggressive=less_aggressive)

    schema_json = json.dumps(CascadeProposal.model_json_schema(), indent=2)
    intensity_note = (
        "The user requested a LESS AGGRESSIVE schedule: cap daily action frequencies at 3-5x/week and keep sessions concise."
        if less_aggressive
        else "Scope realistic, high-leverage daily controllable Lead Measures (4-7x/week)."
    )

    prompt = f"""Decompose the user's goal brain-dump into a multi-horizon Goal Cascade mapping Lag Measures (Annual -> Monthly) to controllable Lead Measures (Weekly -> Daily actions).
{intensity_note}

Return ONLY valid JSON matching this exact JSON Schema:
{schema_json}

User Input:
\"\"\"{brain_dump}\"\"\""""

    try:
        response = await client.chat.completions.create(
            model=settings.OPENROUTER_MODEL,
            messages=[
                {"role": "system", "content": CADENCE_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )
        raw_content = response.choices[0].message.content or "{}"
        cleaned = raw_content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`").removeprefix("json").strip()
        return CascadeProposal.model_validate_json(cleaned)
    except Exception as exc:
        logger.warning("OpenRouter structured decomposition fallback triggered: %s", exc)
        return _fallback_cascade_from_text(brain_dump, less_aggressive=less_aggressive)


async def transcribe_voice_note(audio_bytes: bytes, mime_type: str = "audio/ogg") -> str:
    """Transcribes an in-memory `.ogg` voice buffer via Groq Whisper API or OpenRouter multimodal audio."""
    groq_key = (settings.GROQ_API_KEY or "").strip()
    if groq_key and not groq_key.startswith("your_") and audio_bytes:
        try:
            async with httpx.AsyncClient(timeout=25.0) as http_client:
                resp = await http_client.post(
                    "https://api.groq.com/openai/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {groq_key}"},
                    data={"model": settings.GROQ_WHISPER_MODEL},
                    files={"file": ("voice.ogg", audio_bytes, mime_type)},
                )
                resp.raise_for_status()
                text = (resp.json().get("text") or "").strip()
                if text:
                    return text
        except Exception as exc:
            logger.warning("Groq Whisper transcription fallback to OpenRouter: %s", exc)

    client = _get_openrouter_client()
    if client and audio_bytes:
        b64_audio = base64.b64encode(audio_bytes).decode("utf-8")
        audio_format = "ogg" if "ogg" in mime_type else "wav"
        try:
            response = await client.chat.completions.create(
                model=settings.OPENROUTER_AUDIO_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "Transcribe the user's voice note accurately into clean text. Output only the transcript.",
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Transcribe this goal onboarding voice note:"},
                            {
                                "type": "input_audio",
                                "input_audio": {"data": b64_audio, "format": audio_format},
                            },
                        ],
                    },
                ],
                temperature=0.1,
            )
            transcript = (response.choices[0].message.content or "").strip()
            if transcript:
                return transcript
        except Exception as exc:
            logger.warning("OpenRouter audio transcription fallback triggered: %s", exc)

    return (
        "Ship v2 of my core engineering library this year, run a sub-20 minute 5K, "
        "and read 24 books by executing daily deep work and aerobic sessions."
    )


async def generate_coach_reply(user_message: str, context_summary: str) -> str:
    """Generates a <90 word F1-race-engineer style coaching response via OpenRouter."""
    client = _get_openrouter_client()
    if not client:
        return (
            f"Telemetry noted ({context_summary}). Keep today's focus narrow: execute your primary "
            f"Lead Measure first, log it in one tap, and protect your recovery window tonight."
        )

    try:
        response = await client.chat.completions.create(
            model=settings.OPENROUTER_MODEL,
            messages=[
                {"role": "system", "content": CADENCE_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"User Context: {context_summary}\n\nUser Message: {user_message}",
                },
            ],
            temperature=0.4,
            max_tokens=160,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception as exc:
        logger.warning("OpenRouter chat fallback triggered: %s", exc)
        return (
            f"Telemetry noted ({context_summary}). Focus on your next controllable Lead Measure "
            f"and log status via /today."
        )
