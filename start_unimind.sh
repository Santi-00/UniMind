#!/usr/bin/env bash
# UniMind launcher for Linux and macOS
cd "$(dirname "$0")" || exit 1
echo "=== UNIMIND ==="

command -v python3 >/dev/null || { echo "[ERROR] Python 3 not found (3.10-3.12 recommended)."; exit 1; }
command -v node >/dev/null || { echo "[ERROR] Node.js not found (install the LTS version)."; exit 1; }
command -v ollama >/dev/null || echo "[WARNING] Ollama not found: AI features will stay off. Get it at https://ollama.com"

[ -d backend/.venv ] || { echo "Creating the Python environment..."; python3 -m venv backend/.venv || exit 1; }
echo "Checking backend dependencies..."
backend/.venv/bin/python -m pip install -q -r backend/requirements.txt || { echo "[ERROR] Backend dependencies failed to install."; exit 1; }
echo "Checking frontend dependencies..."
(cd frontend && npm install --no-audit --no-fund) || { echo "[ERROR] npm install failed."; exit 1; }

if ! curl -s http://localhost:11434/api/tags >/dev/null 2>&1 && command -v ollama >/dev/null; then
  (ollama serve >/dev/null 2>&1 &)
fi

trap 'kill 0' EXIT INT TERM
(cd backend && .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000) &
(cd frontend && npm run dev -- --port 3000) &
sleep 6
URL="http://localhost:3000"
if command -v xdg-open >/dev/null; then xdg-open "$URL" >/dev/null 2>&1; elif command -v open >/dev/null; then open "$URL"; fi
echo "UniMind is running at $URL (press Ctrl+C to stop)"
wait
