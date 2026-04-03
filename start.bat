@echo off
title Docking Decision Intelligence Engine

echo ==============================================================
echo Smart Docking System Launcher
echo ==============================================================
echo.

echo [1/3] Starting backend Intelligence Engine...
start /B cmd /c "conda run -n snackk uvicorn backend.main:app --host 127.0.0.1 --port 8000"

echo [2/3] Starting frontend web interface...
start /B cmd /c "cd frontend && npm run dev"

echo [3/3] Warming up systems...
timeout /t 4 /nobreak > nul

echo.
echo Launching the User Interface in your default browser...
start http://localhost:5173

echo.
echo --------------------------------------------------------------
echo [SUCCESS] The application is now running.
echo - LLM Endpoint: http://localhost:8000/api/llm/generate
echo - UI Address: http://localhost:5173
echo 
echo NOTE: You can minimize this window. Do not close it until 
echo you are ready to terminate the application.
echo --------------------------------------------------------------

:: Keep the script alive so the shared console remains active.
:loop
timeout /t 3600 /nobreak > nul
goto :loop
