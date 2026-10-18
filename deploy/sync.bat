@echo off
setlocal enabledelayedexpansion

REM ===================================================================
REM  sync.bat - Push Telegram Cadence Bot to DigitalOcean droplet
REM  Deploys into %REMOTE_DIR% (/opt/tg_cadence_bot) as an isolated
REM  Docker Compose project without touching existing containers.
REM
REM  Usage:
REM    sync.bat              push code + restart bot container
REM    sync.bat --restart    force docker rebuild
REM    sync.bat --from-deploy called by deploy.bat (first push)
REM ===================================================================

cd /d "%~dp0"
set DEPLOY_DIR=%CD%

if not exist "config.bat" (
  echo [sync] config.bat not found. Copy config.example.bat to config.bat first.
  exit /b 1
)
call config.bat

REM Fallback: if values are not set in config.bat, try reading from ..\.env
if exist "%DEPLOY_DIR%\..\.env" (
    for /f "usebackq eol=# tokens=1,* delims==" %%a in ("%DEPLOY_DIR%\..\.env") do (
        if "!TELEGRAM_BOT_TOKEN!"=="" if /i "%%a"=="TELEGRAM_BOT_TOKEN" set "TELEGRAM_BOT_TOKEN=%%b"
        if "!TELEGRAM_BOT_TOKEN!"=="" if /i "%%a"=="BOT_TOKEN" set "TELEGRAM_BOT_TOKEN=%%b"
        if "!ACCESS_PASSPHRASE!"=="" if /i "%%a"=="ACCESS_PASSPHRASE" set "ACCESS_PASSPHRASE=%%b"
        if "!ACCESS_PASSPHRASE!"=="" if /i "%%a"=="BOT_PASSPHRASE" set "ACCESS_PASSPHRASE=%%b"
        if "!OPENROUTER_API_KEY!"=="" if /i "%%a"=="OPENROUTER_API_KEY" set "OPENROUTER_API_KEY=%%b"
        if "!OPENROUTER_API_KEY!"=="" if /i "%%a"=="LLM_API_KEY" set "OPENROUTER_API_KEY=%%b"
        if "!OPENROUTER_MODEL!"=="" if /i "%%a"=="OPENROUTER_MODEL" set "OPENROUTER_MODEL=%%b"
        if "!OPENROUTER_MODEL!"=="" if /i "%%a"=="MODEL_SMART" set "OPENROUTER_MODEL=%%b"
        if "!OPENROUTER_AUDIO_MODEL!"=="" if /i "%%a"=="OPENROUTER_AUDIO_MODEL" set "OPENROUTER_AUDIO_MODEL=%%b"
        if "!OPENROUTER_AUDIO_MODEL!"=="" if /i "%%a"=="MODEL_FAST" set "OPENROUTER_AUDIO_MODEL=%%b"
        if "!GROQ_API_KEY!"=="" if /i "%%a"=="GROQ_API_KEY" set "GROQ_API_KEY=%%b"
        if "!GROQ_WHISPER_MODEL!"=="" if /i "%%a"=="GROQ_WHISPER_MODEL" set "GROQ_WHISPER_MODEL=%%b"
        if "!DEFAULT_TIMEZONE!"=="" if /i "%%a"=="DEFAULT_TIMEZONE" set "DEFAULT_TIMEZONE=%%b"
        if "!DEFAULT_MORNING_BRIEF!"=="" if /i "%%a"=="DEFAULT_MORNING_BRIEF" set "DEFAULT_MORNING_BRIEF=%%b"
        if "!DEFAULT_EVENING_PULSE!"=="" if /i "%%a"=="DEFAULT_EVENING_PULSE" set "DEFAULT_EVENING_PULSE=%%b"
        if "!MINI_APP_URL!"=="" if /i "%%a"=="MINI_APP_URL" (
            if /i not "%%b"=="http://localhost:8000" set "MINI_APP_URL=%%b"
        )
    )
)

if "%TELEGRAM_BOT_TOKEN%"=="" (
    echo [ERROR] TELEGRAM_BOT_TOKEN is not set in deploy\config.bat or .env.
    echo         Paste your @BotFather token into deploy\config.bat ^(set TELEGRAM_BOT_TOKEN=...^) or root .env and re-run.
    exit /b 1
)
if "%TELEGRAM_BOT_TOKEN%"=="1234567890:AAH_your_telegram_bot_token_here" (
    echo [ERROR] TELEGRAM_BOT_TOKEN is still set to the example placeholder.
    echo         Paste your real @BotFather token into deploy\config.bat or root .env and re-run.
    exit /b 1
)

