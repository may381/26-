@echo off
cd /d "%~dp0backend"
if not exist ".venv\Scripts\python.exe" py -3.14 -m venv .venv
if not exist ".venv\Scripts\python.exe" (
  echo Python 3.14 is required for the tested environment.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  pause
  exit /b 1
)
if not exist ".env" copy ".env.example" ".env" >nul
echo Setup complete. Edit backend/.env, then run start-backend.bat.
pause

