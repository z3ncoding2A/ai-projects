#!/bin/bash
LOG_FILE="/tmp/read-aloud.log"
echo "---" > "$LOG_FILE"
echo "Launcher started at $(date)" >> "$LOG_FILE"

VENV_PYTHON="$HOME/.local/share/read-aloud-venv/bin/python3"
SCRIPT_PATH="$HOME/.local/bin/read-aloud-gui.py"
echo "VENV_PYTHON: $VENV_PYTHON" >> "$LOG_FILE"
echo "SCRIPT_PATH: $SCRIPT_PATH" >> "$LOG_FILE"

if pgrep -f "$SCRIPT_PATH"; then
    echo "Process found. Killing existing process." >> "$LOG_FILE"
    pkill -f "$SCRIPT_PATH"
else
    echo "Process not found. Launching..." >> "$LOG_FILE"
    if [ -f "$VENV_PYTHON" ]; then
        echo "Venv python exists." >> "$LOG_FILE"
    else
        echo "Venv python DOES NOT EXIST." >> "$LOG_FILE"
    fi
    if [ -f "$SCRIPT_PATH" ]; then
        echo "Script path exists." >> "$LOG_FILE"
    else
        echo "Script path DOES NOT EXIST." >> "$LOG_FILE"
    fi
    
    "$VENV_PYTHON" "$SCRIPT_PATH" &>> "$LOG_FILE" &
    echo "Command launched in background." >> "$LOG_FILE"
fi
