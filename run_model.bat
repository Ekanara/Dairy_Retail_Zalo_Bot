@echo off
chcp 65001 >nul 2>&1
title Models Service (port 8000)
echo.
echo  ==============================
echo   Models Service - Port 8000
echo  ==============================
echo.

cd /d "%~dp0"

:: Load .env
for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
    set "%%a=%%b"
)

:: Activate venv and run
cd models-service
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
) else (
    echo [ERROR] No .venv found in models-service. Run run.bat first to set up.
    pause
    exit /b 1
)

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set PROMPT_SERVICE_URL=http://127.0.0.1:8001
set MCP_SERVICE_URL=http://127.0.0.1:8004
set CHAT_SERVICE_URL=http://127.0.0.1:8007

echo Starting Models service on http://127.0.0.1:8000 ...
echo Model: %MODEL_NAME%
echo.
python -m uvicorn main:app --host 127.0.0.1 --port 8000
pause
