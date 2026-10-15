@echo off
chcp 65001 >nul
title 小医医疗商业框架 - 一键关闭
cd /d "%~dp0"

echo.
echo ========================================
echo   小医医疗商业框架 - 一键关闭
echo ========================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop-system.ps1"
set "ERR=%ERRORLEVEL%"

echo.
if "%ERR%"=="0" (
  echo [完成] 前后端端口已释放。
) else (
  echo [注意] 关闭过程有异常，可再运行一次本脚本。
)
echo.
pause
exit /b %ERR%
