@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [Cry] Virtual environment was not found. Run install.bat first.
  pause
  exit /b 1
)

".venv\Scripts\python.exe" diagnose.py
pause
