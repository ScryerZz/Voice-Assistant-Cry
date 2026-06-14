@echo off
setlocal
cd /d "%~dp0"

echo [Cry] Creating virtual environment...
py -3.11 -m venv .venv
if errorlevel 1 (
  echo [Cry] Python 3.11 was not found. Install Python 3.11 and run this file again.
  pause
  exit /b 1
)

echo [Cry] Installing dependencies...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo [Cry] Dependency installation failed.
  pause
  exit /b 1
)

echo [Cry] Installation finished.
echo Run settings with run_settings.bat, then start the assistant with run_assistant.bat.
pause
