@echo off
chcp 65001 >nul 2>&1
title Magic Sale AI - Stopping
echo.
echo  ====================================
echo   Magic Sale AI - Stopping all services
echo  ====================================
echo.

set "GITBASH="
if exist "C:\Program Files\Git\bin\bash.exe" set "GITBASH=C:\Program Files\Git\bin\bash.exe"
if exist "C:\Program Files (x86)\Git\bin\bash.exe" set "GITBASH=C:\Program Files (x86)\Git\bin\bash.exe"

if "%GITBASH%"=="" (
    echo [ERROR] Git Bash not found.
    pause
    exit /b 1
)

"%GITBASH%" -l -c "cd '%~dp0' && bash scripts/chat-down.sh"

echo.
echo All services stopped.
pause
