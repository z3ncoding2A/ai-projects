#!/usr/bin/env python3
"""train_jarvis_wake_word.py — fully automated "Jarvis" wake word trainer.

Pipeline:
  1. Use Gemini TTS (gemini-3.1-flash-tts) to synthesise ~500 "Jarvis" clips
     across many voices and prompt styles.
  2. Use the hey_jarvis model's embeddings from the existing openWakeWord
     preprocessor to also pull ~500 negative-example embeddings.
  3. Train a tiny sklearn MLPClassifier on the positive/negative embeddings.
  4. Export to ONNX via skl2onnx.
  5. Drop the .onnx into the openWakeWord models directory.
  6. Update config.toml (wake.model = "jarvis").
  7. Restart the systemd service.

Run:
    cd ~/ai-projects/Jarvis-live-assistant
    .venv/bin/python train_jarvis_wake_word.py
"""

from __future__ import annotations

import base64
import io
import os
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

# ──────────────────────── paths & config ─────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent
VENV_PYTHON = REPO_ROOT / ".venv" / "bin" / "python"
CONFIG_TOML = REPO_ROOT / "config.toml"

import openwakeword
MODELS_DIR = Path(openwakeword.__file__).parent / "resources" / "models"
OUTPUT_ONNX = MODELS_DIR / "jarvis.onnx"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Diverse voices for positive samples (Gemini TTS prebuilt voices)
VOICES = [
    "Kore", "Puck", "Charon", "Fenrir", "Aoede",
    "Leda", "Orus", "Zephyr", "Autonoe", "Callirrhoe",
    "Despina", "Erinome", "Gacrux", "Isonoe", "Laomedeia",
    "Sulafat", "Umbriel",
]

# Prompt variations — instruct Gemini to say "Jarvis" in different styles
PROMPT_TEMPLATES = [
    'Say the word "Jarvis" naturally.',
    'Say "Jarvis" as if calling for an AI assistant.',
    'Say "Jarvis" confidently.',
    'Say "Jarvis" quietly.',
    'Say "Jarvis" from across the room.',
    'Say "Jarvis" with a slightly rising intonation.',
    'Say "Jarvis" as a command.',
    'Say "Jarvis" casually.',
    'Say "Jarvis" quickly.',
    'Say "Jarvis" slowly and clearly.',
]

# Negative phrases — common spoken words that should NOT trigger the detector
NEGATIVE_PHRASES = [
    "hello there", "open firefox", "what time is it", "play some music",
    "turn on the lights", "hey how are you", "good morning", "stop that",
    "that's a great idea", "can you help me", "send a message", "set a timer",
    "the weather looks good today", "close the window", "okay sure",
    "I need help with something", "what is the answer", "let me think",
    "one two three four five", "the quick brown fox", "yes no maybe",
    "navigate to home", "search for news", "show my calendar",
]


# ──────────────────────── helpers ────────────────────────────────────────────

def pcm16_to_wav_bytes(pcm_data: bytes, sample_rate: int = 24000) -> bytes:
    """Wrap raw PCM16 bytes in a minimal WAV header."""
    num_samples = len(pcm_data) // 2
    byte_rate = sample_rate * 1 * 2
    block_align = 2
    buf = io.BytesIO()
    buf.write(b"RIFF")
    buf.write(struct.pack("<I", 36 + len(pcm_data)))
    buf.write(b"WAVE")
    buf.write(b"fmt ")
    buf.write(struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, byte_rate, block_align, 16))
    buf.write(b"data")
    buf.write(struct.pack("<I", len(pcm_data)))
    buf.write(pcm_data)
    return buf.getvalue()


def wav_to_16k_mono_np(wav_bytes: bytes) -> np.ndarray:
    """Read WAV bytes → float32 numpy array at 16 kHz mono."""
    import soundfile as sf
    import librosa

    buf = io.BytesIO(wav_bytes)
    data, sr = sf.read(buf, dtype="float32", always_2d=False)
    if data.ndim > 1:
        data = data.mean(axis=1)
    if sr != 16000:
        data = librosa.resample(data, orig_sr=sr, target_sr=16000)
    return data


def get_embeddings_for_clip(preprocessor, audio_np: np.ndarray) -> np.ndarray | None:
    """Run audio through the openWakeWord feature extractor → embedding matrix.

    embed_clips requires:
      - 2D int16 array of shape (batch, samples)
    Returns shape (batch, n_windows, 96). We flatten to (n_windows, 96).
    """
    try:
        # Convert float32 → int16, ensure 2D batch shape
        if audio_np.dtype != np.int16:
            audio_int16 = (audio_np * 32767).clip(-32768, 32767).astype(np.int16)
        else:
            audio_int16 = audio_np
        batch = audio_int16.reshape(1, -1)  # (1, n_samples)
        result = preprocessor.embed_clips(batch, batch_size=1)  # (1, windows, 96)
        arr = np.array(result)  # (1, windows, 96)
        if arr.ndim == 3:
            arr = arr[0]        # → (windows, 96)
        elif arr.ndim == 1:
            arr = arr.reshape(1, -1)
        return arr if arr.shape[0] > 0 else None
    except Exception as e:
        print(f"  [warn] embed_clips failed: {e}")
        return None


