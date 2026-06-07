#!/bin/bash
set -e

echo "Setting up Hyper Commander..."
cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python -m venv venv
fi

echo "Installing dependencies..."
source venv/bin/activate
pip install -r requirements.txt

echo ""
echo "Setup complete!"
echo "To run Hyper Commander:"
echo "  cd ~/.gemini/projects/hyprwhspr/hyper_commander"
echo "  source venv/bin/activate"
echo "  python main.py"
