@echo off
cd /d "%~dp0backend"
if not exist ".venv\Scripts\python.exe" (
  echo Run setup-backend.bat first.
  pause
  exit /b 1
)
if not exist ".env" copy ".env.example" ".env" >nul
echo Backend: http://127.0.0.1:8000/api/health
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause

