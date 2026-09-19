# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository is two merged projects

This workspace (`Jarvis-live-assistant`) is a merge of **two distinct assistants** that share a directory but not an architecture. Don't assume code in one applies to the other.

1. **MARK XLVI ("J.A.R.V.I.S.")** — Gemini Live API based, GUI-driven assistant.
   Entry point: `main.py`. Uses `ui.py` (PyQt6 HUD), `actions/`, `core/`, `dashboard/`,
   `memory/`, `config/`.
2. **Sovereign Hyprland Voice Assistant** — Anthropic Claude based, headless/overlay
   voice daemon for Hyprland. Entry point: `execution/daemon.py`, run as
   `python -m execution.daemon`. Uses `execution/`, `directives/`, `config.toml`.

`README.md` / `readme.md` / `CONFIGURATION_MANUAL.md` describe project 1 (MARK XLVI).
`GEMINI.md` describes project 2 (the Hyprland daemon) despite its filename.
`AGENTS.md` describes a generic 3-layer directive/orchestration/execution pattern that
applies conceptually to project 2's `directives/` + `execution/` split, not to project 1.

When making a change, first determine which of the two systems the file belongs to —
`actions/`, `core/`, `main.py`, `ui.py`, `dashboard/`, `memory/`, `config/` vs.
`execution/`, `directives/`, `config.toml`.

## Running and building

**MARK XLVI (Gemini, project 1):**
```bash
python setup.py            # installs requirements.txt + playwright browsers
python main.py              # entry point
```
API key resolution: `GEMINI_API_KEY` env var first, then `config/api_keys.json`
(`{"gemini_api_key": ..., "os_system": "linux"|"windows"|"mac"}`).
System prompt lives in `core/prompt.txt` (editable, controls persona/response style/tool
routing rules).
Dashboard (FastAPI, remote/phone control): `dashboard/server.py`, port 8000 (HTTP) /
8001 (HTTPS alias if `config/certs/jarvis.crt` + `jarvis.key` exist).

**Sovereign Hyprland Voice Assistant (Claude, project 2):**
```bash
# Must use Python 3.11 — openWakeWord/onnxruntime/ctranslate2/webrtcvad-wheels have no
# 3.12+/3.13 wheels.
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m execution.daemon        # full daemon
```
`ANTHROPIC_API_KEY` goes in `.env` at repo root (real env var takes precedence).
Config is `config.toml`, loaded once into a frozen `Settings` dataclass by
`execution/config.py` — other modules never read `config.toml` directly.

Per-module manual verification (each runnable standalone from repo root via the venv):
```bash
.venv/bin/python -m execution.config        # dump resolved Settings (API key redacted)
.venv/bin/python -m execution.wake_word     # listen + print on detection
.venv/bin/python -m execution.recorder      # record one utterance until silence
.venv/bin/python -m execution.transcribe path/to/file.wav
.venv/bin/python -m execution.tools         # print tool schemas, exercises call_tool
.venv/bin/python -m execution.llm_router "open firefox"
.venv/bin/python -m execution.tts "Hello from the voice assistant."
```
There is no automated test suite for either project — these manual per-module runs are
the verification method.

System binaries required (not pip-installable): `piper` (TTS, on PATH), `aplay` or
`pw-play`, a downloaded Piper voice model at the path in `config.toml`, and `hyprctl`
(Hyprland).

## Architecture: Sovereign Hyprland Voice Assistant

Runtime flow for one wake-word iteration, owned by `execution/daemon.py`:

1. `wake_word.WakeWordListener` (openWakeWord, ONNX) detects the wake word, fires
   `on_detected`.
2. Daemon spawns a pipeline on a worker thread (one at a time, lock-guarded):
   - `listener.pause()` releases the mic.
   - overlay -> `listening`; `recorder.record_until_silence()` captures one utterance
     (webrtcvad, 16 kHz mono, 30 ms/480-sample frames).
   - overlay -> `thinking`; `transcribe.Transcriber` runs faster-whisper (CUDA -> CPU
     int8 fallback).
   - overlay -> `speaking`; `llm_router.LLMRouter.run()` streams Claude's reply
     sentence-by-sentence, executing tool-use blocks via the `tools.py` registry;
     `tts.speak_stream()` pipes each sentence to Piper so audio starts on sentence 1.
   - overlay -> `hidden`; `listener.resume()` re-arms the mic.
3. Errors inside an iteration are logged and never crash the daemon; it always re-arms.

The optional PyQt6 overlay (`ui_overlay.py`) runs Qt's event loop on the main thread;
off-thread state updates cross via a `StateBridge` pyqtSignal. Without a display or with
the UI disabled, the daemon runs headless and blocks forever.

**Adding a tool**: write a function with a docstring in `execution/tools.py`, decorate
with `@register_tool`. The Anthropic tool schema is derived from the function signature
automatically — nothing else needs to change. Currently only `launch_application` ships;
`hypr.py` exposes `dispatch`/`active_window`/`clients` but no tools wrap them yet.

`[llm] model` in `config.toml` defaults to `claude-haiku-4-5` for low latency; the router
intentionally never sends `temperature`/`top_p`/`top_k`/`thinking`, so `[llm] temperature`
has no effect regardless of what it's set to.

`directives/*.md` (`command_routing.md`, `hyprland_control.md`, `transcription.md`,
`voice_assistant_flow.md`, `wake_word.md`) are the living SOPs for this system — per
`AGENTS.md`'s 3-layer model, update them when you discover new API constraints or
behavior, but don't overwrite/create directives without asking unless told to.

## Architecture: MARK XLVI

`main.py` manages Gemini Live API client sessions (`models/gemini-2.5-flash-native-audio-preview-12-2025`),
schedules dashboard background tasks, and coordinates audio streams
(`sounddevice`, 16 kHz send / 24 kHz receive) plus the PyQt6 UI (`ui.py`) states.

Tool-calling actions live in `actions/` as individual modules imported directly into
`main.py` (`open_app`, `flight_finder`, `weather_action`, `send_message`, `reminder`,
`computer_settings`, `screen_process`, `youtube_video`, `desktop_control`,
`browser_control`, `file_controller`, `code_helper`, `dev_agent`, `web_search`,
`computer_control`, `game_updater`). Each is declared to Gemini via `TOOL_DECLARATIONS`
in `main.py`. To add a new capability, write the module in `actions/`, import it, and add
its declaration.

`memory/memory_manager.py` persists long-term facts/preferences to JSON and formats them
back into the system prompt on load (`load_memory`, `update_memory`,
`format_memory_for_prompt`).

`dashboard/server.py` is a FastAPI app for remote/phone control: WebSocket mic streaming,
file upload up to 500 MB, AES-256-CBC session-key-derived encryption at the application
layer (not just relying on TLS). HTTPS is enabled automatically only when both
`config/certs/jarvis.crt` and `jarvis.key` are present; otherwise it serves plain HTTP.

Cross-platform: Windows-only deps (`comtypes`, `pycaw`, `win10toast`, `pywinauto`) are
conditioned on `sys_platform == "win32"` in `requirements.txt` — keep any new
platform-specific dependency guarded the same way, and account for `os_system`
(`linux`/`windows`/`mac`) in `config/api_keys.json` when writing OS-dependent action code.

## Deployment

`voice-assistant.service` is a systemd **user** unit for the Hyprland daemon
(`execution/daemon.py`), not MARK XLVI. For the service to reach the Wayland compositor,
`WAYLAND_DISPLAY`/`XDG_RUNTIME_DIR` must be imported into the systemd user environment.
