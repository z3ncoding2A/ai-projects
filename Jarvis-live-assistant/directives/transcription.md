# Directive: Transcription (STT) SOP

Standard operating procedure for the speech-to-text layer. Implements
`record-until-silence` (`execution/recorder.py`) → `Transcriber`
(`execution/transcribe.py`). Audio convention throughout: `numpy.ndarray`,
`dtype=float32`, mono, 16000 Hz, range `[-1, 1]`.

Config is read once into the frozen `Settings` dataclass (`execution/config.py`);
modules receive `Settings` and never read `config.toml` directly.

## Stack

- STT engine: **faster-whisper** (`WhisperModel`, ctranslate2 backend).
- Capture VAD: **webrtcvad** (`import webrtcvad`; pip package `webrtcvad-wheels`).
- faster-whisper's own `vad_filter=True` is a **second** guard applied to the
  already-captured buffer at decode time.

## faster-whisper tunables (`[whisper]` in config.toml)

| config.toml key | Settings field        | default          | notes |
|-----------------|-----------------------|------------------|-------|
| `model`         | `whisper_model`        | `small.en`       | faster-whisper model id (`tiny[.en]`, `base[.en]`, `small[.en]`, `medium[.en]`, `large-v3`) or a local CT2 dir. `.en` variants are faster/better for English-only. |
| `device`        | `whisper_device`       | `cuda`           | `"cuda"` or `"cpu"`. Auto-falls back to CPU (see below). |
| `compute_type`  | `whisper_compute_type` | `int8_float16`   | GPU: `int8_float16` / `float16` / `int8`. CPU fallback is **forced to `int8`** regardless of this value. |
| `beam_size`     | `whisper_beam_size`    | `1`              | `1` = greedy = fastest. Raise (e.g. 5) for accuracy at higher latency. |
| `language`      | `whisper_language`     | `en`             | Passed to `transcribe(language=...)`. Set to skip language auto-detect. |

The model is built **lazily** on the first `transcribe()` call (not at
construction), so daemon startup stays cheap and any GPU init error surfaces
where it can be caught and recovered.

Decode call (`transcribe.py`): `model.transcribe(audio, vad_filter=True,
beam_size=whisper_beam_size, language=whisper_language)`. It returns
`(segments_generator, info)`; the generator must be iterated to do the decode.
Text is `"".join(seg.text)` then `.strip()`.

## CUDA → CPU fallback

`Transcriber._ensure_model()` tries `WhisperModel(model, device=whisper_device,
compute_type=whisper_compute_type)`. On **any** exception (typical cause: no
CUDA / missing cuDNN / mismatched compute type) it logs a WARNING with traceback
and rebuilds as `WhisperModel(model, device="cpu", compute_type="int8")`. The
fallback ignores the configured `compute_type` and always uses `int8`. To force
CPU outright, set `device = "cpu"` in config.toml.

## record-until-silence (webrtcvad) params (`[recorder]` + `[audio]`)

`record_until_silence(settings, on_level=None)` opens a 16 kHz mono float32
`sounddevice.InputStream` and reads it in fixed **30 ms = 480-sample** blocks
(webrtcvad accepts only 10/20/30 ms frames; constants `_FRAME_MS=30`,
`_BLOCK_SAMPLES=480`). Each block is clipped to `[-1,1]`, scaled to int16 PCM
bytes, and passed to `vad.is_speech(pcm16_bytes, 16000)`. This 480-sample block
is **independent** of the wake listener's `frame_size`.

| config.toml key (table)        | Settings field                | default | meaning |
|--------------------------------|-------------------------------|---------|---------|
| `[recorder] vad_aggressiveness`| `recorder_vad_aggressiveness` | `2`     | `webrtcvad.Vad(0..3)`; 0 = lax, 3 = strict (fewer false positives, may clip soft speech). |
| `[recorder] start_grace_ms`    | `start_grace_ms`              | `1500`  | Wait this long for speech to begin; if none, return empty array. |
| `[recorder] silence_ms`        | `silence_ms`                  | `700`   | Stop after this much **continuous** non-speech once capture started. |
| `[recorder] max_record_ms`     | `max_record_ms`               | `15000` | Hard cap on a single utterance. |
| `[recorder] min_speech_ms`     | `min_speech_ms`               | `300`   | Discard (return empty) if total *speech* (not buffer) is shorter; filters coughs/blips. |
| `[audio] input_device`         | `input_device`                | `""`    | `""` → system default device (passed to sounddevice as `None`). |

Thresholds are derived as block counts: `silence_blocks = silence_ms // 30`,
`grace_blocks = start_grace_ms // 30`, `max_blocks = max_record_ms // 30` (each
floored to ≥ 1). `min_speech_ms` is checked against `speech_blocks * 30`.

Returns an empty `float32` array if speech never started, the utterance was too
short, or the input stream failed to open. `on_level` (optional) receives
per-block RMS for the UI meter.

## Testing transcribe.py on a sample WAV

Run from the **repo root** (`execution/` is a package; the daemon convention is
`python -m execution.<mod>`).

```bash
# uses the .venv interpreter
.venv/bin/python -m execution.transcribe path/to/sample.wav
```

Prints the transcript to stdout. Logging level comes from `[logging] level`
(set `level = "DEBUG"` in config.toml for verbose model-load / fallback logs).

WAV loading (`_load_wav`): prefers `soundfile` (any format, auto mono mixdown).
**`soundfile` is not currently installed in `.venv`**, so the CLI falls back to
the stdlib `wave` module, which supports **16-bit PCM only**; non-16-bit files
raise `ValueError`. A non-16 kHz file is accepted but logs a warning and may
transcribe poorly. To make a known-good sample:

```bash
# 16 kHz, mono, 16-bit PCM — guaranteed loadable by the wave fallback
ffmpeg -i input.any -ar 16000 -ac 1 -c:a pcm_s16le sample.wav
.venv/bin/python -m execution.transcribe sample.wav
```

To exercise the live capture path (record one utterance, report length only):

```bash
.venv/bin/python -m execution.recorder   # "Speak now..." then prints sample/ms count
```

## Self-annealing

If STT breaks at runtime: read the traceback; if it is a CUDA/cuDNN init failure
confirm the fallback fired (WARNING log) — persistent GPU failure means set
`device = "cpu"`. Re-test this layer standalone with the commands above, then
record the learning (driver quirk, compute_type mismatch, device id) back into
this directive.
