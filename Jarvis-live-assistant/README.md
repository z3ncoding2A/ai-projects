# Sovereign Hyprland Voice Assistant

A local-first, push-nothing-to-the-cloud-but-the-LLM voice assistant for a
Hyprland (Wayland) Linux desktop. Say the wake word, speak a command, and Claude
decides which desktop action to take (e.g. launch an app) and speaks a short reply.

Speech recognition, wake-word detection, and text-to-speech all run **locally**.
Only the language/tool-routing step calls the cloud (Anthropic Claude).

## Architecture

```
wake word  ->  record-until-silence  ->  STT  ->  Claude (tool-calling)  ->  TTS
openWakeWord    webrtcvad VAD            faster-   anthropic SDK,           Piper -> aplay/pw-play
(ONNX, local)   (16 kHz mono)            whisper   streaming + tools        (local, streamed)
                                         (local)
```

Runtime flow (one iteration), owned by `execution/daemon.py`:

1. The wake-word listener detects the configured wake word and fires `on_detected`.
2. The daemon spawns a **pipeline** on a worker thread (one at a time, guarded by a lock):
   - `listener.pause()` releases the mic.
   - overlay -> `listening`; `record_until_silence()` captures one utterance via webrtcvad.
   - overlay -> `thinking`; `Transcriber.transcribe()` runs faster-whisper.
   - overlay -> `speaking`; `LLMRouter.run()` streams Claude's reply sentence-by-sentence,
     executing any tool-use blocks (e.g. `launch_application`) via the tool registry;
     `tts.speak_stream()` pipes each sentence to Piper so audio starts on sentence 1.
   - overlay -> `hidden`; `listener.resume()` re-arms the mic.
3. Errors inside an iteration are logged and never crash the daemon; it always re-arms.

The PyQt6 overlay (optional) shows the state. Qt runs its event loop on the main
thread; off-thread state updates go through a `StateBridge` pyqtSignal. If the UI is
disabled or no display is present, the daemon runs **headless** (no Qt) and blocks forever.

### Layout

- `execution/` — deterministic Python modules (the implementation). Run as a package:
  `python -m execution.<module>` from the repo root.
  - `config.py` — loads `config.toml` + `.env` into a frozen `Settings` dataclass.
  - `wake_word.py` — `WakeWordListener` (openWakeWord, owns the mic + pause/resume handshake).
  - `recorder.py` — `record_until_silence()` (webrtcvad, 30 ms / 480-sample frames).
  - `transcribe.py` — `Transcriber` (faster-whisper, CUDA->CPU fallback).
  - `tools.py` — signature/docstring-driven Anthropic tool registry; MVP tool `launch_application`.
  - `llm_router.py` — `LLMRouter` (manual streaming tool-use loop against Claude).
  - `tts.py` — `speak` / `speak_stream` (Piper subprocess piped to `aplay`/`pw-play`).
  - `ui_overlay.py` — `Overlay` (frameless PyQt6 status indicator).
  - `daemon.py` — integration owner; wires it all together.
- `directives/voice_assistant_flow.md` — master SOP + interface contract.
- `config.toml` — all tunables. `.env` — `ANTHROPIC_API_KEY`.
- `voice-assistant.service` — systemd **user** unit.

## Requirements

- **Python 3.11 (required).** openWakeWord / onnxruntime / ctranslate2 / webrtcvad-wheels
  do not ship wheels for 3.12+/3.13. The venv must be built on 3.11.
- Hyprland (provides `hyprctl`).
- System binaries (NOT pip): `piper` (TTS) on PATH, `aplay` (alsa-utils) or `pw-play`
  (pipewire), and a downloaded Piper voice model.
- An Anthropic API key.
- Optional: NVIDIA GPU with CUDA 12 + cuDNN for GPU whisper; otherwise it falls back to CPU/int8.

## Setup

### 1. Create the 3.11 virtualenv and install Python deps

