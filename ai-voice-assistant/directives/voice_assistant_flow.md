# Directive: Voice Assistant Runtime Flow (Master SOP + Interface Contract)

This is the master SOP for the sovereign Hyprland voice assistant **and** the binding
interface contract that every `execution/` module MUST conform to. Implementers: implement
the signatures below **exactly** — names, arguments, return types. Do not invent alternative
APIs; the daemon wires these together by name.

## Goal

Wake word → overlay shows → record-until-silence → transcribe (local GPU) → Claude
tool-calling → execute Hyprland action → speak streamed reply (Piper) → overlay hides →
re-arm.

## Stack (locked)

- Wake word: **openWakeWord** (ONNX), local.
- STT: **faster-whisper** on CUDA (`int8_float16`), CPU/`int8` fallback. Local.
- VAD (record-until-silence): **webrtcvad** (imports as `webrtcvad`; package
  `webrtcvad-wheels`). faster-whisper's own `vad_filter=True` is a second guard on the
  captured buffer.
- LLM: **cloud Anthropic Claude** with tool-calling + streaming (`anthropic` SDK). Key from
  `ANTHROPIC_API_KEY` env (loaded from `.env` via `python-dotenv`).
- TTS: **Piper** via subprocess, streamed and sentence-chunked into `aplay`.
- UI: **PyQt6** frameless overlay positioned by a Hyprland `windowrule` (v0.53+ syntax).

## Data conventions

- Audio buffers are `numpy.ndarray`, `dtype=float32`, mono, 16000 Hz, range [-1, 1].
- All modules use the stdlib `logging` module (logger name = module `__name__`). No bare prints.
- Config is loaded once via `config.load_settings()` and passed explicitly as a `Settings`
  object to constructors/functions. Modules MUST NOT read `config.toml` independently.
- Errors inside one pipeline iteration must never crash the daemon; the daemon catches,
  logs, plays nothing, and re-arms the wake listener.

## Threading model (critical — daemon owns it)

PyQt6 requires its `QApplication` and all widget mutations on the **main thread**.

- `daemon.py` runs `QApplication.exec()` on the **main thread** (the Qt event loop).
- A `StateBridge(QObject)` exposes `state_changed = pyqtSignal(str)`, connected to
  `Overlay.apply_state`. Anything off the GUI thread updates the overlay by `emit`ting this
  signal — never by calling widget methods directly.
- The wake-word listener runs in its **own thread** (inside `WakeWordListener`).
- When the wake word fires, its callback starts the **pipeline** on a separate
  `threading.Thread` (a worker), so the GUI thread stays responsive. Only one pipeline runs
  at a time (guard with a `threading.Lock`/flag).
- If `ui.enabled = false` or no display is available, run **headless**: skip QApplication,
  call the pipeline directly on the wake callback thread, and make `set_state` a no-op.

## config.Settings (authoritative field list)

`config.py` defines a frozen dataclass `Settings` and `load_settings(path: str | None = None)
-> Settings`. `load_settings` reads `config.toml` (stdlib `tomllib`), expands `~` in all
paths, loads `.env` via `python-dotenv`, and reads `ANTHROPIC_API_KEY` from env. Fields
(grouped by config.toml table, flattened with a prefix):

```
# [wake]
wake_model: str            # openWakeWord model name or path to .onnx
wake_threshold: float
wake_vad_threshold: float
wake_inference_framework: str   # "onnx"
# [audio]
sample_rate: int           # 16000
frame_size: int            # 1280
input_device: str          # "" => default device
# [recorder]
silence_ms: int
min_speech_ms: int
max_record_ms: int
recorder_vad_aggressiveness: int   # webrtcvad 0..3
start_grace_ms: int
# [whisper]
whisper_model: str
whisper_device: str        # "cuda" | "cpu"
whisper_compute_type: str
whisper_beam_size: int
whisper_language: str
# [llm]
llm_provider: str          # "anthropic"
llm_model: str
llm_max_tokens: int
llm_temperature: float
anthropic_api_key: str     # from env, NOT config.toml
# [tts]
tts_engine: str            # "piper"
tts_model_path: str        # expanded
tts_config_path: str       # expanded
tts_sample_rate: int       # 22050
tts_player: str            # "aplay" | "pw-play"
# [ui]
ui_enabled: bool
ui_window_class: str
ui_width: int
ui_height: int
# [logging]
log_level: str
```

