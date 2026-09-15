#!/bin/bash
# Wrapper script to run the TTS python script with the correct virtual environment
echo "[BASH] hypr-tts.sh started" >> /tmp/hypr-tts.log
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
VENV_PYTHON="$SCRIPT_DIR/venv/bin/python3"

# Run the python script
"$VENV_PYTHON" "$SCRIPT_DIR/tts.py"