```bash
cd ~/ai-projects/ai-voice-assistant

# Preferred (uv):
uv venv --python python3.11 .venv
uv pip install --python .venv/bin/python -r requirements.txt

# Or with the stdlib venv:
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### 2. Download the openWakeWord models

The listener auto-downloads missing feature/VAD/wake models on first run. To pre-fetch:

```bash
.venv/bin/python -c "import openwakeword.utils as u; u.download_models()"
```

The default wake word is `hey_jarvis` (set `[wake] model` in `config.toml`; a custom
`.onnx` path is also accepted).

### 3. Download a Piper voice

`config.toml` defaults to `en_US-lessac-high`. Both the `.onnx` and its `.onnx.json`
must exist at the configured paths:

```bash
mkdir -p ~/.local/share/piper
# Download en_US-lessac-high.onnx and en_US-lessac-high.onnx.json from the Piper
# voices repo (rhasspy/piper-voices) into ~/.local/share/piper/
```

Verify the binary: `piper --help` (the `--output_raw`/`--output_file` flags use
underscores — do not change them to hyphens).

### 4. Set the API key

Put your key in `.env` at the repo root (loaded via python-dotenv):

```
ANTHROPIC_API_KEY="sk-ant-..."
```

A real-environment `ANTHROPIC_API_KEY` takes precedence over `.env`.

## Running

```bash
cd ~/ai-projects/ai-voice-assistant
.venv/bin/python -m execution.daemon
```

### As a systemd user service

```bash
cp voice-assistant.service ~/.config/systemd/user/voice-assistant.service
systemctl --user daemon-reload
systemctl --user enable --now voice-assistant
journalctl --user -u voice-assistant -f
```

For the service to reach the compositor, Hyprland should import the session env at
startup (`systemctl --user import-environment WAYLAND_DISPLAY XDG_RUNTIME_DIR`), or
uncomment/adjust the `WAYLAND_DISPLAY` / `XDG_RUNTIME_DIR` lines in the unit.

## Per-layer verification

Each module is independently runnable for testing (all from the repo root, via the venv):

```bash
# Config: dump the resolved Settings (API key redacted)
.venv/bin/python -m execution.config

# Wake word: listen and print on detection; exercises pause/resume
.venv/bin/python -m execution.wake_word

# Recorder: record one utterance until silence and report its length
.venv/bin/python -m execution.recorder

# STT: transcribe a 16 kHz mono WAV
.venv/bin/python -m execution.transcribe path/to/file.wav

# Tools: print tool schemas and exercise call_tool (will launch kitty)
.venv/bin/python -m execution.tools

# LLM router: run the tool-use loop on a prompt (defaults to "open firefox")
.venv/bin/python -m execution.llm_router "open firefox"

# TTS: synthesize and speak text through Piper + the configured player
.venv/bin/python -m execution.tts "Hello from the voice assistant."

# Full daemon
.venv/bin/python -m execution.daemon
```

## Hyprland window rules

The overlay sets its Wayland app_id / XWayland WM_CLASS to `[ui] window_class`
(default `voice_assistant`) via `QApplication.setDesktopFileName`. The widget is
already frameless, translucent, always-on-top, and input-transparent in code
(`ui_overlay.py`) and self-sizes to `[ui] width`/`height` via `resize()`. The
Hyprland rules below mainly float it, center it on the active monitor, and pin it
across workspaces:

```
# Hyprland v0.53+ / HyDE inline syntax. With HyDE, add to ~/.config/hypr/windowrules.conf
windowrule = float 1,match:class ^(voice_assistant)$
windowrule = center 1,match:class ^(voice_assistant)$
windowrule = pin 1,match:class ^(voice_assistant)$
windowrule = noborder 1,match:class ^(voice_assistant)$
windowrule = nofocus 1,match:class ^(voice_assistant)$
# Optional belt-and-suspenders; the overlay already resize()s itself.
# Match this to [ui] width/height in config.toml:
windowrule = size 500 300,match:class ^(voice_assistant)$
```

## Configuration

All tunables live in `config.toml` (loaded once into `Settings`; modules never read it
directly). Notable keys: `[wake] model/threshold/vad_threshold`, `[recorder]
silence_ms/min_speech_ms/max_record_ms/vad_aggressiveness/start_grace_ms`, `[whisper]
model/device/compute_type/beam_size`, `[llm] model/max_tokens` (the router intentionally
does **not** send `temperature`/`top_p`/`top_k`/`thinking`, so changing
`[llm] temperature` has no effect), `[tts] model_path/config_path/player`, and `[ui]
enabled/window_class/width/height`.

The LLM router defaults to `claude-haiku-4-5` (low latency); swap `[llm] model` for a
Sonnet/Opus id for smarter routing.

## Adding tools

Define a function with a docstring (the model reads it to know when to use the tool) and
decorate it with `@register_tool` in `execution/tools.py`. The Anthropic schema is derived
automatically from the signature; no other change is needed.

## Deferred features

- **Only one MVP tool** ships: `launch_application` (launch a desktop app via
  `hyprctl dispatch exec`). Richer desktop control (window focus/move, workspace
  switching, media keys) is not yet implemented — `hypr.py` exposes `dispatch`,
  `active_window`, and `clients` but no tools wrap them yet.
- **No default spoken confirmation** when the model acts silently (yields no text); the
  daemon currently just stays quiet in that case.
- **tflite** wake inference framework is configurable but only `onnx` is exercised.
- **No conversation memory**: each utterance is an independent single-turn request.
</content>
</invoke>
