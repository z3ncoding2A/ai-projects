# Project: hypr-tts

A Text-to-Speech (TTS) utility designed for Wayland environments, specifically leveraging `edge-tts` to convert selected text into speech and playing it via `mpv`.

## Project Overview

- **Purpose:** Converts the currently highlighted text (via `wl-clipboard`) into speech using `edge-tts` and streams the audio playback through `mpv`.
- **Technologies:** Python 3 (asyncio), `edge-tts`, `mpv`, `wl-clipboard` (Wayland).
- **Architecture:** 
  - `tts.py`: Main logic handling configuration, text extraction, chunking (for stability), and piping audio to `mpv`.
  - `hypr-tts.sh`: Wrapper script ensuring the project's Python virtual environment is used.
  - Configuration: Stored at `~/.config/hypr-tts/config.json`.

## Building and Running

The project expects a Python virtual environment located in `venv/`.

- **To run:** Use the provided wrapper script:
  ```bash
  ./hypr-tts.sh
  ```
- **Prerequisites:**
  - `python3` with `edge-tts` installed in `venv/`.
  - `mpv` installed on the system.
  - `wl-clipboard` installed for text extraction.

## Development Conventions

- **Language:** Python 3.
- **Async:** The core logic is asynchronous using `asyncio` for efficient streaming of TTS data to `mpv`.
- **Configuration:** Sensible defaults are provided in `tts.py` and persisted in `~/.config/hypr-tts/config.json`.
- **Modularity:** Text is processed in chunks (max 1500 chars) to prevent `edge-tts` truncation issues.
