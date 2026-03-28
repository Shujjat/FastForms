@echo off
rem Launcher for Task Scheduler — keeps a single path to the repo root.
rem Set "Start in" to J:\FastForms or leave blank; %~dp0 sets the folder.
setlocal
cd /d "%~dp0"
call "scripts\start-fastforms-scheduled.bat"
exit /b %errorlevel%
