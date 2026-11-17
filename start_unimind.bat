@echo off
chcp 65001 >nul
cd /d "%~dp0"
title UniMind launcher
echo === UNIMIND ===

echo %CD% | find /i "OneDrive" >nul && echo [WARNING] This folder is inside OneDrive. Sync can lock files and break npm install. Move UniMind to C:\UNIMIND.

where python >nul 2>nul || (echo [ERROR] Python not found. Install Python 3.10 to 3.12 from python.org and try again. & pause & exit /b 1)
where node >nul 2>nul || (echo [ERROR] Node.js not found. Install the LTS version from nodejs.org and try again. & pause & exit /b 1)
where ollama >nul 2>nul || echo [WARNING] Ollama not found. The app will start but AI features stay off. Get it at https://ollama.com

if not exist backend\.venv (
  echo Creating the Python environment...
  python -m venv backend\.venv || (echo [ERROR] Could not create the Python environment. & pause & exit /b 1)
)
echo Checking backend dependencies...
backend\.venv\Scripts\python -m pip install -q -r backend\requirements.txt || (echo [ERROR] Backend dependencies failed to install. & pause & exit /b 1)

echo Checking frontend dependencies...
pushd frontend
call npm install --no-audit --no-fund || (popd & echo [ERROR] npm install failed. & pause & exit /b 1)
popd

curl -s http://localhost:11434/api/tags >nul 2>nul || (where ollama >nul 2>nul && start "" /min ollama serve)

start "UniMind Backend" cmd /k "cd /d %~dp0backend && .venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
start "UniMind Frontend" cmd /k "cd /d %~dp0frontend && npm run dev -- --port 3000"

echo Opening UniMind in your browser...
timeout /t 6 >nul
start http://localhost:3000
