# Cadence — AI Personal Performance Coach (Featherweight Edition)

Built from [`cadence_product_technical_specification.md`](./cadence_product_technical_specification.md) for deployment on a shared VPS / Droplet with a **strict `< 100 MB` idle RAM footprint**.

## Featherweight Architecture Highlights
1. **Single-Process Unified Event Loop (`--workers 1`)**: Runs **FastAPI**, **aiogram 3.x**, and **APScheduler (`AsyncIOScheduler`)** inside one Python `asyncio` loop via FastAPI's `lifespan`.
2. **Zero External Daemons (`./data/cadence.db` in WAL Mode)**: Uses **SQLite 3** (`aiosqlite` + SQLAlchemy 2.0 Async) with `PRAGMA journal_mode=WAL;`, `PRAGMA synchronous=NORMAL;`, `PRAGMA busy_timeout=5000;`, and `PRAGMA foreign_keys=ON;`. `APScheduler` persists jobs in the same `./data/cadence.db` file via `SQLAlchemyJobStore` (`apscheduler_jobs` table).
3. **Zero-Server Frontend Hosting**: The React 18 + Tailwind CSS Telegram Mini App (`frontend/dist`) is compiled at build time and mounted directly at `/` by FastAPI `StaticFiles`. No Node.js process runs in production.
4. **Zero Heavy Local Libraries**: Voice notes are downloaded into an in-memory `io.BytesIO` buffer and transcribed via **Groq Whisper API (`whisper-large-v3-turbo`)** or **OpenRouter multimodal audio**, while goal cascade decomposition uses **OpenRouter Structured Outputs**. All charts render client-side in pure CSS/SVG.

---

## Production Deployment (Shared Droplet)

1. Configure [`.env`](./.env):
   ```env
   TELEGRAM_BOT_TOKEN=your_botfather_token
   OPENROUTER_API_KEY=your_openrouter_api_key
   GROQ_API_KEY=your_optional_groq_whisper_key
   MINI_APP_URL=https://cadence.yourdomain.com
   ```
2. Build and launch the single 150MB-capped container:
   ```bash
   docker compose up -d --build
   ```
   The unified app listens on `127.0.0.1:8040` (ready to reverse-proxy with Nginx or Caddy) and persists `./data/cadence.db` + `./data/cadence.db-wal` on the host.

---

## Local Single-Process Run

```powershell
# 1. Build the static frontend once
cd frontend
npm install
npm run build
cd ..

# 2. Run the unified single-worker server (serves both /api/* and the Mini App at /)
.\.venv\Scripts\uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 1
```
Open **`http://localhost:8000`** to use the compiled Telegram Mini App Studio served directly by FastAPI.
