@echo off
cd /d "%~dp0backend"
if not exist ".venv\Scripts\python.exe" (
  echo Run setup-backend.bat first.
  pause
  exit /b 1
)
if not exist ".env" copy ".env.example" ".env" >nul
echo Backend: http://127.0.0.1:8000/api/health
if "%FRAUD_BIND%"=="" set FRAUD_BIND=127.0.0.1
if "%FRAUD_PORT%"=="" set FRAUD_PORT=8000
".venv\Scripts\python.exe" -m uvicorn app.main:app --host %FRAUD_BIND% --port %FRAUD_PORT%
pause

