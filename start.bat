@echo off
setlocal
title Docking Decision Intelligence Engine

echo ==============================================================
echo Smart Docking System Launcher
echo ==============================================================
echo.

REM Step 1: Create .venv if needed
if not exist ".venv\Scripts\activate.bat" (
    echo [1/8] Creating Python virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment. Ensure Python is installed.
        pause
        exit /b 1
    )
) else (
    echo [1/8] Virtual environment already exists.
)

REM Step 2: Activate .venv
echo [2/8] Activating virtual environment...
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ERROR] Failed to activate .venv
    pause
    exit /b 1
)

REM Step 3: Install Python packages
echo [3/8] Installing Python dependencies...
set PIP_EXTRA_INDEX_URL=
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install Python dependencies.
    pause
    exit /b 1
)

REM Step 4: Install frontend packages
echo [4/8] Installing frontend dependencies...
pushd frontend
call npm install --silent
if errorlevel 1 (
    echo [ERROR] npm install failed.
    popd
    pause
    exit /b 1
)
popd

REM Free old web app processes on common app ports
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000"') do taskkill /PID %%p /F >nul 2>&1
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5173"') do taskkill /PID %%p /F >nul 2>&1
timeout /t 1 /nobreak > nul

REM Step 5: Start MongoDB (if needed)
echo [5/8] Checking MongoDB on localhost:27017...
netstat -ano | findstr ":27017" >nul
if errorlevel 1 (
    echo      MongoDB is not running. Attempting startup...
    net start MongoDB >nul 2>&1
    net start MongoDBServer >nul 2>&1
    net start "MongoDB Database Server" >nul 2>&1

    netstat -ano | findstr ":27017" >nul
    if errorlevel 1 (
        where mongod >nul 2>&1
        if errorlevel 1 (
            echo [WARNING] MongoDB service/mongod not found. Database features may fail.
        ) else (
            if not exist "mongodb_data" mkdir mongodb_data
            start "MongoDB" /B cmd /c "mongod --dbpath \"%CD%\mongodb_data\" --bind_ip 127.0.0.1"
        )
    )
)

set /a MONGO_TRIES=0
:wait_mongo
set /a MONGO_TRIES+=1
netstat -ano | findstr ":27017" >nul
if not errorlevel 1 goto mongo_ready
if %MONGO_TRIES% gtr 20 goto mongo_timeout
timeout /t 1 /nobreak > nul
goto wait_mongo

:mongo_ready
echo      MongoDB is running.
goto after_mongo

:mongo_timeout
echo [WARNING] MongoDB did not start on port 27017.

:after_mongo

REM Step 6: Start Ollama (if needed)
echo [6/8] Checking Ollama on localhost:11434...
netstat -ano | findstr ":11434" >nul
if errorlevel 1 (
    echo      Ollama is not running. Attempting startup...
    where ollama >nul 2>&1
    if errorlevel 1 (
        echo [WARNING] Ollama is not installed or not in PATH. Chat will use fallback mode.
    ) else (
        start "Ollama" /B cmd /c "ollama serve"
    )
)

set /a OLLAMA_TRIES=0
:wait_ollama
set /a OLLAMA_TRIES+=1
netstat -ano | findstr ":11434" >nul
if not errorlevel 1 goto ollama_ready
if %OLLAMA_TRIES% gtr 15 goto ollama_timeout
timeout /t 1 /nobreak > nul
goto wait_ollama

:ollama_ready
echo      Ollama is running.
goto after_ollama

:ollama_timeout
echo [WARNING] Ollama did not start on port 11434.

:after_ollama

REM Step 7: Start backend and frontend
echo [7/8] Starting backend Intelligence Engine...
start "Backend" /B cmd /c "call .venv\Scripts\activate.bat && set PIP_EXTRA_INDEX_URL= && python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000"

echo      Starting frontend web interface...
start "Frontend" /B cmd /c "cd frontend && npm run dev"

REM Step 8: Wait for frontend then open browser
echo [8/8] Waiting for servers to be ready...
set /a TRIES=0
:wait_frontend
set /a TRIES+=1
if %TRIES% gtr 30 goto open_browser
timeout /t 2 /nobreak > nul
curl -s -o nul http://localhost:5173/ 2>nul
if errorlevel 1 goto wait_frontend

:open_browser
echo.
echo Launching the User Interface in your default browser...
start http://localhost:5173

echo.
echo --------------------------------------------------------------
echo [SUCCESS] The application is now running.
echo - MongoDB:      mongodb://localhost:27017
echo - Ollama API:   http://localhost:11434
echo - Backend API:  http://localhost:8000
echo - Chat API:     http://localhost:8000/api/llm/chat
echo - UI Address:   http://localhost:5173
echo --------------------------------------------------------------

:loop
timeout /t 3600 /nobreak > nul
goto loop
