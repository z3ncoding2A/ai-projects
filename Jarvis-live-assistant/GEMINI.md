# MARK XLVI (46) - Project Context

## Project Overview

MARK XLVI is a cross-platform personal AI assistant developed by FatihMakes. It acts as a real-time voice AI that can see, hear, understand, and control a computer across Windows, macOS, and Linux. The system is designed to provide autonomous task execution, real-time screen processing, voice/keyboard hybrid input, and a deep persistent memory. It is heavily integrated with the Google Gemini API for fast reasoning and reasoning.

The architecture is built in Python and structured into several key directories:
- `actions/`: Contains various modules for controlling the computer (e.g., `browser_control.py`, `computer_control.py`, `desktop.py`), managing files (`file_controller.py`), and performing specific tasks (e.g., `weather_report.py`, `web_search.py`).
- `core/`: Core services including Text-to-Speech (`tts.py`), Speech-to-Text (`stt.py`), LLM integration (`llm_client.py`), and prompts.
- `dashboard/`: A web-based dashboard and API powered by FastAPI/Uvicorn, serving static HTML for remote control and interactions.
- `memory/`: Modules for managing the AI's long-term memory and configuration across sessions.

## Building and Running

**Prerequisites:**
- Python 3.11 or 3.12
- A free Gemini API Key
- Microphone setup for voice interactions

**Installation:**
The project uses standard Python packaging and Playwright for browser automation. To install dependencies:
```bash
# Optional: It is recommended to use a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Linux/macOS
# .venv\Scripts\activate   # On Windows

# Install dependencies and Playwright browsers
python setup.py
# Or manually:
# pip install -r requirements.txt
# playwright install
```
*Note: Some OS-specific dependencies are not included in `requirements.txt` to keep it lightweight. If you encounter a `ModuleNotFoundError`, install it via `pip install <module_name>`.*

**Execution:**
Start the main assistant by running the entry point:
```bash
python main.py
```

## Development Conventions

- **Language & Frameworks:** Built in Python using standard libraries along with `sounddevice`, `playwright`, `fastapi`, and the Google Generative AI Python SDKs. 
- **Modularity:** Action capabilities are cleanly separated in the `actions/` folder, making it easy to extend the assistant with new functions.
- **Cross-Platform Compatibility:** The codebase is designed to run on Windows, macOS, and Linux. Ensure any new features or dependencies account for cross-platform support (as seen in `requirements.txt` with specific Windows modules).
- **Environment Management:** API keys and sensitive settings are expected to be managed securely (e.g., via `.env` or the config manager) to prevent committing secrets to source control.
- **Licensing:** The project is for personal and non-commercial use only (Creative Commons BY-NC 4.0).
