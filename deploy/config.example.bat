@echo off
REM ===================================================================
REM  DigitalOcean deployment config for Cadence (AI Performance Coach)
REM  Copy this file to  config.bat  and fill in your values.
REM  config.bat is gitignored so your secrets stay local.
REM
REM  Prereq: doctl installed & authenticated  ->  doctl auth init
REM ===================================================================

REM ---- Project (Isolated from other apps on the same droplet) ----
set PROJECT_NAME=tg-cadence-bot
REM Isolated directory on the droplet where this bot lives
set REMOTE_DIR=/opt/tg_cadence_bot

REM ---- Shared Droplet (Existing DigitalOcean Droplet) ----
set DROPLET_NAME=pemuda-surau-server
set REGION=sgp1
set SIZE=s-1vcpu-2gb
set IMAGE=docker-20-04

REM ---- SSH Key (Existing key authorized on the droplet) ----
set KEY_NAME=pemuda-surau-do-key
set KEY_FILE=%USERPROFILE%\.ssh\%KEY_NAME%
set PUB_FILE=%USERPROFILE%\.ssh\%KEY_NAME%.pub

REM ---- Telegram Cadence Bot Config ----
REM Create a NEW bot with @BotFather -> /newbot and paste its token here
REM (or leave blank here to read TELEGRAM_BOT_TOKEN from the root .env file)
set TELEGRAM_BOT_TOKEN=

REM Secret Passphrase / PIN required for users to unlock the bot & Mini App
REM (or leave blank here to read ACCESS_PASSPHRASE from the root .env file)
set ACCESS_PASSPHRASE=

REM ---- AI & Voice APIs (OpenRouter & Optional Groq Whisper) ----
REM Leave blank here to read from the root .env file
set OPENROUTER_API_KEY=
set OPENROUTER_MODEL=openai/gpt-4o-mini
set OPENROUTER_AUDIO_MODEL=google/gemini-2.0-flash-001
set GROQ_API_KEY=
set GROQ_WHISPER_MODEL=whisper-large-v3-turbo

REM ---- Default User Ritual Preferences ----
set DEFAULT_TIMEZONE=Asia/Kuala_Lumpur
set DEFAULT_MORNING_BRIEF=08:00
set DEFAULT_EVENING_PULSE=21:00

REM ---- Telegram Mini App Studio (FastAPI) ----
REM Uses host port 8040 to avoid pemuda_surau (8080) and tg_expense_bot (8090)
REM Leave MINI_APP_URL blank to use the built-in Cloudflare HTTPS Quick Tunnel automatically
set WEBAPP_PORT=8040
set MINI_APP_URL=