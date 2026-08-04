"""PyQt6 status overlay for the voice assistant.

A frameless, translucent, always-on-top, input-transparent widget that shows a
single pulsing indicator reflecting the pipeline state (listening / thinking /
speaking) and hides itself otherwise. Hyprland positions/sizes it via a
``windowrule`` matching ``class:^(voice_assistant)$``. That ``class`` is the
Wayland xdg-toplevel app_id (XWayland WM_CLASS), which Qt derives from the
application/desktop-file name — NOT from the window title or the Qt object
name. The daemon therefore sets ``QApplication.setDesktopFileName`` /
``setApplicationName`` to ``settings.ui_window_class`` so the rule matches. The
window title is still set below as a human-readable label, but it is not what
the compositor keys off.

THREADING: every method here mutates Qt widgets and therefore MUST run on the GUI
(main) thread. The daemon never calls ``apply_state`` directly from a worker — it
emits a ``pyqtSignal`` that Qt marshals onto the GUI thread for us.
"""

from __future__ import annotations

import logging
import math

from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QApplication, QWidget

from execution.config import Settings

logger = logging.getLogger(__name__)

# Valid pipeline states. Anything else is treated as "hidden".
_ACTIVE_STATES = ("listening", "thinking", "speaking")

# Indicator base color per state (R, G, B).
_STATE_COLORS = {
    "listening": (0x3D, 0xDC, 0x84),  # green  — mic open, waiting on you
    "thinking": (0xF5, 0xA6, 0x23),   # amber  — transcribing + LLM
    "speaking": (0x4F, 0x9C, 0xF5),   # blue   — TTS playing
}

# Pulse animation cadence. ~33 ms ≈ 30 FPS — smooth without burning CPU.
_PULSE_INTERVAL_MS = 33
# Full pulse cycle length in milliseconds (one breath in/out).
_PULSE_PERIOD_MS = 1400.0


class Overlay(QWidget):
    """Frameless on-screen status indicator driven by ``apply_state``."""

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self._settings = settings
        self._state = "hidden"
        # Monotonic-ish phase accumulator (ms) advanced by the pulse timer; used
        # to compute the breathing alpha/scale so the animation is continuous.
        self._phase_ms = 0.0

        # NOTE: the Hyprland-matched `class` (Wayland app_id / XWayland WM_CLASS)
        # comes from the application/desktop-file name, which the daemon sets via
        # QApplication.setDesktopFileName(settings.ui_window_class). Neither the
        # objectName nor the windowTitle below affects that match; they are kept
        # only as a human-readable identity/label.
        self.setObjectName(settings.ui_window_class)
        self.setWindowTitle(settings.ui_window_class)

        # Frameless + always-on-top + Tool (no taskbar entry / not focus-stealing).
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        # Transparent canvas so only what we paint is visible.
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        # Input-transparent: clicks/hover pass straight through to windows beneath.
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        # Show without grabbing focus so the user's active window keeps it.
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        self.resize(settings.ui_width, settings.ui_height)

        # Pulse timer drives repaints while a state is active. Single-thread: the
        # timer fires on the GUI event loop, same thread as paintEvent.
        self._timer = QTimer(self)
        self._timer.setInterval(_PULSE_INTERVAL_MS)
        self._timer.timeout.connect(self._on_tick)

    # -- public slot ------------------------------------------------------

    @pyqtSlot(str)
    def apply_state(self, state: str) -> None:
        """Update the overlay to ``state`` (GUI-thread only).

        ``state`` is one of {"listening","thinking","speaking","hidden"}. Active
        states show the widget and run the pulse animation; "hidden" (or any
        unknown value) stops the animation and hides the widget.
        """
        if state not in _ACTIVE_STATES and state != "hidden":
            logger.warning("Unknown overlay state %r; hiding", state)
            state = "hidden"

        self._state = state

        if state == "hidden":
            if self._timer.isActive():
                self._timer.stop()
            self.hide()
            return

        # Active state: (re)start the pulse and make sure we are visible.
        self._phase_ms = 0.0
        if not self._timer.isActive():
            self._timer.start()
        if not self.isVisible():
            self.show()
        # Force an immediate repaint so the color flips even mid-pulse.
        self.update()

    # -- internals --------------------------------------------------------

    def _on_tick(self) -> None:
        """Advance the pulse phase and request a repaint."""
        self._phase_ms = (self._phase_ms + _PULSE_INTERVAL_MS) % _PULSE_PERIOD_MS
        self.update()

    def _pulse_factor(self) -> float:
        """Return a smooth 0..1 breathing factor for the current phase."""
        # Sine eased into [0, 1]; peaks mid-cycle, troughs at the ends.
        return 0.5 * (1.0 - math.cos(2.0 * math.pi * self._phase_ms / _PULSE_PERIOD_MS))

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt override name)
        if self._state not in _ACTIVE_STATES:
            return

        r, g, b = _STATE_COLORS[self._state]
        pulse = self._pulse_factor()

        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

            cx = self.width() / 2.0
            cy = self.height() / 2.0
            # Base radius scales with the smaller dimension so it fits any size.
            base = min(self.width(), self.height()) * 0.18

            # Outer soft halo that grows/fades with the pulse.
            halo_radius = base * (1.4 + 0.6 * pulse)
            halo_alpha = int(40 + 70 * (1.0 - pulse))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(r, g, b, halo_alpha))
            painter.drawEllipse(
                int(cx - halo_radius),
                int(cy - halo_radius),
                int(halo_radius * 2),
                int(halo_radius * 2),
            )

            # Solid core that brightens with the pulse.
            core_alpha = int(160 + 95 * pulse)
            painter.setBrush(QColor(r, g, b, core_alpha))
            painter.drawEllipse(
                int(cx - base),
                int(cy - base),
                int(base * 2),
                int(base * 2),
            )
        finally:
            painter.end()


def create_overlay(settings: Settings) -> Overlay:
    """Construct and return an :class:`Overlay`.

    A ``QApplication`` must already exist on the calling (GUI) thread; the daemon
    owns its lifecycle. The overlay starts hidden until ``apply_state`` shows it.
    """
    overlay = Overlay(settings)
    overlay.apply_state("hidden")
    return overlay


if __name__ == "__main__":
    # Manual smoke test: cycle through states so you can eyeball the indicator.
    # Run from the repo root: python -m execution.ui_overlay
    import sys

    from execution.config import load_settings

    logging.basicConfig(level=logging.INFO)
    settings = load_settings()

    app = QApplication(sys.argv)
    overlay = create_overlay(settings)

    states = ["listening", "thinking", "speaking", "hidden"]
    index = {"i": 0}

    def _cycle() -> None:
        state = states[index["i"] % len(states)]
        print(f"-> {state}")
        overlay.apply_state(state)
        index["i"] += 1
        if index["i"] > len(states) * 2:
            app.quit()

    overlay.apply_state("listening")
    cycle_timer = QTimer()
    cycle_timer.timeout.connect(_cycle)
    cycle_timer.start(1500)

    sys.exit(app.exec())
