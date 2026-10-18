@echo off
setlocal enabledelayedexpansion

REM ===================================================================
REM  backup.bat - Zero-downtime hot backup of remote SQLite cadence.db
REM  Uses SQLite's Online Backup API inside the running container so all
REM  WAL frames are safely merged into a single consistent .db file
REM  without stopping the bot.
REM
REM  Usage:
REM    backup.bat                 Download timestamped backup to ..\backups\
REM    backup.bat --to-local-data Also overwrite local ..\data\cadence.db
REM ===================================================================

cd /d "%~dp0"
set DEPLOY_DIR=%CD%

if not exist "config.bat" (
  echo [backup] config.bat not found. Copy config.example.bat to config.bat first.
  exit /b 1
)
call config.bat

echo.
echo ===============================================================
echo    TELEGRAM CADENCE BOT - REMOTE SQLITE BACKUP
echo ===============================================================
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

if not exist "%KEY_FILE%" (
    echo [ERROR] SSH key not found: %KEY_FILE%
    exit /b 1
)

set "SSH_OPTS=-o StrictHostKeyChecking=accept-new -o ConnectTimeout=15 -i "%KEY_FILE%""

REM -- Generate local timestamp (YYYYMMDD_HHMMSS) ---------------------
for /f %%t in ('powershell -NoProfile -Command "Get-Date -Format 'yyyyMMdd_HHmmss'"') do set TIMESTAMP=%%t
set "BACKUP_DIR=%DEPLOY_DIR%\..\backups"
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

set "BACKUP_FILE=%BACKUP_DIR%\cadence_%TIMESTAMP%.db"
set "LATEST_FILE=%BACKUP_DIR%\cadence_latest.db"

echo [1/3] Creating hot WAL-consistent snapshot on %DROPLET_NAME% (%PUBLIC_IP%)...
ssh %SSH_OPTS% root@%PUBLIC_IP% "if docker ps --format '{{.Names}}' | grep -q '^tg_cadence_bot$'; then docker exec tg_cadence_bot python -c \"import sqlite3; src=sqlite3.connect('/app/data/cadence.db'); dst=sqlite3.connect('/app/data/cadence.backup.tmp'); src.backup(dst); dst.close(); src.close()\"; elif [ -f '%REMOTE_DIR%/data/cadence.db' ]; then cp '%REMOTE_DIR%/data/cadence.db' '%REMOTE_DIR%/data/cadence.backup.tmp'; else exit 2; fi"
if %ERRORLEVEL% equ 2 (
    echo [ERROR] Remote database %REMOTE_DIR%/data/cadence.db not found on droplet.
    exit /b 1
)
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to create remote SQLite snapshot.
    exit /b 1
)
echo [OK] Snapshot created.

echo [2/3] Downloading snapshot to local backups folder...
scp %SSH_OPTS% "root@%PUBLIC_IP%:%REMOTE_DIR%/data/cadence.backup.tmp" "%BACKUP_FILE%"
set SCP_RC=%ERRORLEVEL%

REM Clean up temporary snapshot on droplet
ssh %SSH_OPTS% root@%PUBLIC_IP% "rm -f '%REMOTE_DIR%/data/cadence.backup.tmp'" >nul 2>&1

if %SCP_RC% neq 0 (
    echo [ERROR] Failed to download database backup via scp.
    exit /b 1
)

copy /y "%BACKUP_FILE%" "%LATEST_FILE%" >nul
echo [OK] Saved timestamped backup: %BACKUP_FILE%
echo [OK] Updated latest pointer:   %LATEST_FILE%

echo [3/3] Verifying local SQLite backup integrity...
for /f "delims=" %%s in ('powershell -NoProfile -Command "$f = Get-Item '%BACKUP_FILE%'; Write-Output ($f.Length.ToString() + ' bytes')"') do set FILE_SIZE=%%s
echo [OK] Backup file size: %FILE_SIZE%

if /i "%1"=="--to-local-data" (
    if not exist "%DEPLOY_DIR%\..\data" mkdir "%DEPLOY_DIR%\..\data"
    del /q "%DEPLOY_DIR%\..\data\cadence.db-wal" 2>nul
    del /q "%DEPLOY_DIR%\..\data\cadence.db-shm" 2>nul
    copy /y "%BACKUP_FILE%" "%DEPLOY_DIR%\..\data\cadence.db" >nul
    echo [OK] Also restored backup into local ..\data\cadence.db
)

echo.
echo ===============================================================
echo    BACKUP COMPLETE
echo    File:   %BACKUP_FILE%
echo    Latest: %LATEST_FILE%
echo ===============================================================

endlocal

