#!/usr/bin/env bash
#
# setup.sh — bootstrap the Hyprland voice assistant.
#
# What it does (idempotent — safe to re-run):
#   1. Creates a Python 3.11 virtualenv at ./.venv (uv if present, else venv).
#   2. Installs requirements.txt into that venv.
#   3. Downloads the openWakeWord model assets via the venv python.
#   4. Prints next steps: install Piper + a voice model, add hyprland.conf rules.
#
# It does NOT assume a GPU: faster-whisper auto-falls back to CPU/int8, and the
# default onnxruntime (CPU) wheel is what requirements.txt pins. For GPU wake
# inference / STT you can later swap to onnxruntime-gpu and a CUDA toolchain.
#
# Usage:  ./setup.sh   (run from anywhere; it cd's to the repo root itself)

set -euo pipefail

# --- locate the repo root (directory of this script) -----------------------
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

VENV="$ROOT/.venv"
PY=python3.11   # the project REQUIRES 3.11 (no wheels for openWakeWord/ct2 on 3.13+)

# --- 1. create the virtualenv ----------------------------------------------
# Idempotent: only build the venv if its interpreter is missing.
if [ -x "$VENV/bin/python" ]; then
    echo "[setup] venv already present at $VENV — reusing."
else
    if command -v "$PY" >/dev/null 2>&1; then
        :
    else
        echo "[setup] ERROR: $PY not found on PATH. Install Python 3.11 first." >&2
        echo "        (openWakeWord / onnxruntime / ctranslate2 / webrtcvad lack 3.13+ wheels.)" >&2
        exit 1
    fi

    if command -v uv >/dev/null 2>&1; then
        echo "[setup] creating venv with uv ($PY)..."
        uv venv --python "$PY" "$VENV"
    else
        echo "[setup] uv not found; creating venv with '$PY -m venv'..."
        "$PY" -m venv "$VENV"
    fi
fi

VENV_PY="$VENV/bin/python"

# --- 2. install requirements -----------------------------------------------
# pip is idempotent: already-satisfied requirements are skipped.
echo "[setup] installing requirements.txt..."
if command -v uv >/dev/null 2>&1; then
    uv pip install --python "$VENV_PY" -r "$ROOT/requirements.txt"
else
    "$VENV_PY" -m pip install --upgrade pip
    "$VENV_PY" -m pip install -r "$ROOT/requirements.txt"
fi

# --- 3. download openWakeWord assets ---------------------------------------
# Fetches the mandatory feature models (melspectrogram + embedding) and the
# pretrained wake models. Re-downloading is a no-op once files exist.
echo "[setup] downloading openWakeWord model assets..."
"$VENV_PY" -c "import openwakeword.utils; openwakeword.utils.download_models()"

# --- 4. next steps (manual / system-level) ---------------------------------
cat <<'EOF'

================================================================================
[setup] Python environment ready. Remaining MANUAL steps:
================================================================================

1) Anthropic API key
   Create a .env file at the repo root with your key:
       echo 'ANTHROPIC_API_KEY=sk-ant-...' > .env

2) Install Piper (TTS) — the binary must be on PATH as `piper`
   Prefer the rhasspy/piper release binary (NOT `pip install piper-tts`, which
   exposes it only as `python -m piper`). For example:
       mkdir -p ~/.local/bin
       # download the piper_linux_x86_64.tar.gz from
       #   https://github.com/rhasspy/piper/releases
       # extract it and put the `piper` binary on PATH, e.g.:
       #   tar -xzf piper_linux_x86_64.tar.gz -C ~/.local/share/piper-bin
       #   ln -sf ~/.local/share/piper-bin/piper/piper ~/.local/bin/piper
   Verify:  piper --help

3) Install a Piper voice model
   config.toml points at:
       ~/.local/share/piper/en_US-lessac-high.onnx
       ~/.local/share/piper/en_US-lessac-high.onnx.json
   Download both files (model + its .json config) from Hugging Face:
       mkdir -p ~/.local/share/piper
       cd ~/.local/share/piper
       # from https://huggingface.co/rhasspy/piper-voices (en/en_US/lessac/high)
       #   en_US-lessac-high.onnx   and   en_US-lessac-high.onnx.json
   The .json's audio.sample_rate is authoritative; tts.py reads it.

4) Audio player — ensure your configured player is installed
   config.toml [tts] player = "aplay" (alsa-utils) by default; "pw-play"
   (pipewire) is the alternative. Install whichever you set.

5) Hyprland window rules — make the overlay frameless/floating and positioned.
   Hyprland v0.53+ block syntax. With HyDE, add to
   ~/.config/hypr/windowrules.conf (the class must match
   [ui] window_class = "voice_assistant" in config.toml):
       windowrule {
           name = voice_assistant_config
           match:class = ^(voice_assistant)$
           float = true
           pin = true
           decorate = false
           move = (100%-520) 40
           size = 500 300
       }
   Then reload:  hyprctl reload
   (Set [ui] enabled = false in config.toml to run headless / no overlay.)

--------------------------------------------------------------------------------
Run it (from the repo root, so `execution` resolves as a package):
       .venv/bin/python -m execution.daemon

Test individual layers:
       .venv/bin/python -m execution.tts "hello there"
       .venv/bin/python -m execution.transcribe some.wav
       .venv/bin/python -m execution.config

Or install the systemd unit (voice-assistant.service) for autostart.
================================================================================
EOF

echo "[setup] done."