set BUILD=0
if "%1"=="--restart"     set BUILD=1
if "%1"=="--from-deploy" set BUILD=1

echo.
echo === SYNC - Telegram Cadence Bot (%DROPLET_NAME%) ===
echo.

REM -- Resolve public IP ----------------------------------------------
set PUBLIC_IP=
if exist "%TEMP%\%PROJECT_NAME%-do-ip.txt" set /p PUBLIC_IP=<"%TEMP%\%PROJECT_NAME%-do-ip.txt"
if "%PUBLIC_IP%"=="" (
    for /f %%i in ('doctl compute droplet get %DROPLET_NAME% --format PublicIPv4 --no-header 2^>nul') do set PUBLIC_IP=%%i
)
if "%PUBLIC_IP%"=="" (
    echo [ERROR] Could not resolve IP for droplet %DROPLET_NAME%.
    echo         Ensure doctl is authenticated: doctl auth init
    exit /b 1
)
echo [INFO] Target Droplet: %DROPLET_NAME% (%PUBLIC_IP%)
echo [INFO] Remote Path:    %REMOTE_DIR% (isolated from other apps)

if not exist "%KEY_FILE%" (
    echo [ERROR] SSH key not found: %KEY_FILE%
    exit /b 1
)

set "SSH_OPTS=-o StrictHostKeyChecking=accept-new -o ConnectTimeout=15 -o ServerAliveInterval=5 -o ServerAliveCountMax=3 -i "%KEY_FILE%""
set SSH_RETRIES=5

REM -- Package code (exclude .venv, .git, node_modules, data, deploy, .env) --
echo [1/5] Packaging project...
cd /d "%~dp0.."
if exist "%TEMP%\%PROJECT_NAME%.tar" del "%TEMP%\%PROJECT_NAME%.tar"
tar -cf "%TEMP%\%PROJECT_NAME%.tar" ^
    --exclude=".venv" ^
    --exclude="venv" ^
    --exclude="__pycache__" ^
    --exclude=".pytest_cache" ^
    --exclude=".git" ^
    --exclude=".env" ^
    --exclude=".env.local" ^
    --exclude="deploy" ^
    --exclude="tests" ^
    --exclude="data" ^
    --exclude="backups" ^
    --exclude="node_modules" ^
    --exclude="frontend/node_modules" ^
    --exclude="frontend/dist" ^
    --exclude="frontend/.vite" ^
    --exclude="*.db" ^
    --exclude="*.db-wal" ^
    --exclude="*.db-shm" ^
    --exclude="*.pyc" ^
    --exclude="*.log" ^
    *
if %ERRORLEVEL% neq 0 (
    echo [ERROR] tar packaging failed.
    exit /b 1
)
echo [OK] Packaged.

REM -- Copy to droplet ------------------------------------------------
echo [2/5] Ensuring isolated remote directory exists (%REMOTE_DIR%)...
call :ssh_run "mkdir -p %REMOTE_DIR%/data"
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Could not create remote directory %REMOTE_DIR%.
    exit /b 1
)
echo [OK] Remote directory ready.

echo [3/5] Uploading archive to droplet...
call :ssh_pipe "%TEMP%\%PROJECT_NAME%.tar" "cat > %REMOTE_DIR%/app.tar"
set SCP_RC=%ERRORLEVEL%
del "%TEMP%\%PROJECT_NAME%.tar" 2>nul
if not %SCP_RC% equ 0 (
    echo [ERROR] Upload failed.
    exit /b 1
)
echo [OK] Uploaded.

REM -- Extract + configure .env ---------------------------------------
echo [4/5] Extracting and configuring %REMOTE_DIR%/.env...
call :ssh_run "cd %REMOTE_DIR% && tar -xf app.tar && rm -f app.tar"
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Extraction failed.
    exit /b 1
)

set "ENV_TMP=%TEMP%\%PROJECT_NAME%-configure-env.sh"
powershell -NoProfile -Command "(Get-Content -Raw '%DEPLOY_DIR%\configure-env.sh') -replace [char]13, '' | Set-Content -NoNewline '%ENV_TMP%' -Encoding ascii"
if not exist "%ENV_TMP%" (
    echo [ERROR] Could not prepare configure-env.sh.
    exit /b 1
)

