@echo off
setlocal
rem FastForms — project root is this file's directory (%~dp0)

cd /d "%~dp0"
set "ROOT=%cd%"

rem ---------- Python: prefer a real Python 3.12 install, then PATH ----------
rem Avoid using a stale PATH entry that points to a removed "pythoncore" install.
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
      goto :python_from_path_done
    )
  )
)
:python_from_path_done
if not defined PYTHON_BIN (
  echo Python 3.11+ not found. Install Python 3.12 from python.org and check "Add to PATH", or add Python312 to PATH.
  pause
  exit /b 1
)

rem ---------- npm (frontend) — verify before start ----------
where npm >nul 2>nul
if errorlevel 1 (
  if not exist "C:\Program Files\nodejs\npm.cmd" if not exist "C:\Program Files (x86)\nodejs\npm.cmd" (
    echo Node.js/npm is not installed or not in PATH.
    pause
    exit /b 1
  )
)

rem ---------- Prepare backend: venv, deps, migrate ----------
cd /d "%ROOT%\backend"

rem If .venv was copied from another PC or the old Python was removed, pip will fail with "did not find executable..."
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
  echo Removing broken .venv ^(interpreter path changed or project was copied from another machine^)...
  rmdir /s /q ".venv" 2>nul
  set "VENV_DEAD="
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating Python virtual environment: "%ROOT%\backend\.venv"
  "%PYTHON_BIN%" -m venv .venv
  if errorlevel 1 (
    echo Failed to create .venv
    pause
    exit /b 1
  )
)

set "VENV_PY=.venv\Scripts\python.exe"
echo Using Python for venv: "%PYTHON_BIN%"
echo Installing/updating backend dependencies...
"%VENV_PY%" -m pip install --upgrade pip
if errorlevel 1 (
  echo pip upgrade failed. If this keeps happening, delete the folder backend\.venv and run this script again.
  pause
  exit /b 1
)
"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 (
  echo pip install failed.
  pause
  exit /b 1
)
rem Django loads psycopg v3 before psycopg2 if both exist; v3 can fail on Windows without libpq. Prefer v2 driver.
"%VENV_PY%" -m pip uninstall -y psycopg psycopg-binary 2>nul
echo Running migrations...
"%VENV_PY%" manage.py migrate
if errorlevel 1 (
  echo Migration failed. Check PostgreSQL and backend\.env
  pause
  exit /b 1
)
cd /d "%ROOT%"

rem ---------- Start servers (venv activated in backend window) ----------
rem Use START /D for working dir — avoids broken nested quotes with paths like "C:\Program Files\nodejs\npm.cmd"
echo Starting backend with virtual environment activated...
start "FastForms Backend" /D "%ROOT%\backend" cmd /k "call .venv\Scripts\activate.bat && python manage.py runserver 127.0.0.1:8000"

echo Starting frontend...
start "FastForms Frontend" /D "%ROOT%\frontend" cmd /k "npm install && npm run dev -- --host 127.0.0.1 --port 5173"

echo Waiting for backend at http://127.0.0.1:8000 ...
powershell -NoProfile -Command ^
  "for($i=0;$i -lt 180;$i++){ try{$c=New-Object Net.Sockets.TcpClient('127.0.0.1',8000);$c.Close(); exit 0}catch{ Start-Sleep -Seconds 1 } } exit 1"

if not %ERRORLEVEL%==0 (
  echo Backend did not start in time. Check the Backend window for errors.
  exit /b 1
)

echo Waiting for frontend at http://127.0.0.1:5173 ...
powershell -NoProfile -Command ^
  "for($i=0;$i -lt 180;$i++){ try{$c=New-Object Net.Sockets.TcpClient('127.0.0.1',5173);$c.Close(); exit 0}catch{ Start-Sleep -Seconds 1 } } exit 1"

if %ERRORLEVEL%==0 (
  echo Opening browser...
  start "" "http://127.0.0.1:5173"
) else (
  echo Timed out waiting for frontend. Check the Frontend window for errors.
)

exit /b 0
