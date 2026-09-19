#!/usr/bin/bash
# Script to build frontend, start Python backend server (which serves the frontend build and APIs), and launch Chrome app mode

PROJECT_DIR="/home/z3ncoding123/ai-projects/porn-project"
FRONTEND_DIR="$PROJECT_DIR/frontend"
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"

BIND_HOST="127.0.0.1"
if [ "$1" == "--lan" ]; then
    BIND_HOST="0.0.0.0"
    echo "LAN mode enabled: Binding to 0.0.0.0"
fi

echo "Building frontend production build..."
cd "$FRONTEND_DIR" && npm run build

echo "Starting Python server on $BIND_HOST:8888..."
pkill -f '[s]erve.py' || true
if [ -x "$VENV_PYTHON" ]; then
    cd "$PROJECT_DIR" && BIND_HOST="$BIND_HOST" "$VENV_PYTHON" serve.py --no-browser > serve.log 2>&1 &
else
    cd "$PROJECT_DIR" && BIND_HOST="$BIND_HOST" python3 serve.py --no-browser > serve.log 2>&1 &
fi

sleep 1.0

# Remove stale profile locks if any exist
rm -f "$PROJECT_DIR/.chrome_profile/SingletonLock" \
      "$PROJECT_DIR/.chrome_profile/SingletonSocket" \
      "$PROJECT_DIR/.chrome_profile/SingletonCookie" 2>/dev/null

CHROME_URL="http://localhost:8888"
if [ "$BIND_HOST" = "0.0.0.0" ]; then
    LOCAL_IP=$(ip route get 1.1.1.1 2>/dev/null | grep -oP 'src \K[^ ]+' || echo "localhost")
    CHROME_URL="http://$LOCAL_IP:8888"
    echo "LAN server accessible at http://$LOCAL_IP:8888 from other devices"
else
    echo "Launching Chrome in app mode pointing to http://localhost:8888..."
fi

/usr/bin/google-chrome-stable --user-data-dir="$PROJECT_DIR/.chrome_profile" --app="$CHROME_URL" &
