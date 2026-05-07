#!/bin/bash
LOG_FILE="/tmp/read-aloud.log"

# Ensure the log file is cleared for each run
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
    
    # Launching with all output redirected to the log file
    nohup "$VENV_PYTHON" "$SCRIPT_PATH" >> "$LOG_FILE" 2>&1 &
    echo "Command launched in background." >> "$LOG_FILE"
fi
