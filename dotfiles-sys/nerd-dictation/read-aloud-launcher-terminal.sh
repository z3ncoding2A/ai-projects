#!/bin/bash
VENV_PYTHON="$HOME/.local/share/read-aloud-venv/bin/python3"
SCRIPT_PATH="$HOME/.local/bin/read-aloud-gui.py"

# Launch the script in a new kitty terminal window to see all output
kitty "$VENV_PYTHON" -X faulthandler "$SCRIPT_PATH"