## Python imports & packaging (binding)

- `execution/` is a package (`execution/__init__.py` exists). The daemon runs as
  `python -m execution.daemon` **from the repo root**.
- Cross-module imports use the **absolute** form: `from execution.hypr import dispatch_exec`,
  `from execution.config import Settings, load_settings`, etc. Do **not** use bare
  `import hypr` or relative `from .hypr import`.
- Each module's `if __name__ == "__main__":` CLI must also work via `python -m execution.<mod>`.

## Library landmines (verify against the INSTALLED package — do not code from memory)

The deps are installed in `.venv`. Before writing a module, introspect the real API
(`.venv/bin/python -c "import X; help(X.thing)"` or read the package source). Known traps:
- **openWakeWord**: construct `openwakeword.Model(wakeword_models=[<name-or-path>],
  inference_framework="onnx")`; call `model.predict(int16_frame) -> {model_name: score}`.
  You may need `openwakeword.utils.download_models()` once. Confirm exact arg/return shape.
- **webrtcvad**: `webrtcvad.Vad(aggressiveness)`; `is_speech(pcm16_bytes, sample_rate)` needs
  frames of exactly 10/20/30 ms (480 samples @16 kHz for 30 ms). Wrong frame size raises.
- **piper**: `pip install piper-tts` may expose the CLI as `python -m piper` (not a bare
  `piper` on PATH). The model's true sample rate is in the voice `.json` (`audio.sample_rate`)
  — read it rather than hardcoding 22050 if they differ. Build the pipe accordingly.
- **mic handoff**: `WakeWordListener.pause()` must `stop()`/close its `InputStream` (not just
  ignore frames) so `record_until_silence` can open the device cleanly; `resume()` reopens it.
- **faster-whisper**: `WhisperModel(...).transcribe(audio, ...)` returns
  `(segments_generator, info)`; you must iterate the generator to get text.
- **anthropic** (authoritative — from the `claude-api` skill; do NOT use stale recall):
  - Client: `anthropic.Anthropic(api_key=settings.anthropic_api_key)`. Model from
    `settings.llm_model` (default `claude-haiku-4-5`, a valid alias).
  - Tool schema shape: `{"name": str, "description": str, "input_schema": {"type":"object",
    "properties": {...}, "required": [...], "additionalProperties": False}}`. Optionally add
    top-level `"strict": True` (a sibling of `name`, NOT on `tool_choice`).
  - **Manual streaming tool-use loop** (the loop is non-streaming-shaped until the final turn):
    ```python
    messages = [{"role": "user", "content": user_text}]
    while True:
        with client.messages.stream(model=settings.llm_model,
                                     max_tokens=settings.llm_max_tokens,
                                     system=SYSTEM_PROMPT, tools=schemas,
                                     messages=messages) as stream:
            for chunk in stream.text_stream:
                ...  # buffer + yield on sentence boundaries
            msg = stream.get_final_message()
        messages.append({"role": "assistant", "content": msg.content})
        if msg.stop_reason == "tool_use":
            results = [{"type": "tool_result", "tool_use_id": b.id,
                        "content": call_tool(b.name, b.input)}
                       for b in msg.content if b.type == "tool_use"]
            messages.append({"role": "user", "content": results})
            continue
        break  # end_turn (or refusal → yield a short apology)
    ```
  - Handle `msg.stop_reason == "refusal"` (yield one short apology sentence, then stop).
  - **Do NOT pass `thinking`, `output_config`/`effort`, `temperature`, `top_p`, or `top_k`** —
    keeps the router valid across Haiku 4.5 (rejects `effort`) and Opus-4.8-class models
    (reject sampling params), and minimizes latency. `max_tokens` (1024) is well under the
    streaming-required threshold, so plain `messages.create` also works for `respond()`.

