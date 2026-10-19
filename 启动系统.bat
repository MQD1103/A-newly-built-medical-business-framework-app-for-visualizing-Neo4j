@echo off
chcp 65001 >nul
title 小医 - 启动并打开前端
cd /d "%~dp0"

echo.
echo ========================================
echo   小医医疗商业框架 - 启动并打开前端
echo ========================================
echo.

rem 前端已在运行则立即打开浏览器；否则先启动前后端，就绪后自动打开
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0open-frontend.ps1"
set "ERR=%ERRORLEVEL%"

if not "%ERR%"=="0" (
  echo.
  echo [失败] 启动未成功，请查看上方提示或弹出的黑色窗口报错。
  echo.
  pause
  exit /b %ERR%
)

rem 启动成功后不再停留，直接进入前端页面
exit /b 0
