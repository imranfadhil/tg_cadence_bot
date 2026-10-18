# Cadence — Product & Technical Specification (Featherweight Edition)

> **Vibe Coding Context File:** Drop this file into the root of your repository and reference it (`@CADENCE_SPEC.md`) when prompting your AI coding assistant.
> **Hardware Target:** Shared VPS / Droplet alongside other apps. **Strict RAM budget: < 100 MB idle.**

## 1. Project Overview & Core Philosophy

**Cadence** is an AI-powered personal trainer and multi-horizon goal accountability system built on **Telegram** (Bot + Telegram Mini App / WebApp).

* **The Problem:** Traditional habit trackers and reminder bots cause notification fatigue. Users mute them within 2 weeks because they act like nagging cron jobs with high logging friction.
* **The Solution:** Cadence combines **zero-friction 1-tap chat check-ins**, **voice-first onboarding**, **context-aware persistence** (rigorous standards, empathetic to real-life chaos), and a **clean, light-themed Telegram Mini App (TWA)** for visual goal hierarchy management.
* **Brand Persona:** Calm, analytical, high-performance coach. Think "F1 Race Engineer meets Olympic Strength Coach." Concise, data-informed, never preachy, focused on rhythm and momentum.

---

## 2. Featherweight Architecture Constraints (CRITICAL FOR AI CODING)

To run smoothly alongside other apps on a small shared Droplet (~60–85 MB total RAM footprint), the AI assistant **MUST** adhere to these strict architectural rules:

1. **Single-Process Unified Event Loop (`--workers 1`):**
   * Run **FastAPI**, **aiogram 3.x**, and **APScheduler (`AsyncIOScheduler`)** inside a **single Python `asyncio` event loop** managed by FastAPI's `lifespan` context manager.
   * **NEVER** create separate containers or processes for the bot, web server, or task queue.
2. **Zero External Daemons (No Postgres, No Redis, No Celery):**
   * Use **SQLite (`aiosqlite` + SQLAlchemy 2.0 Async)** stored in a single `./data/cadence.db` file.
   * Enable **`PRAGMA journal_mode=WAL;`** and **`PRAGMA synchronous=NORMAL;`** on startup so concurrent reads from the Mini App and writes from bot check-ins never lock the database.
   * Persist `APScheduler` jobs inside the same SQLite database (`SQLAlchemyJobStore`) so scheduled check-ins survive restarts with zero Redis overhead.
3. **Zero-Server Frontend Hosting:**
   * Compile the Vite + React + Tailwind frontend at build time (`npm run build`) and serve the static `dist/` folder directly from FastAPI using `StaticFiles` (or host on Cloudflare Pages for 0 MB local overhead). Never keep a Node.js server running in production.
4. **Zero Heavy Local Libraries:**
   * **FORBIDDEN packages:** `torch`, `faster-whisper`, `pandas`, `numpy`, `matplotlib`, `pillow`, `playwright`.
   * Offload all LLM reasoning and voice transcription to external APIs (**Groq Whisper API** / **OpenAI** / **Gemini Flash**).
   * Render all weekly/monthly scorecards and charts client-side in the Telegram Mini App using pure SVG / CSS instead of generating images on the server.

---

## 3. UI/UX & Design System (Clean Light Theme)

The Telegram Mini App (TWA) acts as the visual control center for viewing the cascading goal tree, editing metrics, and inspecting weekly/monthly scorecards.

### 3.1 Aesthetic Direction

* **Vibe:** Minimalist editorial utility—inspired by **Linear (Light Mode)**, **Things 3**, and **Apple Health**.
* **Surface Hierarchy:** Crisp, high-contrast typography on warm alabaster/off-white backgrounds with subtle 1px borders and soft micro-shadows. No heavy drop shadows or neon gradients.

### 3.2 Color Palette (Tailwind CSS Tokens)

* **Background Primary:** `#FAFAFA` (`bg-neutral-50`) — Main app canvas
* **Background Surface / Cards:** `#FFFFFF` (`bg-white`) — Goal cards, modals, sheets
* **Background Subtle / Muted:** `#F4F4F5` (`bg-zinc-100`) — Secondary buttons, pill backgrounds, progress track
* **Border Primary:** `#E4E4E7` (`border-zinc-200`) — Hairline card dividers
* **Text Primary:** `#18181B` (`text-zinc-900`) — Headings, active goal titles
* **Text Secondary:** `#52525B` (`text-zinc-600`) — Subtitles, parent goal breadcrumbs
* **Text Muted:** `#A1A1AA` (`text-zinc-400`) — Timestamps, inactive labels
* **Brand Accent (CadenceCobalt):** `#2563EB` (`bg-blue-600` / `text-blue-600`) — Primary CTAs, active horizon indicators, focus rings
* **Semantic Status Colors:**
  * **On Track / Done:** `#10B981` (`emerald-500`) with `#ECFDF5` (`emerald-50`) badge fill
  * **Partial / Slipping:** `#F59E0B` (`amber-500`) with `#FFFBEB` (`amber-50`) badge fill
  * **Missed / Blocker:** `#F43F5E` (`rose-500`) with `#FFF1F2` (`rose-50`) badge fill

