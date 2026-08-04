"""Local speech-to-text via faster-whisper.

Wraps faster_whisper.WhisperModel with lazy construction and a CUDA->CPU
fallback. Audio in is the project convention: mono float32, 16 kHz, range [-1, 1].
"""

from __future__ import annotations

import logging
import sys

import numpy as np

from execution.config import Settings, load_settings

logger = logging.getLogger(__name__)


class Transcriber:
    """Holds a faster-whisper model, built lazily on first transcribe()."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        # Built on first use so daemon startup stays cheap and a GPU init
        # failure surfaces at transcription time (where we can fall back).
        self._model = None

    def _ensure_model(self):
        """Construct the WhisperModel once, falling back to CPU/int8 on failure."""
        if self._model is not None:
            return self._model

        s = self._settings
        # Import here so simply importing this module doesn't pull in the heavy
        # ctranslate2 backend.
        from faster_whisper import WhisperModel

        try:
            self._model = WhisperModel(
                s.whisper_model,
                device=s.whisper_device,
                compute_type=s.whisper_compute_type,
            )
            logger.info(
                "Loaded whisper model '%s' on device=%s compute_type=%s",
                s.whisper_model,
                s.whisper_device,
                s.whisper_compute_type,
            )
        except Exception:
            # Typical cause: no CUDA / missing cuDNN. Fall back to CPU int8.
            logger.warning(
                "Failed to init whisper on device=%s (compute_type=%s); "
                "falling back to device=cpu, compute_type=int8",
                s.whisper_device,
                s.whisper_compute_type,
                exc_info=True,
            )
            self._model = WhisperModel(
                s.whisper_model,
                device="cpu",
                compute_type="int8",
            )
            logger.info("Loaded whisper model '%s' on CPU (int8)", s.whisper_model)

        return self._model

    def _force_cpu_fallback(self) -> None:
        """Rebuild the model on CPU/int8, discarding any GPU model."""
        from faster_whisper import WhisperModel

        self._model = None
        self._model = WhisperModel(
            self._settings.whisper_model,
            device="cpu",
            compute_type="int8",
        )
        logger.info(
            "Rebuilt whisper model '%s' on CPU (int8) after inference-time GPU failure",
            self._settings.whisper_model,
        )

    def transcribe(self, audio: "np.ndarray") -> str:
        """Transcribe a mono float32 16 kHz buffer; return the stripped text."""
        if audio is None or len(audio) == 0:
            return ""

        model = self._ensure_model()
        s = self._settings

        # faster-whisper wants a contiguous float32 1-D array.
        audio = np.ascontiguousarray(audio, dtype=np.float32)

        try:
            segments, _info = model.transcribe(
                audio,
                vad_filter=True,
                beam_size=s.whisper_beam_size,
                language=s.whisper_language,
            )
            # Generator does actual decoding here — CUDA errors surface during iteration.
            text = "".join(segment.text for segment in segments)
        except RuntimeError as exc:
            if "libcublas" in str(exc) or "cuda" in str(exc).lower():
                logger.warning(
                    "GPU inference failed (%s); falling back to CPU and retrying", exc
                )
                self._force_cpu_fallback()
                segments, _info = self._model.transcribe(
                    audio,
                    vad_filter=True,
                    beam_size=s.whisper_beam_size,
                    language=s.whisper_language,
                )
                text = "".join(segment.text for segment in segments)
            else:
                raise

        return text.strip()


def _load_wav(path: str) -> "np.ndarray":
    """Load a WAV file as mono float32 16 kHz in [-1, 1] for the CLI.

    Uses soundfile if available, otherwise the stdlib wave module + numpy.
    """
    try:
        import soundfile as sf  # type: ignore

        data, sr = sf.read(path, dtype="float32", always_2d=True)
        data = data.mean(axis=1)  # mix down to mono
    except ImportError:
        import wave

        with wave.open(path, "rb") as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            sr = wf.getframerate()
            raw = wf.readframes(wf.getnframes())

        if sampwidth != 2:
            raise ValueError(
                f"Only 16-bit PCM WAV supported in CLI fallback (got {sampwidth * 8}-bit)"
            )
        ints = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        if n_channels > 1:
            ints = ints.reshape(-1, n_channels).mean(axis=1)
        data = ints

    if sr != 16000:
        logger.warning(
            "WAV sample rate is %d Hz, expected 16000; transcription may be poor", sr
        )
    return np.ascontiguousarray(data, dtype=np.float32)


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: python -m execution.transcribe <file.wav>", file=sys.stderr)
        raise SystemExit(2)

    settings = load_settings()
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))

    audio = _load_wav(sys.argv[1])
    transcriber = Transcriber(settings)
    print(transcriber.transcribe(audio))


if __name__ == "__main__":
    main()
