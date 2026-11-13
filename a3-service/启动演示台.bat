@echo off
chcp 936 >nul
title A3 演示台（关掉这个窗口就停止服务）
cd /d "%~dp0"

echo ============================================
echo   A3 演示台
echo ============================================
echo.

rem 优先用装了依赖的系统 Python。工作台自带的 python 没有第三方包，
rem 直接敲 python 可能命中它，会报 No module named xxx。
if exist "D:/Python/python.exe" (
    set "PY=D:/Python/python.exe"
) else if exist "D:/Python/安装3.14.2/python.exe" (
    set "PY=D:/Python/安装3.14.2/python.exe"
) else if exist "D:/Anaconda/Anaconda3/python.exe" (
    set "PY=D:/Anaconda/Anaconda3/python.exe"
) else (
    set "PY=python"
)

echo 解释器：%PY%
echo.

rem 先把页面弹出来。这时服务还没起，页面会是黄色「离线」。
start "" "%~dp0演示台.html"

echo 页面已打开。等下面出现「监听 http://127.0.0.1:18003」，
echo 就说明服务起来了 —— 回浏览器按一下 F5，状态灯会变绿。
echo.
echo 停止服务：关掉这个窗口，或者按 Ctrl+C。
echo --------------------------------------------
echo.

"%PY%" v3_server.py --port 18003

echo.
echo 服务已停止。按任意键关闭。
pause >nul