# ──────────────────────── Gemini TTS synthesis ───────────────────────────────

def synthesise_gemini(prompt: str, voice: str, client) -> bytes | None:
    """Call Gemini TTS and return raw PCM16 bytes at 24 kHz, or None on error."""
    from google.genai import types
    try:
        response = client.models.generate_content(
            model="gemini-3.1-flash-tts-preview",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=voice
                        )
                    )
                ),
            ),
        )
        part = response.candidates[0].content.parts[0]
        if part.inline_data and part.inline_data.data:
            return part.inline_data.data
        return None
    except Exception as e:
        print(f"  [warn] Gemini TTS failed ({voice!r}, {prompt[:40]!r}): {e}")
        return None


def synthesise_piper(text: str, model_path: str, config_path: str) -> bytes | None:
    """Synthesise text with local Piper → raw PCM16 bytes at 22050 Hz."""
    try:
        result = subprocess.run(
            ["piper", "-m", model_path, "-c", config_path, "--output_raw", "-q"],
            input=text.encode(),
            capture_output=True,
            timeout=15,
        )
        if result.returncode == 0 and result.stdout:
            return result.stdout
        return None
    except Exception as e:
        print(f"  [warn] piper failed: {e}")
        return None


def piper_sample_rate(config_path: str) -> int:
    import json
    try:
        with open(config_path) as f:
            return int(json.load(f)["audio"]["sample_rate"])
    except Exception:
        return 22050


# ──────────────────────── main training pipeline ─────────────────────────────

