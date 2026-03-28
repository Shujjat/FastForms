@echo off
setlocal
cd /d "%~dp0\..\backend"

rem Prefer real Python 3.12 installs; PATH may point to a removed Windows Store / pythoncore install.
set "PYTHON_BIN="
if exist "%LocalAppData%\Programs\Python\Python312\python.exe" set "PYTHON_BIN=%LocalAppData%\Programs\Python\Python312\python.exe"
if not defined PYTHON_BIN if exist "C:\Program Files\Python312\python.exe" set "PYTHON_BIN=C:\Program Files\Python312\python.exe"
if not defined PYTHON_BIN if exist "C:\Program Files (x86)\Python312\python.exe" set "PYTHON_BIN=C:\Program Files (x86)\Python312\python.exe"
if not defined PYTHON_BIN (
  py -3.12 -c "import sys" >nul 2>&1
  if %errorlevel%==0 (
    for /f "delims=" %%i in ('py -3.12 -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON_BIN=%%i"
  )
)
if not defined PYTHON_BIN (
  where python >nul 2>nul
  if %errorlevel%==0 (
    for /f "delims=" %%i in ('where python') do (
      set "PYTHON_BIN=%%i"
      goto :py_done
    )
  )
)
:py_done
if not defined PYTHON_BIN (
  echo Python 3.11+ not found. Install Python 3.12 from python.org and add to PATH.
  pause
  exit /b 1
)

if exist ".venv\Scripts\python.exe" (
  echo Checking virtual environment...
  "%PYTHON_BIN%" -m venv --upgrade .venv 2>nul
  set "VENV_DEAD="
  ".venv\Scripts\python.exe" -c "import sys" >nul 2>&1
  if errorlevel 1 (
    set "VENV_DEAD=1"
  ) else (
    ".venv\Scripts\python.exe" -m pip --version >nul 2>&1
    if errorlevel 1 set "VENV_DEAD=1"
  )
)
if defined VENV_DEAD (
  echo Removing broken .venv ^(Python was moved or project was copied from another machine^)...
  rmdir /s /q ".venv" 2>nul
  set "VENV_DEAD="
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

set "VENV_PYTHON=.venv\Scripts\python.exe"
echo Using Python for venv: "%PYTHON_BIN%"

echo Installing/verifying backend requirements inside venv...
"%VENV_PYTHON%" -m pip install --upgrade pip
if errorlevel 1 (
  echo Failed while upgrading pip. Try deleting the folder backend\.venv and run again.
  pause
  exit /b 1
)
"%VENV_PYTHON%" -m pip install -r requirements.txt
if errorlevel 1 (
  echo Failed while installing backend requirements.
  pause
  exit /b 1
)
"%VENV_PYTHON%" -m pip uninstall -y psycopg psycopg-binary 2>nul

"%VENV_PYTHON%" manage.py migrate
if errorlevel 1 (
  echo Migration failed. Check PostgreSQL service and backend\.env values.
  pause
  exit /b 1
)

echo Backend ready at http://127.0.0.1:8000
"%VENV_PYTHON%" manage.py runserver 127.0.0.1:8000
