"""Wake-word listener for the Hyprland voice assistant.

Opens a 16 kHz mono int16 microphone stream and feeds frames to an
openWakeWord model. When any model's score crosses ``settings.wake_threshold``
the supplied ``on_detected`` callback fires (debounced). The listener owns its
own daemon thread and the lifecycle of the ``sounddevice`` stream so that
``pause()`` can fully release the microphone for the recorder, and ``resume()``
can reopen it.

Verified against the installed openWakeWord:
  - ``openwakeword.model.Model(wakeword_models=[...], vad_threshold=...,
    inference_framework="onnx")`` is the real constructor (introspected through
    the ``@re_arg`` decorator wrapper).
  - ``Model.predict(int16_ndarray) -> {model_name: score}``.
  - ``openwakeword.utils.download_models()`` always fetches the mandatory
    feature models (melspectrogram + embedding); pretrained names like
    ``"hey_jarvis"`` map to files such as ``hey_jarvis_v0.1.onnx``.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Callable

import numpy as np
import sounddevice as sd

import openwakeword
from openwakeword.model import Model
from openwakeword.utils import download_models

from execution.config import Settings

logger = logging.getLogger(__name__)

# How long (seconds) to ignore further detections after one fires, so a single
# utterance of the wake word does not retrigger the pipeline repeatedly.
_DEBOUNCE_SECONDS = 2.0


def _models_dir() -> str:
    """Absolute path of openWakeWord's bundled ``resources/models`` directory."""
    return os.path.join(os.path.dirname(openwakeword.__file__), "resources", "models")


def _ensure_models(settings: Settings) -> None:
    """Download openWakeWord assets once if they are not already present.

    Always ensures the mandatory feature models (melspectrogram + embedding)
    and the selected pretrained wake model. If the built-in VAD gate is enabled
    (``wake_vad_threshold > 0``) the Silero VAD model is needed too.

    A custom ``.onnx`` path in ``settings.wake_model`` is used as-is and only
    the feature/VAD models are fetched.
    """
    models_dir = _models_dir()

    # Required files that must exist on disk before Model() can construct.
    required: list[str] = []
    for fm in openwakeword.FEATURE_MODELS.values():
        required.append(fm["download_url"].split("/")[-1])
    if settings.wake_vad_threshold and settings.wake_vad_threshold > 0:
        for vm in openwakeword.VAD_MODELS.values():
            required.append(vm["download_url"].split("/")[-1])

    is_path = settings.wake_model.endswith(".onnx") or os.path.sep in settings.wake_model
    if not is_path and settings.wake_model in openwakeword.MODELS:
        required.append(
            openwakeword.MODELS[settings.wake_model]["download_url"].split("/")[-1]
        )

    # download_url entries point at .tflite files, but with the ONNX framework the
    # Model loads the .onnx variants. Check for the files that are actually loaded
    # so a partial (.tflite-only) install still triggers the .onnx download.
    if settings.wake_inference_framework == "onnx":
        required = [f[:-7] + ".onnx" if f.endswith(".tflite") else f for f in required]

    missing = [f for f in required if not os.path.exists(os.path.join(models_dir, f))]
    if missing:
        logger.info("Downloading openWakeWord models (missing: %s)", missing)
        # download_models() with no names fetches feature + all pretrained +
        # VAD models, which is the safe superset and idempotent.
        download_models()
        logger.info("openWakeWord models ready in %s", models_dir)


