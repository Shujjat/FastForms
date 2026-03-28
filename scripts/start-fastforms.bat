@echo off
setlocal

cd /d "%~dp0\.."

set PYTHON_OK=0
where python >nul 2>nul
if %errorlevel%==0 set PYTHON_OK=1
if %PYTHON_OK%==0 (
  if exist "C:\Program Files\Python312\python.exe" set PYTHON_OK=1
  if exist "C:\Program Files (x86)\Python312\python.exe" set PYTHON_OK=1
)
if %PYTHON_OK%==0 (
  echo Python is not installed (and fallback Python312 not found).
  pause
  exit /b 1
)

set NPM_OK=0
where npm >nul 2>nul
if %errorlevel%==0 set NPM_OK=1
if %NPM_OK%==0 (
  if exist "C:\Program Files\nodejs\npm.cmd" set NPM_OK=1
  if exist "C:\Program Files (x86)\nodejs\npm.cmd" set NPM_OK=1
)
if %NPM_OK%==0 (
  echo Node.js/npm is not installed (and fallback nodejs not found).
  pause
  exit /b 1
)

start "FastForms Backend" cmd /k "%~dp0start-backend.bat"
start "FastForms Frontend" cmd /k "%~dp0start-frontend.bat"

echo Waiting for backend at http://127.0.0.1:8000 ...
powershell -NoProfile -Command ^
  "for($i=0;$i -lt 180;$i++){ try{$c=New-Object Net.Sockets.TcpClient('127.0.0.1',8000);$c.Close(); exit 0}catch{ Start-Sleep -Seconds 1 } } exit 1"

if not %ERRORLEVEL%==0 (
  echo Backend did not start in time. Check the backend terminal output for errors.
  exit /b 1
)

echo Waiting for frontend at http://127.0.0.1:5173 ...
powershell -NoProfile -Command ^
  "for($i=0;$i -lt 180;$i++){ try{$c=New-Object Net.Sockets.TcpClient('127.0.0.1',5173);$c.Close(); exit 0}catch{ Start-Sleep -Seconds 1 } } exit 1"

if %ERRORLEVEL%==0 (
  echo Frontend is ready. Opening browser...
  start "" "http://127.0.0.1:5173"
) else (
  echo Timed out waiting for frontend. Check the backend/frontend terminal output for errors.
)

exit /b 0
