@echo off
setlocal

cd /d "%~dp0"

if not exist "scripts\start-fastforms.bat" (
  echo Could not find scripts\start-fastforms.bat
  pause
  exit /b 1
)

call "scripts\start-fastforms.bat"
