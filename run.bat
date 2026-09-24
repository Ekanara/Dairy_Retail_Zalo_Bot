@echo off
chcp 65001 >nul 2>&1
title Magic Sale AI - Zalo Chatbot
echo.
echo  ====================================
echo   Magic Sale AI - Starting all services
echo  ====================================
echo.

:: Find Git Bash
set "GITBASH="
if exist "C:\Program Files\Git\bin\bash.exe" set "GITBASH=C:\Program Files\Git\bin\bash.exe"
if exist "C:\Program Files (x86)\Git\bin\bash.exe" set "GITBASH=C:\Program Files (x86)\Git\bin\bash.exe"

if "%GITBASH%"=="" (
    echo [ERROR] Git Bash not found. Please install Git for Windows.
    pause
    exit /b 1
)

echo [1/2] Starting Docker Desktop...
start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe" 2>nul

echo       Waiting for Docker to be ready...
:wait_docker
docker info >nul 2>&1
if errorlevel 1 (
    timeout /t 3 /nobreak >nul
    goto wait_docker
)
echo       Docker is ready!
echo.

echo [2/2] Starting all services via chat-up.sh...
echo.
"%GITBASH%" -l -c "cd '%~dp0' && bash scripts/chat-up.sh"

echo.
pause
