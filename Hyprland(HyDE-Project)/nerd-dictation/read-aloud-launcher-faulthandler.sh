#!/bin/bash
LOG_FILE="/tmp/read_aloud_gui_debug.log"

> "$LOG_FILE"
echo "---" >> "$LOG_FILE"
echo "Launcher started at $(date)" >> "$LOG_FILE"

VENV_PYTHON="$HOME/.local/share/read-aloud-venv/bin/python3"
SCRIPT_PATH="$HOME/.local/bin/read-aloud-gui.py"

echo "VENV_PYTHON: $VENV_PYTHON" >> "$LOG_FILE"
echo "SCRIPT_PATH: $SCRIPT_PATH" >> "$LOG_FILE"

if pgrep -f "$SCRIPT_PATH"; then
    echo "Process found. Killing existing process." >> "$LOG_FILE"
    pkill -f "$SCRIPT_PATH" >> "$LOG_FILE" 2>&1
    echo "Killed." >> "$LOG_FILE"
else
    echo "Process not found. Launching with faulthandler..." >> "$LOG_FILE"
    
    # Launching with all output redirected to the log file and using -X faulthandler
    nohup "$VENV_PYTHON" -X faulthandler "$SCRIPT_PATH" >> "$LOG_FILE" 2>&1 &
    echo "Command launched in background." >> "$LOG_FILE"
fi
