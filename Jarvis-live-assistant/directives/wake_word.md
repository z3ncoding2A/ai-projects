# Directive: Wake-Word Layer SOP

Operating procedure for the wake-word layer of the Hyprland voice assistant.
This is the always-on front end: it listens on the microphone and fires the
pipeline when the wake phrase is heard. Implemented in
`execution/wake_word.py`; tunables live in `config.toml` under `[wake]` and
`[audio]`. This doc must match the actual implementation — verify with the
commands below before changing behavior.

## What it does

`WakeWordListener` (in `execution/wake_word.py`) runs a background daemon
thread that:

1. Opens a **16 kHz mono int16** `sounddevice.InputStream` (`blocksize =
   settings.frame_size`, `device = settings.input_device or default`).
2. Feeds each frame's 1-D int16 array to `openwakeword.model.Model.predict()`,
   which returns `{model_name: score}`.
3. When the top score `>= settings.wake_threshold`, calls
   `on_detected(model_name)` once, then debounces for **2.0 s**
   (`_DEBOUNCE_SECONDS`) and calls `Model.reset()` to flush prediction buffers
   so the same utterance does not retrigger.

The daemon (`execution/daemon.py`) constructs it as
`WakeWordListener(settings, on_detected)` and calls `.start()`. The callback
launches the record→transcribe→respond→speak pipeline on a worker thread.

### Mic handoff (pause/resume)

The wake stream and the recorder cannot hold the mic at the same time.

- `pause()` — synchronous handshake. Sets a flag; the worker finishes its
  current read, **stops and closes** the `InputStream`, then acks. `pause()`
  blocks (up to 5 s) until the mic is confirmed released, so
  `recorder.record_until_silence` can open the device without racing.
- `resume()` — re-arms; the worker reopens the stream.
- The thread that opened the stream is the one that closes it (no cross-thread
  close race). The detection callback is dispatched on a short-lived thread, not
  the worker thread, to avoid a deadlock where `pause()` waits on a worker that
  is itself blocked in the callback.

## openWakeWord usage

- Constructor (verified against the installed package):
  `Model(wakeword_models=[settings.wake_model],
  vad_threshold=settings.wake_vad_threshold,
  inference_framework=settings.wake_inference_framework)`.
- `model.predict(int16_1d_ndarray) -> {model_name: float}`.
- `model.reset()` clears internal buffers after a detection.
- Built-in VAD gate: when `wake_vad_threshold > 0`, openWakeWord runs Silero
  VAD and suppresses inference on non-speech frames. Set to `0` to disable.
  This is independent of the recorder's webrtcvad.

## Tunables (config.toml)

Loaded once by `execution/config.py` into the frozen `Settings` dataclass.
Modules never read `config.toml` directly. Relevant keys:

```toml
[wake]
model = "hey_jarvis"          # -> settings.wake_model
threshold = 0.5               # -> settings.wake_threshold  (detection cutoff, 0-1)
vad_threshold = 0.5           # -> settings.wake_vad_threshold  (Silero VAD gate; 0 disables)
inference_framework = "onnx"  # -> settings.wake_inference_framework  ("onnx" | "tflite")

[audio]
sample_rate = 16000           # -> settings.sample_rate   (must stay 16 kHz for the models)
frame_size = 1280             # -> settings.frame_size     (samples/inference, ~80 ms @ 16 kHz)
input_device = ""             # -> settings.input_device   ("" = system default)
```

Tuning guidance:
- `threshold`: raise toward 0.6-0.7 if you get false triggers; lower toward
  0.3-0.4 if the wake word is missed. It is compared against the single
  top-scoring model per frame.
- `vad_threshold`: raise to cut false triggers in noisy/TV environments; `0`
  disables the gate (and means `_ensure_models` no longer *requires* the
  Silero VAD model on disk; a no-arg `download_models()` still fetches it).
- `model`: a pretrained name (see below) **or** an absolute/relative path to a
  custom `.onnx`. A value ending in `.onnx` or containing a path separator is
  treated as a file path and used as-is.
- `frame_size`: leave at 1280; openWakeWord expects 80 ms blocks at 16 kHz.

### Pretrained model names

Installed pretrained wake models (`openwakeword.MODELS`):
`alexa`, `hey_mycroft`, `hey_jarvis`, `hey_rhasspy`, `timer`, `weather`.
The default is `hey_jarvis`.

## Downloading models

The required ONNX assets are **auto-downloaded on first run** by
`_ensure_models()` in `wake_word.py`. It checks the bundled
`openwakeword/resources/models` directory for:

- the mandatory feature models (melspectrogram + embedding),
- the Silero VAD model (only when `vad_threshold > 0`),
- the selected pretrained wake model (skipped when `wake_model` is a custom
  `.onnx` path).

If any are missing it calls `openwakeword.utils.download_models()` (no args),
which fetches the full safe superset and is idempotent.

To pre-fetch manually (NOTE: there is **no** `openwakeword download_models`
console script or runnable `-m openwakeword.download_models` module in this
install — invoke the library function directly):

```bash
# From the repo root, using the project venv:
.venv/bin/python -c "from openwakeword.utils import download_models; download_models()"
```

Models land in the package's `resources/models` directory
(`.venv/lib/python3.11/site-packages/openwakeword/resources/models`). To list
the directory openWakeWord resolves to:

```bash
.venv/bin/python -c "import openwakeword,os; print(os.path.join(os.path.dirname(openwakeword.__file__),'resources','models'))"
```

## Testing wake_word.py standalone

The module has a smoke-test entrypoint. Run it from the repo root using the
project venv:

```bash
.venv/bin/python -m execution.wake_word
```

Behavior:
- Loads `Settings`, configures logging, ensures/downloads models, and starts
  the listener.
- Prints `Listening for wake word... (Ctrl+C to quit)`.
- On detection prints `[wake] detected: <model>`, then exercises the
  pause/resume handshake (`pausing (releasing mic)...` → 1 s → `resuming...`),
  which is exactly the mic handoff the daemon depends on.
- Ctrl+C stops the listener cleanly.

To watch scores/VAD activity for threshold tuning, set `[logging] level =
"DEBUG"` in `config.toml`; the listener logs stream open/close and overflow
events at DEBUG and each detection (with score) at INFO.

## Custom-phrase training — DEFERRED

Training a custom wake phrase (your own `.onnx` via openWakeWord's
synthetic-data training pipeline) is **deferred**. The layer already supports a
custom model: point `[wake] model` at an absolute path to a trained `.onnx` and
`_ensure_models()` will use it as-is (fetching only the feature/VAD models). No
code change is needed when that model exists; only the training workflow is out
of scope for now. Until then, use a pretrained name from the list above.

## Self-annealing

If wake detection misbehaves at runtime: reproduce with the standalone command
above at DEBUG level, adjust `threshold`/`vad_threshold`, and if you change
listener behavior, update this directive with the learning (API quirk, timing,
device handoff). Do not discard the directive.
