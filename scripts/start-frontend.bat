@echo off
setlocal
cd /d "%~dp0\..\frontend"

set NPM_BIN=
where npm >nul 2>nul
if %errorlevel%==0 (
  for /f "delims=" %%i in ('where npm') do set NPM_BIN=%%i
) else (
  if exist "C:\Program Files\nodejs\npm.cmd" set NPM_BIN=C:\Program Files\nodejs\npm.cmd
  if "%NPM_BIN%"=="" if exist "C:\Program Files (x86)\nodejs\npm.cmd" set NPM_BIN=C:\Program Files (x86)\nodejs\npm.cmd
)

if "%NPM_BIN%"=="" (
  echo Node.js/npm is not installed or not in PATH (and fallback npm.cmd not found).
  pause
  exit /b 1
)

echo Installing/verifying frontend dependencies...
"%NPM_BIN%" install
if errorlevel 1 (
  echo Failed while installing frontend dependencies.
  pause
  exit /b 1
)

"%NPM_BIN%" run dev -- --host 127.0.0.1 --port 5173