### 3.3 Typography & Micro-Interactions

* **Font Stack:** `Inter` or system SF Pro (`font-sans`) for UI; `JetBrains Mono` (`font-mono`) for streaks, percentages, and completion metrics.
* **Telegram Native Integration:**
  * Force Light Mode header and background colors via `window.Telegram.WebApp.setHeaderColor('#FAFAFA')` and `setBackgroundColor('#FAFAFA')`.
  * Trigger native haptic feedback (`window.Telegram.WebApp.HapticFeedback.impactOccurred('light')`) on every goal toggle, horizon tab switch, and cascade expansion.

---

## 4. Core Functional Workflows

### 4.1 "The Cascade" Onboarding (Voice/Text to Tree)

1. **Input:** User sends a voice note or text paragraph to the Telegram Bot describing their goals for the year.
2. **AI Decomposition:** Backend downloads the `.ogg` voice buffer in memory, sends it to Groq/OpenAI Whisper API, and prompts the LLM to generate a structured JSON hierarchy mapping **Lag Measures** (Annual $\rightarrow$ Monthly) to **Lead Measures** (Weekly $\rightarrow$ Daily controllable actions).
3. **Preview & Calibration:**
   * Bot replies with a clean formatted summary of the tree and an inline keyboard:
     * `[✅ Lock In Cadence]`
     * `[📉 Make Less Aggressive]`
     * `[🎛️ Edit in Studio (Mini App)]`

### 4.2 Multi-Horizon Rituals