if "%WEBAPP_PORT%"=="" set WEBAPP_PORT=8040
if "%OPENROUTER_MODEL%"=="" set OPENROUTER_MODEL=openai/gpt-4o-mini
if "%OPENROUTER_AUDIO_MODEL%"=="" set OPENROUTER_AUDIO_MODEL=google/gemini-2.0-flash-001
if "%GROQ_WHISPER_MODEL%"=="" set GROQ_WHISPER_MODEL=whisper-large-v3-turbo
if "%DEFAULT_TIMEZONE%"=="" set DEFAULT_TIMEZONE=Asia/Kuala_Lumpur
if "%DEFAULT_MORNING_BRIEF%"=="" set DEFAULT_MORNING_BRIEF=08:00
if "%DEFAULT_EVENING_PULSE%"=="" set DEFAULT_EVENING_PULSE=21:00

call :ssh_pipe "%ENV_TMP%" "bash -s -- '%REMOTE_DIR%' '%TELEGRAM_BOT_TOKEN%' '%ACCESS_PASSPHRASE%' '%OPENROUTER_API_KEY%' '%OPENROUTER_MODEL%' '%OPENROUTER_AUDIO_MODEL%' '%GROQ_API_KEY%' '%GROQ_WHISPER_MODEL%' '%DEFAULT_TIMEZONE%' '%DEFAULT_MORNING_BRIEF%' '%DEFAULT_EVENING_PULSE%' '%WEBAPP_PORT%' '%MINI_APP_URL%'"
set ENV_RC=%ERRORLEVEL%
del "%ENV_TMP%" 2>nul
if not %ENV_RC% equ 0 (
    echo [ERROR] Failed to configure remote .env.
    exit /b 1
)
echo [OK] Environment configured.

REM -- Start ONLY tg_cadence_bot container ----------------------------
echo [5/5] Starting tg_cadence_bot container...
set REMOTE_CMD=cd %REMOTE_DIR% ^&^& docker compose -p tg_cadence_bot up -d
if %BUILD% equ 1 set REMOTE_CMD=!REMOTE_CMD! --build

call :ssh_run "!REMOTE_CMD!"
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Remote docker compose up failed. Check the droplet:
    echo         ssh -i %KEY_FILE% root@%PUBLIC_IP%
    exit /b 1
)

echo.
echo [OK] Sync complete!
if %BUILD% equ 1 echo [OK] Cadence image built and started.

echo.
echo [INFO] Waiting 4s for Cadence & Quick Tunnel initialization...
ping -n 5 127.0.0.1 >nul

echo.
echo [INFO] Cadence Bot stack status (%REMOTE_DIR%):
call :ssh_run "cd %REMOTE_DIR% && docker compose -p tg_cadence_bot ps"

echo.
echo [INFO] All running containers on droplet %DROPLET_NAME% (verifying existing apps are untouched):
call :ssh_run "docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'"

echo.
echo [INFO] Recent bot logs:
call :ssh_run "cd %REMOTE_DIR% && docker compose -p tg_cadence_bot logs --tail=25 cadence"

goto :sync_end

:ssh_run
set /a SSH_TRY=0
:ssh_run_loop
set /a SSH_TRY+=1
ssh %SSH_OPTS% root@%PUBLIC_IP% %* <nul
if %ERRORLEVEL% equ 0 exit /b 0
if %SSH_TRY% geq %SSH_RETRIES% exit /b 1
echo [WARN] SSH attempt %SSH_TRY%/%SSH_RETRIES% failed - retrying...
ping -n 5 127.0.0.1 >nul
goto :ssh_run_loop

:ssh_pipe
set /a SSH_TRY=0
:ssh_pipe_loop
set /a SSH_TRY+=1
type "%~1" | ssh %SSH_OPTS% root@%PUBLIC_IP% %2
if %ERRORLEVEL% equ 0 exit /b 0
if %SSH_TRY% geq %SSH_RETRIES% exit /b 1
echo [WARN] SSH attempt %SSH_TRY%/%SSH_RETRIES% failed - retrying...
ping -n 5 127.0.0.1 >nul
goto :ssh_pipe_loop

:sync_end
endlocal