def main() -> None:
    print("=" * 60)
    print("  Jarvis Wake Word Auto-Trainer")
    print("  Uses Gemini TTS + openWakeWord embeddings + sklearn")
    print("=" * 60)

    if not GEMINI_API_KEY:
        sys.exit("[error] GEMINI_API_KEY is not set. Export it or add it to .env")

    # ── imports ──────────────────────────────────────────────────────────────
    print("\n[1/6] Loading dependencies...")
    from google import genai
    from openwakeword.model import Model
    from sklearn.neural_network import MLPClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import Pipeline

    client = genai.Client(api_key=GEMINI_API_KEY)

    # Load the openWakeWord feature preprocessor (melspec + embedding model)
    oww = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
    preprocessor = oww.preprocessor
    print("  openWakeWord preprocessor ready.")

    # ── piper config ──────────────────────────────────────────────────────────
    # Read from config.toml
    import tomllib
    with open(CONFIG_TOML, "rb") as f:
        cfg = tomllib.load(f)
    tts_cfg = cfg.get("tts", {})
    piper_model = str(Path(tts_cfg.get("model_path", "")).expanduser())
    piper_config = str(Path(tts_cfg.get("config_path", "")).expanduser())
    use_piper = os.path.isfile(piper_model) and os.path.isfile(piper_config)
    if use_piper:
        piper_sr = piper_sample_rate(piper_config)
        print(f"  Piper TTS ready ({piper_model})")
    else:
        print("  [warn] Piper model not found; using Gemini TTS only")

    # ── positive samples: "Jarvis" ────────────────────────────────────────────
    print("\n[2/6] Synthesising positive samples ('Jarvis')...")
    pos_embeddings: list[np.ndarray] = []

    total_pos = 0
    for voice_idx, voice in enumerate(VOICES):
        for prompt in PROMPT_TEMPLATES:
            print(f"  Gemini TTS [{voice_idx+1}/{len(VOICES)}] voice={voice!r}", end="\r")
            pcm = synthesise_gemini(prompt, voice, client)
            if pcm:
                wav = pcm16_to_wav_bytes(pcm, 24000)
                audio = wav_to_16k_mono_np(wav)
                emb = get_embeddings_for_clip(preprocessor, audio)
                if emb is not None and emb.shape[0] > 0:
                    pos_embeddings.append(emb)
                    total_pos += emb.shape[0]
            time.sleep(0.05)  # light rate limiting

    # Supplement with Piper TTS for acoustic diversity
    if use_piper:
        piper_phrases = [
            "Jarvis", "Jarvis.", "Jarvis?",
            "Jarvis!", "Hey Jarvis", "Jarvis, wake up",
        ]
        for phrase in piper_phrases:
            pcm_raw = synthesise_piper(phrase, piper_model, piper_config)
            if pcm_raw:
                wav = pcm16_to_wav_bytes(pcm_raw, piper_sr)
                audio = wav_to_16k_mono_np(wav)
                emb = get_embeddings_for_clip(preprocessor, audio)
                if emb is not None and emb.shape[0] > 0:
                    pos_embeddings.append(emb)
                    total_pos += emb.shape[0]

    print(f"\n  Positive embedding windows: {total_pos}")
    if total_pos < 10:
        sys.exit("[error] Too few positive samples; check Gemini API connectivity")

    # ── negative samples ──────────────────────────────────────────────────────
    print("\n[3/6] Synthesising negative samples (other speech)...")
    neg_embeddings: list[np.ndarray] = []
    total_neg = 0

    neg_voices = VOICES[:8]  # subset is enough for negatives
    for neg_phrase in NEGATIVE_PHRASES:
        for voice in neg_voices[:4]:
            pcm = synthesise_gemini(f'Say: "{neg_phrase}"', voice, client)
            if pcm:
                wav = pcm16_to_wav_bytes(pcm, 24000)
                audio = wav_to_16k_mono_np(wav)
                emb = get_embeddings_for_clip(preprocessor, audio)
                if emb is not None and emb.shape[0] > 0:
                    neg_embeddings.append(emb)
                    total_neg += emb.shape[0]
            time.sleep(0.05)
        # Also piper negatives
        if use_piper:
            pcm_raw = synthesise_piper(neg_phrase, piper_model, piper_config)
            if pcm_raw:
                wav = pcm16_to_wav_bytes(pcm_raw, piper_sr)
                audio = wav_to_16k_mono_np(wav)
                emb = get_embeddings_for_clip(preprocessor, audio)
                if emb is not None and emb.shape[0] > 0:
                    neg_embeddings.append(emb)
                    total_neg += emb.shape[0]

    print(f"  Negative embedding windows: {total_neg}")

    # ── build dataset ──────────────────────────────────────────────────────────
    print("\n[4/6] Building training dataset...")
    X_pos = np.vstack(pos_embeddings)
    X_neg = np.vstack(neg_embeddings)
    y_pos = np.ones(len(X_pos))
    y_neg = np.zeros(len(X_neg))

    X = np.vstack([X_pos, X_neg])
    y = np.concatenate([y_pos, y_neg])

    # Shuffle
    rng = np.random.default_rng(42)
    idx = rng.permutation(len(X))
    X, y = X[idx], y[idx]
    print(f"  Dataset: {len(X)} windows ({len(X_pos)} pos / {len(X_neg)} neg)")

    # ── train classifier ──────────────────────────────────────────────────────
    print("\n[5/6] Training MLPClassifier...")
    clf = Pipeline([
        ("scaler", StandardScaler()),
        ("mlp", MLPClassifier(
            hidden_layer_sizes=(64, 32),
            activation="relu",
            max_iter=500,
            random_state=42,
            early_stopping=True,
            validation_fraction=0.15,
            n_iter_no_change=20,
            verbose=False,
        )),
    ])
    clf.fit(X, y)
    train_acc = clf.score(X, y)
    print(f"  Training accuracy: {train_acc:.3f}")

    # ── export to ONNX ─────────────────────────────────────────────────────────
    print(f"\n[6/6] Exporting to ONNX → {OUTPUT_ONNX}")
    try:
        from skl2onnx import convert_sklearn
        from skl2onnx.common.data_types import FloatTensorType
    except ImportError:
        print("  Installing skl2onnx...")
        subprocess.run(
            [str(VENV_PYTHON), "-m", "pip", "install", "skl2onnx", "-q"],
            check=True,
        )
        from skl2onnx import convert_sklearn
        from skl2onnx.common.data_types import FloatTensorType

    embedding_dim = X.shape[1]
    initial_type = [("float_input", FloatTensorType([None, embedding_dim]))]
    onnx_model = convert_sklearn(clf, initial_types=initial_type,
                                  target_opset=17)

    # openWakeWord expects the ONNX output to be a single probability score.
    # skl2onnx's MLP pipeline output has a "probabilities" output we can use.
    OUTPUT_ONNX.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_ONNX, "wb") as f:
        f.write(onnx_model.SerializeToString())
    print(f"  Saved: {OUTPUT_ONNX}")

    # ── update config.toml ────────────────────────────────────────────────────
    print("\n[✓] Updating config.toml: wake.model = 'jarvis'")
    config_text = CONFIG_TOML.read_text()
    import re
    config_text = re.sub(
        r'(^\s*model\s*=\s*")(?:hey_jarvis|jarvis)(".*?#.*?$)',
        r'\1jarvis\2',
        config_text,
        flags=re.MULTILINE,
    )
    # If the wake model line doesn't have a comment, handle plain case
    config_text = re.sub(
        r'(^\s*model\s*=\s*")(?:hey_jarvis|jarvis)(")',
        r'\1jarvis\2',
        config_text,
        flags=re.MULTILINE,
    )
    CONFIG_TOML.write_text(config_text)

    # ── restart service ───────────────────────────────────────────────────────
    print("\n[✓] Restarting voice-assistant service...")
    result = subprocess.run(
        ["systemctl", "--user", "restart", "voice-assistant"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        time.sleep(2)
        status = subprocess.run(
            ["systemctl", "--user", "is-active", "voice-assistant"],
            capture_output=True, text=True,
        )
        print(f"  Service status: {status.stdout.strip()}")
    else:
        print(f"  [warn] Restart failed: {result.stderr.strip()}")

    print("\n" + "=" * 60)
    print("  Done! Say 'Jarvis' to wake the assistant.")
    print(f"  Model: {OUTPUT_ONNX}")
    print("  Tune wake.threshold in config.toml if needed (default 0.5)")
    print("=" * 60)


if __name__ == "__main__":
    main()
