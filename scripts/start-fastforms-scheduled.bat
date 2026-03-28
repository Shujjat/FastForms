@echo off
setlocal EnableDelayedExpansion
rem =============================================================================
rem FastForms — start backend + frontend for Task Scheduler / unattended runs
rem
rem Task Scheduler (example):
rem   Program/script:  J:\FastForms\Run-FastForms-Scheduled.bat
rem   Start in:          J:\FastForms
rem   Run whether user is logged on or not: optional (often use a dedicated
rem   service account with rights to J:\FastForms and logon as batch if needed)
rem
rem Trigger: "At startup" — add 1–2 minute delay so PostgreSQL (and Redis) are up.
rem
rem Requirements: Python, Node, PostgreSQL, backend\.env (see RUN_ON_NEW_SYSTEM.md)
rem This script appends to logs\scheduler.log
rem =============================================================================

pushd "%~dp0.."
set "FASTFORMS_ROOT=%CD%"
popd

if not exist "%FASTFORMS_ROOT%\scripts\start-backend.bat" (
  set "LOGDIR=%FASTFORMS_ROOT%\logs"
  if not exist "!LOGDIR!" mkdir "!LOGDIR!"
  echo [%date% %time%] ERROR: Missing scripts\start-backend.bat under "!FASTFORMS_ROOT!" >> "!LOGDIR!\scheduler.log" 2>&1
  exit /b 1
)

set "LOGDIR=%FASTFORMS_ROOT%\logs"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"

echo [%date% %time%] Scheduled start invoked. >> "%LOGDIR%\scheduler.log"

rem --- Skip if already running (avoids duplicate bind errors) ---
powershell -NoProfile -Command "try { $c=New-Object Net.Sockets.TcpClient('127.0.0.1',8000); $c.Close(); exit 0 } catch { exit 1 }"
if %errorlevel%==0 (
  echo [%date% %time%] Port 8000 in use — backend assumed running. >> "%LOGDIR%\scheduler.log"
  goto :frontend
)

echo [%date% %time%] Starting backend (minimized window)... >> "%LOGDIR%\scheduler.log"
start "FastForms Backend" /MIN cmd /k "cd /d \"%FASTFORMS_ROOT%\scripts\" && call start-backend.bat"

:frontend
powershell -NoProfile -Command "try { $c=New-Object Net.Sockets.TcpClient('127.0.0.1',5173); $c.Close(); exit 0 } catch { exit 1 }"
if %errorlevel%==0 (
  echo [%date% %time%] Port 5173 in use — frontend assumed running. >> "%LOGDIR%\scheduler.log"
  goto :done
)

echo [%date% %time%] Starting frontend (minimized window)... >> "%LOGDIR%\scheduler.log"
start "FastForms Frontend" /MIN cmd /k "cd /d \"%FASTFORMS_ROOT%\scripts\" && call start-frontend.bat"

:done
echo [%date% %time%] Done. >> "%LOGDIR%\scheduler.log"
exit /b 0
