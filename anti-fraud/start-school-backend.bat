@echo off
cd /d "%~dp0backend"
set LLM_PROVIDER=school
set LLM_BASE_URL=http://10.138.50.151:8000/v1
set LLM_MODEL=qwen3.8-27b
set LLM_API_KEY=
if not exist ".venv-school\Scripts\python.exe" (
 echo Missing project environment .venv-school. Please run setup first.
 pause
 exit /b 1
)
".venv-school\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
