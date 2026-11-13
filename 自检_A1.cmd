@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0a1-orchestrator"
echo ==========================================
echo  A1 端到端自检（需要 8095 / 8091 / 8000 已启动）
echo  检查：追问不派发、旅游真回内容、反诈真出结果、失败被挡
echo ==========================================
python -u -X utf8 e2e_smoke.py
set CODE=%ERRORLEVEL%
echo.
if %CODE%==0 (echo 自检通过) else (echo 自检未通过，请查看上面的 FAIL)
echo 报告在 A1new\qa\ 目录下。
pause
exit /b %CODE%