## Module contracts (`execution/`)

### config.py
- `@dataclass(frozen=True) class Settings:` — fields above.
- `def load_settings(path: str | None = None) -> Settings`
- `def configure_logging(settings: Settings) -> None` — sets root logging level/format.

### hypr.py
- `class HyprError(Exception): ...`
- `def dispatch_exec(command: str) -> None` — `hyprctl dispatch exec -- <command>`; raise
  `HyprError` on nonzero exit.
- `def dispatch(args: list[str]) -> str` — `hyprctl dispatch <args...>`, return stdout.
- `def active_window() -> dict` — parse `hyprctl activewindow -j` (return `{}` if none).
- `def clients() -> list[dict]` — parse `hyprctl clients -j`.

### wake_word.py
- `class WakeWordListener:`
  - `def __init__(self, settings: Settings, on_detected: Callable[[str], None]) -> None`
  - `def start(self) -> None` — spawn background daemon thread; open a 16 kHz mono
    `sounddevice.InputStream` (blocksize = `settings.frame_size`, dtype int16), feed frames
    to `openwakeword.Model`; when any model score ≥ `settings.wake_threshold`, call
    `on_detected(model_name)` once, then debounce.
  - `def stop(self) -> None`
  - `def pause(self) -> None` / `def resume(self) -> None` — pause must release/ignore the
    mic so `recorder.record_until_silence` can use it; resume re-arms.

### recorder.py
- `def record_until_silence(settings: Settings, on_level: Callable[[float], None] | None =
  None) -> "np.ndarray"` — open a 16 kHz mono float32 `InputStream`; buffer frames; use
  **webrtcvad** for speech/non-speech decisions. webrtcvad requires **16-bit PCM** frames of
  exactly 10/20/30 ms — use **30 ms = 480 samples @ 16 kHz**; convert each float32 frame to
  int16 bytes before `vad.is_speech(frame_bytes, 16000)`. Begin capturing on first detected
  speech (give up after `start_grace_ms` of no speech → return empty array); stop after
  `silence_ms` of continuous non-speech or `max_record_ms` cap. Discard and return empty
  array if captured speech < `min_speech_ms`. `on_level` (optional) receives per-frame RMS
  for UI metering. NOTE: the 480-sample VAD frame is independent of the wake listener's
  `frame_size`; read the stream in 480-sample blocks here.

### transcribe.py
- `class Transcriber:`
  - `def __init__(self, settings: Settings) -> None` — lazily construct
    `faster_whisper.WhisperModel`; if `device="cuda"` init fails, fall back to CPU/`int8`
    and log a warning.
  - `def transcribe(self, audio: "np.ndarray") -> str` — `vad_filter=True`,
    `beam_size=settings.whisper_beam_size`, `language=settings.whisper_language`; join
    segment texts; return stripped string.
- CLI: `python -m execution.transcribe <file.wav>` prints the transcript.

### tools.py
- A lightweight registry built from function signatures + docstrings (blueprint's
  inspect-driven approach, no heavy deps):
  - `@register_tool` decorator: introspects the function's signature and docstring to build
    an Anthropic tool schema (`{"name","description","input_schema":{...}}`); registers the
    callable.
  - `def get_tool_schemas() -> list[dict]` — all registered Anthropic tool schemas.
  - `def call_tool(name: str, arguments: dict) -> str` — execute and return a short result
    string for the model; catch exceptions and return `"Error: ..."`.
- MVP tool:
  - `def launch_application(target: str) -> str` — docstring: "Launch a desktop application
    by its executable name (e.g. 'firefox', 'kitty'). Use for any 'open/launch/start X'
    request." Calls `hypr.dispatch_exec(target)`; returns confirmation text.
