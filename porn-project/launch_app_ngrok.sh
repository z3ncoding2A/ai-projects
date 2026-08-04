#!/usr/bin/bash
# Ngrok version: Build frontend, start Python backend server,
# create public tunnel with ngrok, and launch Chrome

PROJECT_DIR="/home/z3ncoding123/ai-projects/porn-project"
FRONTEND_DIR="$PROJECT_DIR/frontend"
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"

echo "Building frontend production build..."
cd "$FRONTEND_DIR" && npm run build

echo "Starting Python server on localhost:8888..."
pkill -f '[s]erve.py' || true
if [ -x "$VENV_PYTHON" ]; then
    cd "$PROJECT_DIR" && "$VENV_PYTHON" serve.py --no-browser > serve.log 2>&1 &
else
    cd "$PROJECT_DIR" && python3 serve.py --no-browser > serve.log 2>&1 &
fi

sleep 2

# Start ngrok tunnel and capture the URL
echo "Starting ngrok tunnel..."
ngrok http 8888 --log=stdout > /tmp/ngrok.log 2>&1 &
NGROK_PID=$!
sleep 3

# Extract the public URL from ngrok
NGROK_URL=$(grep -oP 'https://[a-z0-9.-]+\.ngrok\.io' /tmp/ngrok.log | head -1)

if [ -z "$NGROK_URL" ]; then
    echo "Failed to get ngrok URL. Check /tmp/ngrok.log"
    kill $NGROK_PID 2>/dev/null
    exit 1
fi

echo ""
echo "✓ Server is running on localhost:8888"
echo "✓ Ngrok tunnel created"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Access from iPhone: $NGROK_URL"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Remove stale profile locks if any exist
rm -f "$PROJECT_DIR/.chrome_profile/SingletonLock" \
      "$PROJECT_DIR/.chrome_profile/SingletonSocket" \
      "$PROJECT_DIR/.chrome_profile/SingletonCookie" 2>/dev/null

# Launch Chrome to the ngrok URL
/usr/bin/google-chrome-stable --user-data-dir="$PROJECT_DIR/.chrome_profile" --app="$NGROK_URL" &

echo "Chrome opened to: $NGROK_URL"
