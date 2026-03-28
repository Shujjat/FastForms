@echo off
setlocal
cd /d "%~dp0\..\backend"

set PYTHON_BIN=
where python >nul 2>nul
if %errorlevel%==0 (
  for /f "delims=" %%i in ('where python') do set PYTHON_BIN=%%i
) else (
  if exist "C:\Program Files\Python312\python.exe" set PYTHON_BIN=C:\Program Files\Python312\python.exe
  if "%PYTHON_BIN%"=="" if exist "C:\Program Files (x86)\Python312\python.exe" set PYTHON_BIN=C:\Program Files (x86)\Python312\python.exe
)

if "%PYTHON_BIN%"=="" (
  echo Python is not installed or not in PATH (and fallback python312 not found).
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating backend virtual environment (.venv)...
  "%PYTHON_BIN%" -m venv .venv
  if errorlevel 1 (
    echo Failed to create Python virtual environment.
    pause
    exit /b 1
  )
)

set VENV_PYTHON=.venv\Scripts\python.exe

echo Installing/verifying backend requirements inside venv...
"%VENV_PYTHON%" -m pip install --upgrade pip
if errorlevel 1 (
  echo Failed while upgrading pip.
  pause
  exit /b 1
)
"%VENV_PYTHON%" -m pip install -r requirements.txt
if errorlevel 1 (
  echo Failed while installing backend requirements.
  pause
  exit /b 1
)

"%VENV_PYTHON%" manage.py migrate
if errorlevel 1 (
  echo Migration failed. Check PostgreSQL service and backend\.env values.
  pause
  exit /b 1
)

echo Backend ready at http://127.0.0.1:8000
"%VENV_PYTHON%" manage.py runserver 127.0.0.1:8000
