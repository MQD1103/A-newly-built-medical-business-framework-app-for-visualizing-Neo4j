@echo off
chcp 65001 >nul
title 小医医疗商业框架 - 一键启动
cd /d "%~dp0"

echo.
echo ========================================
echo   小医医疗商业框架 - 一键启动
echo ========================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-system.ps1"
set "ERR=%ERRORLEVEL%"

echo.
if "%ERR%"=="0" (
  echo [完成] 系统已启动。关闭请双击「关闭系统.bat」
) else (
  echo [失败] 启动未成功，请查看上方提示或弹出的黑色窗口报错。
)
echo.
pause
exit /b %ERR%