| Horizon | Ritual Name | Default Schedule | UX Pattern |
| :--- | :--- | :--- | :--- |
| **Daily** | **Morning Brief** | 08:00 Local | Read-only focus message listing today's 1–3 Lead Measures + `[⚡ Open Today's View]` TWA button. |
| **Daily** | **Evening Pulse** | 21:00 Local | Interactive inline keyboard per daily goal: `[✅ Done]` `[⚠️ Partial]` `[❌ Missed]`. Zero typing required. |
| **Weekly** | **Sunday Strategy** | Sun 18:00 Local | Bot sends a text scorecard + deep-link button to the TWA Weekly Review sheet + asks 1 diagnostic question via chat/voice. |
| **Monthly** | **Horizon Audit** | Last Sun of Month | Evaluates whether high Weekly execution actually moved Monthly milestone percentages. |
| **Annual** | **North Star Check** | Quarterly | Full tree review in the Mini App to archive completed goals or pivot priorities. |

### 4.3 The "Non-Annoying Rigor" State Machine

* **Rule 1: Earned Silence:** If a user hits a 5-day streak on a Daily goal, suppress morning reminders for that specific habit and switch to a minimalist badge in the Evening Pulse.
* **Rule 2: No Nagging Repeats:** Never send the exact same reminder twice. If the 21:00 Evening Pulse is ignored, wait until 10:00 the next morning and send a **Diagnostic Check**:
  * *"Missed yesterday's pulse. Crazy day, or did we hit friction on the plan?"*
  * Inline Buttons: `[Log Yesterday All ✅]` `[Crazy Day - Resume Today]` `[Adjust Weekly Load]`
* **Rule 3: The Coach's Bargain (2x Snooze/Miss):** If a user misses or snoozes a specific daily habit twice in a row, trigger an immediate tactical trade-off:
  * `[Do a 5-min micro-version now]`
  * `[Scale back weekly target by 25%]`
  * `[Pause habit until Monday]`

---

## 5. Technical Stack & Directory Structure

### 5.1 Featherweight Stack

* **Runtime:** Single Python 3.12-slim process (`uvicorn backend.main:app --workers 1`)
* **Web & Bot Framework:** **FastAPI** + **aiogram 3.x** (running inside FastAPI `lifespan`)
* **Database:** **SQLite 3** (`aiosqlite` + **SQLAlchemy 2.0 Async**) with `WAL` mode enabled
* **Scheduler:** **APScheduler 3.x** (`AsyncIOScheduler` backed by SQLite `SQLAlchemyJobStore`)
* **AI & Voice APIs:** `httpx` or lightweight OpenAI/Gemini client (Groq `whisper-large-v3-turbo` for fast/cheap voice transcription + `gpt-4o-mini` or `gemini-2.5-flash` for structured JSON output)
* **Frontend (Telegram Mini App):** **React 18 (Vite, TypeScript)** + **Tailwind CSS** + **Lucide Icons** (compiled to static assets and mounted at `/` by FastAPI)

### 5.2 Directory Structure

```text
cadence/
├── CADENCE_SPEC.md
├── Dockerfile                  # Multi-stage build (Node build -> python:3.12-slim)
├── docker-compose.yml          # Single container capped at 150MB RAM
├── .env.example
├── data/                       # Mounted volume for cadence.db & cadence.db-wal
├── backend/
│   ├── main.py                 # Unified entrypoint: FastAPI + aiogram + APScheduler + StaticFiles
│   ├── config.py               # Pydantic Settings
│   ├── database.py             # Async SQLite setup + PRAGMA WAL event listener
│   ├── models.py               # DB Tables (User, GoalNode, CheckInLog)
│   ├── schemas.py              # Pydantic models for API & LLM Structured Outputs
│   ├── bot/
│   │   ├── handlers.py         # Onboarding, daily check-ins, voice notes, callbacks
│   │   └── keyboards.py        # Inline keyboards & Mini App WebAppInfo buttons
│   ├── services/
│   │   ├── coach_ai.py         # Lightweight API calls for Whisper & LLM JSON trees
│   │   ├── scheduler.py        # In-process AsyncIOScheduler jobs per user
│   │   └── streak_engine.py    # Earned silence & Coach's Bargain state logic
│   └── api/
│       └── routes.py           # REST endpoints for the Telegram Mini App (/api/*)
└── frontend/                   # Built at deploy time into static HTML/CSS/JS
    ├── index.html
    ├── src/
    │   ├── App.tsx
    │   ├── components/
    │   │   ├── HorizonTabs.tsx     # Today | Cascade Tree | Scorecard
    │   │   ├── GoalCascadeTree.tsx # Collapsible parent-child visual hierarchy
    │   │   ├── TodayCheckInCard.tsx# 1-tap clean light-mode logging cards
    │   │   └── MomentumHeader.tsx  # Streak counter & cadence score pill
    │   └── lib/
    │       ├── telegram.ts         # TWA SDK wrapper & light theme enforcer
    │       └── api.ts              # Fetch client with Telegram initData auth
```

---

## 6. Reference Blueprints for Single-Process Setup

### 6.1 SQLite WAL Mode Setup (`backend/database.py`)

```python
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

DATABASE_URL = "sqlite+aiosqlite:///./data/cadence.db"

engine = create_async_engine(DATABASE_URL, echo=False)

# Enforce WAL mode and busy_timeout on every SQLite connection
@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA synchronous=NORMAL;")
    cursor.execute("PRAGMA busy_timeout=5000;")
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.close()

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
```

### 6.2 Unified FastAPI + Aiogram + Scheduler Entrypoint (`backend/main.py`)

```python
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from aiogram import Bot, Dispatcher
from backend.database import engine
from backend.models import Base
from backend.services.scheduler import scheduler
from backend.bot.handlers import router as bot_router
from backend.api.routes import router as api_router
from backend.config import settings

bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
dp = Dispatcher()
dp.include_router(bot_router)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Initialize SQLite tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # 2. Start in-process AsyncIOScheduler
    scheduler.start()
    
    # 3. Start Telegram Bot polling as a background task in the SAME event loop
    # (Or use webhook endpoint if preferred; background polling uses 0 extra ports)
    polling_task = asyncio.create_task(dp.start_polling(bot, handle_signals=False))
    
    yield
    
    # Graceful teardown
    polling_task.cancel()
    scheduler.shutdown(wait=False)
    await bot.session.close()

app = FastAPI(title="Cadence Featherweight API", lifespan=lifespan)
app.include_router(api_router, prefix="/api")

# Serve compiled React Mini App static files from the same process
app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="static")
```

### 6.3 Resource-Capped `docker-compose.yml`

```yaml
services:
  cadence:
    build: .
    container_name: cadence_app
    restart: unless-stopped
    env_file: .env
    volumes:
      - ./data:/app/data
    ports:
      - "127.0.0.1:8040:8000" # Reverse proxy via existing Nginx/Caddy on droplet
    deploy:
      resources:
        limits:
          memory: 150M