class WakeWordListener:
    """Background wake-word detector.

    Spawns a daemon thread that streams audio into an openWakeWord model and
    invokes ``on_detected(model_name)`` once per detection (then debounces).
    The thread owns the audio stream; ``pause()``/``resume()`` coordinate with
    it via events so the microphone is cleanly released and reacquired without
    cross-thread stream closes.
    """

    def __init__(self, settings: Settings, on_detected: Callable[[str], None]) -> None:
        self._settings = settings
        self._on_detected = on_detected

        self._model: Model | None = None  # constructed inside the worker thread
        self._thread: threading.Thread | None = None

        # Lifecycle / coordination events.
        self._stop = threading.Event()          # request full shutdown
        self._pause_requested = threading.Event()  # daemon asks to free the mic
        self._paused_ack = threading.Event()    # worker confirms mic is closed
        self._resume = threading.Event()        # daemon asks to re-arm

        self._last_fire = 0.0  # monotonic time of the last detection

    # -- public API -------------------------------------------------------

    def start(self) -> None:
        """Start the background listening thread (idempotent)."""
        if self._thread is not None and self._thread.is_alive():
            logger.debug("WakeWordListener already running")
            return
        self._stop.clear()
        self._pause_requested.clear()
        self._paused_ack.clear()
        self._resume.clear()
        self._thread = threading.Thread(
            target=self._run, name="wake-word-listener", daemon=True
        )
        self._thread.start()
        logger.info("WakeWordListener started (model=%s)", self._settings.wake_model)

    def stop(self) -> None:
        """Stop the listener and join its thread."""
        self._stop.set()
        # Unblock the worker if it is parked in the paused state.
        self._resume.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=5.0)
            if thread.is_alive():
                logger.warning("WakeWordListener thread did not exit cleanly")
        self._thread = None
        logger.info("WakeWordListener stopped")

    def pause(self) -> None:
        """Release the microphone and block until it is confirmed closed.

        Synchronous handshake: the worker thread finishes its current short
        read, closes the stream, and acks. Only then does this return, so the
        caller (the recorder) can open the mic without racing.
        """
        if self._thread is None or not self._thread.is_alive():
            return
        if self._pause_requested.is_set():
            return  # already paused / pausing
        self._paused_ack.clear()
        self._resume.clear()
        self._pause_requested.set()
        # Wait for the worker to actually close the stream.
        if not self._paused_ack.wait(timeout=5.0):
            logger.warning("WakeWordListener.pause() timed out waiting for mic release")
        else:
            logger.debug("WakeWordListener paused (mic released)")

    def resume(self) -> None:
        """Re-arm the listener after a pause (reopens the stream)."""
        if self._thread is None or not self._thread.is_alive():
            return
        if not self._pause_requested.is_set():
            return  # not paused
        self._pause_requested.clear()
        self._paused_ack.clear()
        self._resume.set()
        logger.debug("WakeWordListener resume requested")

    # -- worker thread ----------------------------------------------------

    def _run(self) -> None:
        """Thread body: ensure models, then loop over open/listen/pause."""
        try:
            _ensure_models(self._settings)
            self._model = Model(
                wakeword_models=[self._settings.wake_model],
                vad_threshold=self._settings.wake_vad_threshold,
                inference_framework=self._settings.wake_inference_framework,
            )
        except Exception:
            logger.exception("Failed to initialize openWakeWord model; listener stopping")
            return

        while not self._stop.is_set():
            try:
                self._listen_loop()
            except Exception:
                logger.exception("Wake-word listen loop crashed; retrying shortly")
                time.sleep(0.5)
                continue

            # We exited the listen loop because a pause was requested (and the
            # stream is now closed). Park here until resume or stop.
            if self._stop.is_set():
                break
            self._resume.wait()
            self._resume.clear()

    def _listen_loop(self) -> None:
        """Open the stream and feed frames until stop or pause is requested."""
        device = self._settings.input_device or None  # "" => default device
        # int16 mono stream; read() returns (ndarray[frames, 1], overflowed).
        stream = sd.InputStream(
            samplerate=self._settings.sample_rate,
            blocksize=self._settings.frame_size,
            device=device,
            channels=1,
            dtype="int16",
        )
        stream.start()
        logger.debug("Wake stream opened (rate=%d, block=%d)",
                     self._settings.sample_rate, self._settings.frame_size)
        try:
            while not self._stop.is_set() and not self._pause_requested.is_set():
                frame, overflowed = stream.read(self._settings.frame_size)
                if overflowed:
                    logger.debug("Wake input overflow")
                # predict() wants a 1-D int16 array.
                scores = self._model.predict(frame[:, 0])
                self._evaluate(scores)
        finally:
            # The worker thread that opened the stream is the one closing it —
            # no cross-thread close race.
            stream.stop()
            stream.close()
            logger.debug("Wake stream closed")
            if self._pause_requested.is_set():
                # Confirm the mic is free for the recorder.
                self._paused_ack.set()

    def _evaluate(self, scores: dict[str, float]) -> None:
        """Fire ``on_detected`` for the top-scoring model above threshold."""
        if not scores:
            return
        best_model = max(scores, key=scores.get)
        best_score = scores[best_model]
        if best_score < self._settings.wake_threshold:
            return

        now = time.monotonic()
        if now - self._last_fire < _DEBOUNCE_SECONDS:
            return  # still inside the refractory window
        self._last_fire = now

        # Clear internal prediction buffers so buffered frames from this same
        # utterance don't immediately retrigger after the cooldown.
        try:
            self._model.reset()
        except Exception:
            logger.debug("Model.reset() unavailable; relying on time debounce")

        logger.info("Wake word detected: %s (score=%.3f)", best_model, best_score)
        # Dispatch the callback on a separate short-lived thread rather than
        # invoking it on this worker thread. In headless mode on_detected runs
        # the pipeline directly, and the pipeline calls listener.pause(), which
        # blocks until this worker reaches the finally that closes the stream
        # and sets _paused_ack. If on_detected ran here, the worker would be
        # blocked inside pause() and could never reach that finally -> deadlock
        # until the 5s timeout, leaving the wake stream open during recording.
        threading.Thread(
            target=self._dispatch_detected,
            args=(best_model,),
            name="wake-on-detected",
            daemon=True,
        ).start()

    def _dispatch_detected(self, model_name: str) -> None:
        """Invoke the user callback off the listener worker thread."""
        try:
            self._on_detected(model_name)
        except Exception:
            logger.exception("on_detected callback raised")


if __name__ == "__main__":
    # Standalone smoke test: python -m execution.wake_word
    from execution.config import configure_logging, load_settings

    _settings = load_settings()
    configure_logging(_settings)

    _detected = threading.Event()

    def _cb(name: str) -> None:
        print(f"[wake] detected: {name}")
        _detected.set()

    _listener = WakeWordListener(_settings, _cb)
    _listener.start()
    print("Listening for wake word... (Ctrl+C to quit)")
    try:
        while True:
            if _detected.wait(timeout=1.0):
                _detected.clear()
                # Exercise the pause/resume handshake the daemon relies on.
                print("[wake] pausing (releasing mic)...")
                _listener.pause()
                time.sleep(1.0)
                print("[wake] resuming...")
                _listener.resume()
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        _listener.stop()