- Adding tools later = define a function + `@register_tool`; no other change.

### llm_router.py
- `SYSTEM_PROMPT: str` — concise: a Hyprland desktop assistant; use tools to act; keep spoken
  replies to one short sentence; never output markdown/code fences (text is spoken aloud).
- `class LLMRouter:`
  - `def __init__(self, settings: Settings) -> None` — `anthropic.Anthropic(api_key=...)`.
  - `def run(self, user_text: str) -> "Iterator[str]"` — run the tool-use loop: call
    Messages API with `tools=tools.get_tool_schemas()`; on `tool_use` blocks, execute via
    `tools.call_tool` and continue; **stream** the final assistant text and `yield` it split
    on sentence boundaries (so TTS can start early). Yields nothing if the model only acted
    silently (then daemon may speak a default confirmation).
  - `def respond(self, user_text: str) -> str` — non-streaming convenience (tests): full
    final text.

### tts.py
- `def speak(text: str, settings: Settings) -> None` — synth + play whole text (blocking).
- `def speak_stream(sentences: "Iterable[str]", settings: Settings) -> None` — for each
  incoming sentence, pipe text to `piper -m <model> -c <config> --output-raw | <player> -r
  <sr> -f S16_LE -t raw -` so audio starts on sentence 1 while later ones synthesize. Strip
  markdown/syntax chars before synthesis.
- CLI: `python -m execution.tts "<text>"` speaks it.

### ui_overlay.py
- `class Overlay(QWidget):`
  - `def __init__(self, settings: Settings) -> None` — frameless, translucent,
    always-on-top, input-transparent (`Qt.WindowType.FramelessWindowHint |
    WindowStaysOnTopHint | Tool`, `WA_TranslucentBackground`); set `windowTitle` and object
    name to `settings.ui_window_class` so Hyprland rules match `class:^(voice_assistant)$`.
  - `def apply_state(self, state: str) -> None` — GUI-thread-only slot; `state` in
    {`"listening"`,`"thinking"`,`"speaking"`,`"hidden"`}; show/hide + update a simple animated
    indicator (QPainter + QTimer pulse).
- `def create_overlay(settings: Settings) -> Overlay`

### daemon.py (integration owner)
- `def main() -> None`:
  1. `settings = load_settings(); configure_logging(settings)`.
  2. Construct `Transcriber`, `LLMRouter`.
  3. If `settings.ui_enabled` and a display is present: create `QApplication`, `Overlay`,
     and a `StateBridge(QObject)` with `state_changed = pyqtSignal(str)` connected to
     `overlay.apply_state`; define `set_state(s)` = `bridge.state_changed.emit(s)`. Else
     headless: `set_state = lambda s: None`.
  4. Define `pipeline()` (runs on a worker thread): guard re-entrancy; `listener.pause()`;
     `set_state("listening")`; `audio = record_until_silence(settings)`; if empty → reset &
     return; `set_state("thinking")`; `text = transcriber.transcribe(audio)`; if blank →
     return; `set_state("speaking")`; `tts.speak_stream(router.run(text), settings)`;
     `set_state("hidden")`; finally `listener.resume()`. Wrap in try/except that logs and
     re-arms.
  5. `on_detected(name)` → start `pipeline` on a `threading.Thread` if none running.
  6. Create + `start()` the `WakeWordListener`. If GUI: `app.exec()`. Else: block forever.
- CLI: `python -m execution.daemon`.

## Tunables, install, and operations
See `config.toml`, `directives/wake_word.md`, `directives/transcription.md`,
`directives/command_routing.md`, and `directives/hyprland_control.md` (systemd + window
rules + Piper/openWakeWord model install).

## Self-annealing
When a step breaks at runtime: read the trace, fix the relevant `execution/` script, re-test
that layer standalone (see verification commands in each directive), then update the affected
directive with the learning (API quirk, timing, device fallback). Do not discard directives.