```

---

## 7. Database Schema (Relational / Adjacency List)

```python
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

# 1. Users Table
# - id (BigInt, Telegram User ID, PK)
# - username, first_name, timezone (default "Asia/Kuala_Lumpur")
# - morning_brief_time (default "08:00"), evening_pulse_time (default "21:00")
# - coach_intensity (Enum: "STANDARD", "HIGH_RIGOR", "RECOVERY_MODE")

# 2. GoalNodes Table (Self-Referencing Adjacency List)
# - id (String UUID, PK)
# - user_id (FK -> Users.id)
# - parent_id (String UUID, FK -> GoalNodes.id, nullable=True for ANNUAL roots)
# - horizon (Enum: HorizonLevel)
# - title (String, e.g., "45m Deep Code Block")
# - metric_type (Enum: "BOOLEAN", "NUMERIC", "DURATION")
# - target_value (Float, e.g., 1.0 for daily boolean, 4.0 for 4x/week)
# - current_value (Float, default 0.0)
# - streak_count (Int, default 0)
# - consecutive_misses (Int, default 0) -> Triggers "Coach's Bargain" at >= 2
# - status (Enum: GoalStatus)

# 3. CheckInLogs Table
# - id (String UUID, PK)
# - goal_id (FK -> GoalNodes.id)
# - user_id (FK -> Users.id)
# - logged_date (Date, indexed)
# - result (Enum: CheckInResult)
# - value_logged (Float)
# - user_note (Text, nullable - populated if user replies via voice/text)
```

---

## 8. AI System Prompts & Structured Output Contracts

### 8.1 Persona System Prompt (`services/coach_ai.py`)

```text
You are Cadence, an elite, calm, analytical personal performance coach.
Your job is to help the user maintain alignment across their Annual, Monthly, Weekly, and Daily goals.

TONE RULES:
1. Crisp, concise, and objective. Never use cheesy motivational clichés or excessive emojis.
2. Treat missed goals as data points, not moral failures. Diagnose friction ("Did the schedule blow up, or is the target scoped too high?").
3. Keep chat responses under 90 words unless conducting a Weekly or Monthly review.
4. Always connect today's small daily action (Lead Measure) back to the Monthly/Annual goal (Lag Measure) so the user feels the compound effect.
```

### 8.2 Goal Cascade Decomposition Schema (Pydantic)

```python
class DailyNodeDraft(BaseModel):
    title: str
    frequency_per_week: int # e.g., 5 for weekdays, 7 for daily

class WeeklyNodeDraft(BaseModel):
    title: str
    target_metric: str
    daily_actions: list[DailyNodeDraft]

class MonthlyNodeDraft(BaseModel):
    title: str
    weekly_milestones: list[WeeklyNodeDraft]

class AnnualGoalDraft(BaseModel):
    title: str
    category: str # e.g., "Engineering", "Fitness", "Reading"
    monthly_targets: list[MonthlyNodeDraft]

class CascadeProposal(BaseModel):
    coach_summary: str
    annual_goals: list[AnnualGoalDraft]
```

---

## 9. Step-by-Step "Vibe Coding" Implementation Roadmap

Use these exact phases to prompt your AI assistant in VS Code one step at a time:

* **Phase 1: Clean Light-Mode Mini App Prototype (`frontend/`)**
  * Scaffold Vite + React + Tailwind with mock data. Build the `#FAFAFA` light layout, `MomentumHeader`, `HorizonTabs` (`Today` | `Cascade Tree` | `Scorecard`), 1-tap `TodayCheckInCard`, and collapsible `GoalCascadeTree`.
* **Phase 2: Featherweight SQLite WAL & Unified FastAPI Server (`backend/`)**
  * Implement `database.py` (SQLite WAL), `models.py`, and `main.py` mounting the API routes alongside the compiled static frontend.
* **Phase 3: Telegram Bot & 1-Tap Check-In Loop (`backend/bot/`)**
  * Add `aiogram` handlers for `/start`, `/today`, and inline callback queries (`checkin:<goal_id>:<status>`). Wire up real-time streak updates and the 2-miss "Coach's Bargain" keyboard.
* **Phase 4: Voice/Text Cascade Onboarding & In-Process Scheduler (`backend/services/`)**
  * Connect Groq/OpenAI Whisper + Structured Outputs for `/setup` and register per-user Morning Brief / Evening Pulse jobs in `AsyncIOScheduler`.