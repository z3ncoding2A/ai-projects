"""Record an utterance from the microphone, stopping on silence.

`record_until_silence` opens a 16 kHz mono float32 sounddevice InputStream, reads it
in fixed 30 ms (480-sample) blocks, and uses webrtcvad to decide speech vs. silence on
each block. It waits up to `start_grace_ms` for speech to begin, then keeps capturing
until either `silence_ms` of continuous non-speech or the `max_record_ms` hard cap is
reached. The captured float32 buffer is returned mono @ 16 kHz, range [-1, 1]. Anything
shorter than `min_speech_ms`, or never-started, comes back as an empty array.

The 480-sample VAD block here is independent of the wake listener's `frame_size`.
"""

from __future__ import annotations

import logging
from typing import Callable

import numpy as np
import sounddevice as sd
import webrtcvad

from execution.config import Settings

logger = logging.getLogger(__name__)

# webrtcvad accepts only 10/20/30 ms frames; we use 30 ms.
_FRAME_MS = 30
_SAMPLE_RATE = 16000  # webrtcvad supports 8/16/32/48 kHz; the pipeline is locked to 16 kHz.
_BLOCK_SAMPLES = (_SAMPLE_RATE * _FRAME_MS) // 1000  # 480 samples @ 16 kHz


def record_until_silence(
    settings: Settings,
    on_level: Callable[[float], None] | None = None,
) -> np.ndarray:
    """Capture one spoken utterance, returning float32 mono 16 kHz audio.

    Args:
        settings: loaded Settings; uses recorder_* fields and input_device.
        on_level: optional callback receiving per-block RMS (for UI metering).

    Returns:
        A 1-D float32 ndarray (range [-1, 1]) of the captured speech, or an empty
        float32 array if speech never started or the utterance was too short.
    """
    vad = webrtcvad.Vad(settings.recorder_vad_aggressiveness)

    # "" in config means "system default device"; sounddevice wants None for that.
    device = settings.input_device or None

    # Derive block-count thresholds from the millisecond config knobs.
    silence_blocks = max(1, settings.silence_ms // _FRAME_MS)
    grace_blocks = max(1, settings.start_grace_ms // _FRAME_MS)
    max_blocks = max(1, settings.max_record_ms // _FRAME_MS)

    captured: list[np.ndarray] = []  # float32 blocks of detected/ongoing speech
    started = False                  # have we heard the first speech yet?
    silence_run = 0                  # consecutive non-speech blocks since speech start
    grace_run = 0                    # consecutive blocks waited before speech started
    total_blocks = 0                 # total blocks read since capture began
    speech_blocks = 0                # blocks flagged as speech (for min_speech_ms gate)

    empty = np.empty(0, dtype=np.float32)

    try:
        stream = sd.InputStream(
            samplerate=_SAMPLE_RATE,
            blocksize=_BLOCK_SAMPLES,
            device=device,
            channels=1,
            dtype="float32",
        )
    except Exception:
        logger.exception("Failed to open input stream for recording")
        return empty

    with stream:
        while True:
            data, overflowed = stream.read(_BLOCK_SAMPLES)
            if overflowed:
                logger.warning("Input overflow during recording (audio dropped)")

            # InputStream returns shape (frames, channels); flatten to mono 1-D.
            block = np.asarray(data, dtype=np.float32).reshape(-1)

            # Report RMS level for any UI meter (guard against empty/NaN).
            if on_level is not None:
                rms = float(np.sqrt(np.mean(np.square(block)))) if block.size else 0.0
                on_level(rms)

            # webrtcvad needs 16-bit PCM bytes; clip then scale float32 [-1,1] -> int16.
            pcm16 = np.clip(block, -1.0, 1.0)
            pcm16 = (pcm16 * 32767.0).astype(np.int16)
            is_speech = vad.is_speech(pcm16.tobytes(), _SAMPLE_RATE)

            if not started:
                grace_run += 1
                if is_speech:
                    # First speech: begin capturing from this block.
                    started = True
                    silence_run = 0
                    total_blocks = 0
                    speech_blocks = 1
                    captured.append(block)
                elif grace_run >= grace_blocks:
                    # No speech arrived within the grace window: give up.
                    logger.debug("No speech within start grace window; aborting capture")
                    return empty
                continue

            # Already capturing: keep every block so trailing/leading edges aren't clipped.
            captured.append(block)
            total_blocks += 1

            if is_speech:
                silence_run = 0
                speech_blocks += 1
            else:
                silence_run += 1
                if silence_run >= silence_blocks:
                    logger.debug("Silence threshold reached; stopping capture")
                    break

            if total_blocks >= max_blocks:
                logger.debug("Max record length reached; stopping capture")
                break

    if not captured:
        return empty

    audio = np.concatenate(captured).astype(np.float32)

    # Discard if the actual *speech* (not the buffer, which includes trailing silence)
    # is shorter than the configured minimum — filters coughs/blips/false triggers.
    speech_ms = speech_blocks * _FRAME_MS
    if speech_ms < settings.min_speech_ms:
        logger.debug(
            "Captured speech too short (%d ms < %d ms); discarding",
            speech_ms,
            settings.min_speech_ms,
        )
        return empty

    buffer_ms = (audio.size / _SAMPLE_RATE) * 1000.0
    logger.info(
        "Captured %.0f ms buffer (%d ms speech, %d samples)",
        buffer_ms,
        speech_ms,
        audio.size,
    )
    return audio


if __name__ == "__main__":
    # Standalone smoke test: record one utterance and report its length.
    import sys

    from execution.config import configure_logging, load_settings

    _settings = load_settings()
    configure_logging(_settings)

    print("Speak now... (recording until silence)", file=sys.stderr)
    _audio = record_until_silence(_settings, on_level=None)
    if _audio.size == 0:
        print("No usable speech captured.", file=sys.stderr)
    else:
        _ms = (_audio.size / _SAMPLE_RATE) * 1000.0
        print(f"Captured {_audio.size} samples ({_ms:.0f} ms).", file=sys.stderr)
