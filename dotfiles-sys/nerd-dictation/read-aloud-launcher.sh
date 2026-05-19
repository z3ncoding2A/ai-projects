#!/bin/bash
VENV_PYTHON="$HOME/.local/share/read-aloud-venv/bin/python3"
SCRIPT_PATH="$HOME/.local/bin/read-aloud-gui.py"

if pgrep -f "$SCRIPT_PATH"; then
    pkill -f "$SCRIPT_PATH"
else
    "$VENV_PYTHON" "$SCRIPT_PATH" &
fi
