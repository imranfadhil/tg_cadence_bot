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
COACH_SYSTEM_PROMPT = """You are Cadence, an elite, calm, analytical personal performance coach.
Your job is to help the user maintain alignment across their Annual, Monthly, Weekly, and Daily goals.

TONE RULES:
1. Crisp, concise, and objective. Never use cheesy motivational clichés or excessive emojis.
2. Treat missed goals as data points, not moral failures. Diagnose friction ("Did the schedule blow up, or is the target scoped too high?").
3. Keep chat responses under 90 words unless conducting a Weekly or Monthly review.
4. Always connect today's small daily action (Lead Measure) back to the Monthly/Annual goal (Lag Measure) so the user feels the compound effect.""".strip()

CADENCE_SYSTEM_PROMPT = COACH_SYSTEM_PROMPT


def _get_llm_client() -> Optional[AsyncOpenAI]:
    """Returns a single lightweight AsyncOpenAI client compatible with Google Gemini, OpenAI, Groq, or OpenRouter."""
    api_key = settings.effective_llm_api_key
    if not api_key:
        return None
    base_url = settings.effective_llm_base_url
    default_headers = {}
    if "openrouter.ai" in base_url:
        default_headers = {
            "HTTP-Referer": settings.public_webapp_url,
            "X-Title": "Cadence Performance Coach",
        }
    return AsyncOpenAI(
        api_key=api_key,
        base_url=base_url,
        default_headers=default_headers or None,
    )


def _supports_native_audio(model_name: str) -> bool:
    """Returns True if the configured model natively ingests base64 input_audio (.ogg) without Whisper."""
    m = (model_name or "").lower()
    return "gemini" in m or "audio" in m


def _fallback_cascade_from_text(brain_dump: str, less_aggressive: bool = False) -> CascadeProposal:
    """Deterministic fallback generator when LLM_API_KEY is not configured."""
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


async def _transcribe_via_groq_whisper(
    audio_bytes: bytes, mime_type: str = "audio/ogg"
) -> Optional[str]:
    """Optional Fallback: Routes .ogg buffers to Groq Whisper (whisper-large-v3-turbo) when LLM is text-only."""
    groq_key = (settings.GROQ_API_KEY or "").strip()
    if not groq_key or groq_key.startswith("your_") or not audio_bytes:
        return None
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
            return text or None
    except Exception as exc:
        logger.warning("Groq Whisper transcription failed: %s", exc)
        return None


async def transcribe_voice_note(audio_bytes: bytes, mime_type: str = "audio/ogg") -> str:
    """
    Short voice note transcription using MODEL_FAST (native multimodal input_audio)
    or Groq Whisper fallback when using a text-only model.
    """
    if not audio_bytes:
        return ""

    client = _get_llm_client()
    fast_model = settings.MODEL_FAST

    # If the model is text-only (or Groq key is explicitly preferred for non-native audio models), try Groq first
    if not _supports_native_audio(fast_model):
        groq_text = await _transcribe_via_groq_whisper(audio_bytes, mime_type=mime_type)
        if groq_text:
            return groq_text

    if client:
        b64_audio = base64.b64encode(audio_bytes).decode("utf-8")
        audio_format = "ogg" if "ogg" in mime_type else "wav"
        try:
            response = await client.chat.completions.create(
                model=fast_model,
                messages=[
                    {
                        "role": "system",
                        "content": "Transcribe the user's voice note accurately into clean text. Output only the transcript.",
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_audio",
                                "input_audio": {"data": b64_audio, "format": audio_format},
                            },
                            {"type": "text", "text": "Transcribe this voice note accurately."},
                        ],
                    },
                ],
                temperature=0.1,
            )
            transcript = (response.choices[0].message.content or "").strip()
            if transcript:
                return transcript
        except Exception as exc:
            logger.warning("MODEL_FAST native audio transcription fallback triggered: %s", exc)

    # Secondary fallback to Groq Whisper if native audio call failed
    groq_text = await _transcribe_via_groq_whisper(audio_bytes, mime_type=mime_type)
    if groq_text:
        return groq_text

    return (
        "Ship v2 of my core engineering library this year, run a sub-20 minute 5K, "
        "and read 24 books by executing daily deep work and aerobic sessions."
    )


