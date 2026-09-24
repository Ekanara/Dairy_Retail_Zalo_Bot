@echo off
chcp 65001 >nul 2>&1
title MCP Service (port 8004)
echo.
echo  ============================
echo   MCP Service - Port 8004
echo  ============================
echo.

cd /d "%~dp0"

:: Load .env
for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
    set "%%a=%%b"
)

:: Activate venv and run
cd mcp-service
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
) else (
    echo [ERROR] No .venv found in mcp-service. Run run.bat first to set up.
    pause
    exit /b 1
)

set PYTHONUTF8=1
set DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5434/magic_sale
set PROMPT_SERVICE_URL=http://127.0.0.1:8001
set ORDER_SERVICE_URL=http://127.0.0.1:8003
set MCP_TRANSPORT=http
set ZALO_SERVICE_URL=http://127.0.0.1:8080

echo Starting MCP service on http://127.0.0.1:8004 ...
echo.
python main.py
pause
