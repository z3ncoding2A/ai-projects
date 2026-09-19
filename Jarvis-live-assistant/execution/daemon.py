"""Daemon: integration owner for the sovereign Hyprland voice assistant.

Wires the wake listener and the Gemini Live API session into one runtime loop:

    wake word → overlay "listening" → Gemini Live API session
                 ├─ streams mic audio in real-time
                 ├─ receives + plays spoken Gemini responses
                 ├─ executes tool calls (e.g. launch_application)
                 └─ handles interruptions (user speaks → kills player)
    → overlay hides → re-arm.

The Gemini Live API session (``run_live_session``) replaces the previous
record → transcribe → Claude → Piper pipeline.  STT, LLM, and TTS are all
handled inside the single WebSocket session.

Threading model (the daemon owns it):
  - PyQt6's QApplication event loop runs on the MAIN thread.
  - The wake-word listener runs in its own thread (inside WakeWordListener).
  - Each wake detection spawns the pipeline on a worker thread so the GUI stays
    responsive. A non-blocking lock guarantees only one pipeline runs at a time.
  - Off-GUI-thread state updates go through StateBridge's pyqtSignal, which Qt
    auto-queues onto the GUI thread, so the widget is only ever mutated on the
    main thread.
  - Headless (ui disabled or no display): no QApplication, set_state is a no-op,
    and the process blocks forever on a threading.Event.

Run from the repo root:  python -m execution.daemon
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading

from execution.config import load_settings, configure_logging
from execution.llm_router import run_live_session
from execution.wake_word import WakeWordListener

logger = logging.getLogger(__name__)


def main() -> None:
    """Build every component, start the wake listener, and run the event loop."""
    # 1. Config + logging first so component constructors' logs are visible.
    settings = load_settings()
    configure_logging(settings)
    logger.info("Voice assistant starting up (Gemini Live API)")

    # 2. Decide GUI vs headless. A display must actually be present even when the
    #    config enables the UI (e.g. running under systemd without a session).
    has_display = bool(os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY"))
    gui = settings.ui_enabled and has_display

    app = None
    if gui:
        # Defer the PyQt6 import into this branch so headless mode never loads Qt.
        from PyQt6.QtCore import QObject, pyqtSignal
        from PyQt6.QtWidgets import QApplication
        from execution.ui_overlay import create_overlay

        class StateBridge(QObject):
            """Thread-safe conduit to the overlay.

            The signal is emitted from the worker thread; Qt queues the slot call
            onto the GUI thread that owns the overlay, so the widget is only ever
            mutated on the main thread.
            """

            # Must be a class attribute (pyqtSignal cannot be created in __init__).
            state_changed = pyqtSignal(str)

        # QApplication must exist before any QWidget (the overlay is a QWidget).
        app = QApplication([])
        # Hyprland matches windows on the Wayland xdg-toplevel app_id (and the
        # XWayland WM_CLASS). Qt derives both from the application/desktop-file
        # name, NOT from the window title or Qt objectName, so we must set it
        # here for the `class:^(voice_assistant)$` windowrule to match. Set both
        # the desktop file name (app_id source) and application name to be safe.
        app.setApplicationName(settings.ui_window_class)
        QApplication.setDesktopFileName(settings.ui_window_class)
        overlay = create_overlay(settings)
        bridge = StateBridge()
        bridge.state_changed.connect(overlay.apply_state)

        def set_state(s: str) -> None:
            bridge.state_changed.emit(s)

        logger.info("UI overlay enabled (display detected)")
    else:
        def set_state(s: str) -> None:
            pass

        if settings.ui_enabled and not has_display:
            logger.warning("UI enabled in config but no display found; running headless")
        else:
            logger.info("Running headless (UI disabled)")

    # Non-blocking guard: only one pipeline iteration may run at a time. A stuck
    # or slow pipeline simply causes later wake detections to be dropped rather
    # than queued, which matches the "one at a time" contract.
    pipeline_lock = threading.Lock()

    def pipeline() -> None:
        """Run one full wake → Gemini Live session cycle.

        Runs on a worker thread. Calls asyncio.run() to execute the
        async Gemini Live session (mic streaming + audio playback + tools).
        The outer try/finally guarantees the wake listener is re-armed and
        the overlay is hidden on every exit path — success, error, or
        KeyboardInterrupt — so the daemon never wedges.
        """
        # Drop the detection if a pipeline is already running.
        if not pipeline_lock.acquire(blocking=False):
            logger.debug("Pipeline already running; ignoring wake detection")
            return
        try:
            try:
                # run_live_session manages the full session lifecycle, including
                # state transitions (listening / speaking / hidden) via set_state.
                asyncio.run(run_live_session(settings, set_state))
            except Exception:
                # An error in one iteration must never crash the daemon.
                logger.exception("Pipeline iteration failed; re-arming")
            finally:
                # Ensure overlay hides and mic is re-armed regardless of outcome.
                set_state("hidden")
                listener.resume()
        finally:
            pipeline_lock.release()

    def on_detected(name: str) -> None:
        """Wake-word callback: pause the listener and launch the pipeline."""
        logger.info("Wake word detected: %s", name)
        # Pause the wake listener (releases mic) before the session opens its own
        # mic stream. The pipeline's finally block calls listener.resume().
        listener.pause()
        # daemon=True so a stuck pipeline never blocks process exit.
        threading.Thread(target=pipeline, name="pipeline", daemon=True).start()

    # Start listening and hand control to the appropriate loop.
    listener = WakeWordListener(settings, on_detected)
    listener.start()
    logger.info("Wake-word listener started; waiting for activation")

    try:
        if gui:
            assert app is not None
            app.exec()
        else:
            # Block the main thread forever; all work happens on other threads.
            threading.Event().wait()
    except KeyboardInterrupt:
        logger.info("Interrupted; shutting down")
    finally:
        listener.stop()
        logger.info("Voice assistant stopped")


if __name__ == "__main__":
    main()
