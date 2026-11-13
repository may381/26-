@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
echo ==========================================
echo Yinling A1 - school qwen3.8-27b only
 echo No local-model or simulated-answer fallback
 echo ==========================================
echo 1. Tourism - school model (8091)
echo 2. Anti-fraud backend - school (8000)
echo 3. Anti-fraud frontend (5174)
echo 4. Open competition showcase
echo 5. Exit
 echo 6. A1 natural-language domain entry (school; not P2)
echo 7. A1 v3 integration service (8093, P2 entry)
choice /c 1234567 /n /m "Select one service (open menu again for another): "
if errorlevel 7 goto a1v3
if errorlevel 6 goto a1chat
if errorlevel 5 exit /b 0
if errorlevel 4 goto showcase
if errorlevel 3 goto frontend
if errorlevel 2 goto fraudschool
if errorlevel 1 goto travelschool
exit /b 0
:travelschool
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0a1-guide\start-release.ps1" -Mode school
goto done
:fraudschool
call "%~dp0外包A30\anti-fraud\start-school-backend.bat"
goto done
:frontend
cd /d "%~dp0外包A30\anti-fraud"
node node_modules\vite\bin\vite.js --host 127.0.0.1
goto done
:a1chat
set "A1_MODEL_URL=http://10.138.50.151:8000/v1/chat/completions"
set "A1_MODEL_NAME=qwen3.8-27b"
py -3 "%~dp0a1-orchestrator\domain_chat.py"
goto done
:a1v3
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0a1-orchestrator\启动A1联调服务.ps1"
goto done
:showcase
start "" http://127.0.0.1:8091/showcase.html
goto done
:done
echo Service exited. Read any error above; do not start duplicate processes.
pause
