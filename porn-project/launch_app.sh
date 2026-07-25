#!/usr/bin/bash
# Script to ensure serve.py and frontend vite dev server are running, then launch Chrome app mode

PROJECT_DIR="/home/z3ncoding123/ai-projects/porn-project"
FRONTEND_DIR="$PROJECT_DIR/frontend"
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"

# 1. Start Python backend server if not running
if ! pgrep -f "serve.py" > /dev/null; then
    if [ -x "$VENV_PYTHON" ]; then
        cd "$PROJECT_DIR" && "$VENV_PYTHON" serve.py --no-browser > /dev/null 2>&1 &
    else
        cd "$PROJECT_DIR" && python3 serve.py --no-browser > /dev/null 2>&1 &
    fi
fi

# 2. Start Vite frontend dev server if not running
if ! pgrep -f "vite" > /dev/null; then
    cd "$FRONTEND_DIR" && npm run dev > /dev/null 2>&1 &
fi

# Wait briefly for servers to bind
sleep 0.8

# 3. Launch Chrome pointing to frontend dev server
/usr/bin/google-chrome-stable --app=http://localhost:5173
