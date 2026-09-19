#!/usr/bin/bash
# Tailscale version: Build frontend, start Python backend server listening on all interfaces,
# and launch Chrome pointing to the Tailscale IP for access over VPN

PROJECT_DIR="/home/z3ncoding123/ai-projects/porn-project"
FRONTEND_DIR="$PROJECT_DIR/frontend"
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"

# Tailscale IP for access from other devices via VPN
TAILSCALE_IP="100.96.196.4"
# Bind to all interfaces so Tailscale routing works instead of 0.0.0.0 to ensure proper routing
BIND_HOST="0.0.0.0"

echo "Building frontend production build..."
cd "$FRONTEND_DIR" && npm run build

echo "Starting Python server on $BIND_HOST:8888 (Tailscale IP)..."
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

echo "Launching Chrome in app mode pointing to Tailscale IP: http://$TAILSCALE_IP:8888"
echo "Access from iPhone: http://$TAILSCALE_IP:8888"

/usr/bin/google-chrome-stable --user-data-dir="$PROJECT_DIR/.chrome_profile" --app="http://$TAILSCALE_IP:8888" &