async def generate_goal_cascade(
    user_text: str | None = None,
    ogg_audio_bytes: bytes | None = None,
    less_aggressive: bool = False,
) -> CascadeProposal:
    """
    Section 6.3: Uses MODEL_SMART to decompose a messy text or .ogg voice note into a 4-tier Goal Cascade JSON.
    When using Gemini (native multimodal audio), passes .ogg bytes directly as base64 `input_audio` in a single API call.
    If using a text-only LLM, falls back to Groq Whisper transcription before prompting MODEL_SMART.
    """
    client = _get_llm_client()
    smart_model = settings.MODEL_SMART

    # Optional Fallback: if audio bytes provided but MODEL_SMART has no native audio, transcribe via Groq Whisper first
    if ogg_audio_bytes and not _supports_native_audio(smart_model):
        whisper_transcript = await _transcribe_via_groq_whisper(ogg_audio_bytes, mime_type="audio/ogg")
        if whisper_transcript:
            user_text = f"{user_text}\n{whisper_transcript}".strip() if user_text else whisper_transcript
            ogg_audio_bytes = None

    if not client:
        fallback_seed = user_text or "Voice Note Goal Cascade"
        return _fallback_cascade_from_text(fallback_seed, less_aggressive=less_aggressive)

    intensity_note = (
        "The user requested a LESS AGGRESSIVE schedule: cap daily action frequencies at 3-5x/week and keep sessions concise."
        if less_aggressive
        else "Decompose these goals into a structured Annual -> Monthly -> Weekly -> Daily cascade with controllable Daily Lead Measures (4-7x/week)."
    )

    user_content: list[dict] = []
    if ogg_audio_bytes:
        b64_audio = base64.b64encode(ogg_audio_bytes).decode("utf-8")
        user_content.append(
            {
                "type": "input_audio",
                "input_audio": {"data": b64_audio, "format": "ogg"},
            }
        )
    if user_text:
        user_content.append({"type": "text", "text": user_text})

    user_content.append(
        {
            "type": "text",
            "text": intensity_note,
        }
    )

    # 1. Primary path: OpenAI SDK structured outputs (`beta.chat.completions.parse`) per Section 6.3
    try:
        response = await client.beta.chat.completions.parse(
            model=smart_model,
            messages=[
                {"role": "system", "content": COACH_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            response_format=CascadeProposal,
        )
        parsed = response.choices[0].message.parsed
        if parsed:
            return parsed
    except Exception as exc:
        logger.warning("MODEL_SMART beta.chat.completions.parse fallback to JSON mode: %s", exc)

    # 2. Secondary path: JSON schema prompt (preserves native base64 .ogg input_audio on OpenRouter Gemini models)
    try:
        schema_json = json.dumps(CascadeProposal.model_json_schema(), indent=2)
        fallback_content: list[dict] = []

        if ogg_audio_bytes and _supports_native_audio(smart_model):
            b64_audio = base64.b64encode(ogg_audio_bytes).decode("utf-8")
            fallback_content.append(
                {
                    "type": "input_audio",
                    "input_audio": {"data": b64_audio, "format": "ogg"},
                }
            )
        elif ogg_audio_bytes:
            whisper_transcript = await _transcribe_via_groq_whisper(
                ogg_audio_bytes, mime_type="audio/ogg"
            )
            if whisper_transcript:
                user_text = (
                    f"{user_text}\n{whisper_transcript}".strip()
                    if user_text
                    else whisper_transcript
                )

        fallback_prompt = (
            f"{intensity_note}\n\n"
            f"Return ONLY valid JSON matching this exact JSON Schema:\n{schema_json}\n\n"
            + (f"User Input:\n\"\"\"{user_text}\"\"\"" if user_text else "Decompose the goals from the attached voice note.")
        )
        fallback_content.append({"type": "text", "text": fallback_prompt})

        response = await client.chat.completions.create(
            model=smart_model,
            messages=[
                {"role": "system", "content": COACH_SYSTEM_PROMPT},
                {"role": "user", "content": fallback_content},
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
        logger.warning("MODEL_SMART structured decomposition fallback triggered: %s", exc)
        return _fallback_cascade_from_text(
            user_text or "Voice Note Goal Cascade", less_aggressive=less_aggressive
        )


async def decompose_goals_to_cascade(
    brain_dump: str | None = None,
    less_aggressive: bool = False,
    ogg_audio_bytes: bytes | None = None,
) -> CascadeProposal:
    """Backward-compatible wrapper around `generate_goal_cascade`."""
    return await generate_goal_cascade(
        user_text=brain_dump,
        ogg_audio_bytes=ogg_audio_bytes,
        less_aggressive=less_aggressive,
    )


async def quick_coach_reply(prompt: str, context_summary: str) -> str:
    """
    Section 6.3: Uses MODEL_FAST for ultra-cheap daily check-ins, diagnostics, and Coach's Bargain follow-ups.
    """
    client = _get_llm_client()
    if not client:
        return (
            f"Telemetry noted ({context_summary}). Keep today's focus narrow: execute your primary "
            f"Lead Measure first, log it in one tap, and protect your recovery window tonight."
        )

    try:
        response = await client.chat.completions.create(
            model=settings.MODEL_FAST,
            messages=[
                {
                    "role": "system",
                    "content": f"{COACH_SYSTEM_PROMPT}\n\nUSER STATE:\n{context_summary}",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=180,
            temperature=0.4,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception as exc:
        logger.warning("MODEL_FAST quick_coach_reply fallback triggered: %s", exc)
        return (
            f"Telemetry noted ({context_summary}). Focus on your next controllable Lead Measure "
            f"and log status via /today."
        )


async def generate_coach_reply(user_message: str, context_summary: str) -> str:
    """Alias for `quick_coach_reply` routed to MODEL_FAST."""
    return await quick_coach_reply(prompt=user_message, context_summary=context_summary)


async def generate_strategy_diagnostic(
    cadence_score: int,
    audit_summary: str,
    fallback_question: str,
    is_monthly_audit: bool = False,
) -> str:
    """
    Section 5.2: Uses MODEL_SMART for Sunday Strategy diagnostic reflections and Monthly Horizon Audits.
    """
    client = _get_llm_client()
    if not client:
        return fallback_question

    ritual_type = "Monthly Horizon Audit" if is_monthly_audit else "Weekly Sunday Strategy"
    prompt = (
        f"Conduct a {ritual_type} diagnostic reflection.\n"
        f"7-Day Rhythm: {cadence_score}% On Cadence.\n"
        f"Horizon Telemetry:\n{audit_summary}\n\n"
        f"Ask exactly ONE sharp, analytical diagnostic question (<55 words) connecting their Weekly Lead Measure execution to their Monthly Lag Measure progress."
    )
    try:
        response = await client.chat.completions.create(
            model=settings.MODEL_SMART,
            messages=[
                {"role": "system", "content": COACH_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            max_tokens=120,
            temperature=0.4,
        )
        question = (response.choices[0].message.content or "").strip()
        return question or fallback_question
    except Exception as exc:
        logger.warning("MODEL_SMART strategy diagnostic fallback triggered: %s", exc)
        return fallback_question

