# ui/splash.py
#
# Stage: Responsive Splash Screen (v1.5).
# CryptixSplash  - painted renderer: milestone rows, progress, pulsing shield,
#                  converging final message, critical-failure state, fade-out.
# startup_steps  - the REAL milestone registry (critical/recoverable classes).
# run_startup_sequence - chains steps via QTimer.singleShot(0): zero fake delay.
#
# Principles (spec):
#   - timing comes from real startup work, never artificial delays
#   - recoverable failure  -> red check, continue with fallback
#   - critical failure     -> "Startup aborted safely", clear error, exit
#   - the window always wins the hand-over

import math
import os
import sys

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget

BG = QColor("#0B0F19")
ACCENT = QColor("#00F0FF")
DONE = QColor("#00FF66")
ERROR = QColor("#FF3B3B")
DIM = QColor("#6B7A90")
TEXT = QColor("#E2E8F0")

FINAL_MESSAGE = "Initializing Secure Modules..."

CRITICAL = "critical"
RECOVERABLE = "recoverable"


class CryptixSplash(QWidget):
    """Painted splash surface. A pure renderer: it displays state it is
    given and knows nothing about what the startup steps do."""

    finished = Signal()  # emitted when the fade-out hand-over begins

    def __init__(self, labels):
        super().__init__(None,
                         Qt.WindowType.SplashScreen
                         | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.FramelessWindowHint)
        self._labels = list(labels)
        self._states = ["pending"] * len(self._labels)
        self._final_phase = False
        self._failure = None  # (step_label, message)
        self._phase = 0.0
        # Height derives from the row count so the final message (and the
        # failure detail line) ALWAYS fit inside the window with margin:
        # rows start at y=216, each row is 26px, the closing message needs
        # ~64px below the last row. (A fixed 400px clipped it before.)
        self.setFixedSize(480, max(360, 216 + 26 * len(self._labels) + 64))
        self.setWindowTitle("Cryptix Core")

        self._pulse = QTimer(self)
        self._pulse.setInterval(50)
        self._pulse.timeout.connect(self._tick_pulse)
        self._pulse.start()

    # ---------------- state API (used by the runner) ----------------

    def set_current(self, index):
        self._states[index] = "current"
        self.update()

    def mark_done(self, index, ok=True):
        self._states[index] = "done" if ok else "error"
        self.update()

    def show_final_message(self):
        self._final_phase = True
        self.update()

    def show_failure(self, step_label, message):
        self._failure = (step_label, message)
        self.update()

    # ---------------- test accessors ----------------

    def row_states(self):
        return list(self._states)

    def progress(self):
        done = sum(1 for s in self._states if s in ("done", "error"))
        return done / max(1, len(self._states))

    def is_final_message_visible(self):
        return self._final_phase

    def failure(self):
        return self._failure

    # ---------------- hand-over ----------------

    def begin_handover(self, fade_ms=300):
        """Fade the splash out and close it. The main window always wins."""
        self.finished.emit()
        state = {"i": 0}
        steps = 10
        timer = QTimer(self)
        timer.setInterval(int(fade_ms / steps))

        def tick():
            state["i"] += 1
            try:
                self.setWindowOpacity(1.0 - state["i"] / steps)
            except RuntimeError:
                timer.stop()
                return
            if state["i"] >= steps:
                timer.stop()
                self.close()

        timer.timeout.connect(tick)
        timer.start()
        self._handover_timer = timer  # keep alive

    # ---------------- painting ----------------

    def _tick_pulse(self):
        self._phase += 0.12
        self.update()

    def _shield_pixmap(self):
        base = getattr(sys, "frozen", False) and getattr(sys, "_MEIPASS") or os.path.abspath(".")
        icon = QIcon(os.path.join(base, "cryptix.ico"))
        return icon.pixmap(64, 64)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()

        p.fillRect(self.rect(), BG)

        cx = w / 2
        shield_y = 78

        # breathing radial glow + shield
        glow_r = 58 + 10 * (0.5 + 0.5 * math.sin(self._phase))
        grad = QRadialGradient(cx, shield_y, glow_r)
        pulse_alpha = 70 + 50 * (0.5 + 0.5 * math.sin(self._phase))
        grad.setColorAt(0.0, QColor(0, 240, 255, pulse_alpha))
        grad.setColorAt(1.0, QColor(0, 240, 255, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(grad)
        p.drawEllipse(int(cx - glow_r), int(shield_y - glow_r), int(glow_r * 2), int(glow_r * 2))

        pix = self._shield_pixmap()
        if not pix.isNull():
            p.drawPixmap(int(cx - 32), int(shield_y - 32), 64, 64, pix)

        # title
        title_font = QFont("Segoe UI", 18, QFont.Weight.Bold)
        title_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 3)
        p.setFont(title_font)
        p.setPen(ACCENT)
        p.drawText(self.rect().adjusted(0, 140, 0, 0), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                   "CRYPTIX CORE")

        # progress bar
        total = max(1, len(self._labels))
        done = sum(1 for s in self._states if s in ("done", "error"))
        bar_w, bar_x, bar_y = 300, int(cx - 150), 186
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#131822"))
        p.drawRoundedRect(bar_x, bar_y, bar_w, 6, 3, 3)
        if done:
            p.setBrush(ACCENT if not self._failure else ERROR)
            p.drawRoundedRect(bar_x, bar_y, int(bar_w * done / total), 6, 3, 3)

        # milestone rows
        row_font = QFont("Consolas", 10)
        p.setFont(row_font)
        row_x, row_y0, row_h = 96, 216, 26
        final_y = row_y0 + row_h * total + 26
        for i, label in enumerate(self._labels):
            y = row_y0 + i * row_h
            state = self._states[i]
            if state == "done":
                glyph, color = "✓", DONE
            elif state == "error":
                glyph, color = "✗", ERROR
            elif state == "current":
                glyph, color = "⟳", ACCENT
            else:
                glyph, color = "·", DIM
            if self._failure and state == "error":
                color = ERROR
            elif state == "done":
                color = QColor("#7FCF9F")  # muted green for text
            p.setPen(color)
            p.drawText(row_x, y, 400, 20, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       f"{glyph}  {label}")

        # convergence + final message
        if self._failure:
            step, msg = self._failure
            p.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
            p.setPen(ERROR)
            p.drawText(self.rect().adjusted(10, final_y - 6, -10, 0),
                       Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                       "Startup aborted safely")
            p.setFont(QFont("Consolas", 8))
            p.setPen(QColor("#FFB4B4"))
            elided = msg if len(msg) <= 64 else msg[:61] + "..."
            p.drawText(self.rect().adjusted(10, final_y + 14, -10, 0),
                       Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                       f"✗ {step}: {elided}")
        elif self._final_phase:
            pen = QPen(QColor(0, 240, 255, 60))
            pen.setWidth(1)
            p.setPen(pen)
            for i in range(total):
                y = row_y0 + i * row_h + 10
                p.drawLine(int(row_x + 240), y, int(cx + 60), final_y + 4)
            p.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
            p.setPen(ACCENT)
            p.drawText(self.rect().adjusted(10, final_y - 6, -10, 0),
                       Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                       FINAL_MESSAGE)
        p.end()


# =========================================================
# THE REAL MILESTONES
# =========================================================

def startup_steps(initial_file=None, window_holder=None):
    """Returns [(label, callable, classification), ...] - real startup work."""

    def build_engine():
        from cryptix_engine import aead, container, kdf  # noqa: F401 - real imports

    def load_config():
        from utils.settings import load_settings
        load_settings()

    def load_hardware_profile():
        from utils.performance import get_hardware_profile
        get_hardware_profile()  # cached profile or documented defaults

    def validate_academy():
        from cryptix_academy.curriculum import validate_curriculum
        from cryptix_academy.tamper_pedagogy import validate_pedagogy
        problems = validate_curriculum() or []
        problems = list(problems) + list(validate_pedagogy())
        if problems:
            raise RuntimeError("; ".join(map(str, problems[:3])))

    def scan_audio_themes():
        from audio.sound_manager import list_themes
        list_themes()

    def build_interface():
        from ui.main_window import MainWindow
        window_holder["window"] = MainWindow(initial_file=initial_file)

    return [
        ("Cryptographic engine", build_engine, CRITICAL),
        ("Local configuration", load_config, RECOVERABLE),
        ("Hardware profile", load_hardware_profile, RECOVERABLE),
        ("Academy curriculum", validate_academy, RECOVERABLE),
        ("Audio themes", scan_audio_themes, RECOVERABLE),
        ("Constructing interface", build_interface, CRITICAL),
    ]


# =========================================================
# THE RUNNER
# =========================================================

def run_startup_sequence(splash, steps, on_complete, on_critical,
                         final_hold_ms=350, critical_pause_ms=1500):
    """Chains steps with QTimer.singleShot(0) - zero artificial pacing.
    Recoverable failure  -> red check, continue.
    Critical failure     -> splash failure state, then on_critical(label, err).
    Success              -> final message, short hold, fade hand-over,
                            then on_complete()."""

    state = {"i": 0, "aborted": False}

    def next_step():
        if state["aborted"]:
            return
        i = state["i"]
        if i >= len(steps):
            splash.show_final_message()
            QTimer.singleShot(final_hold_ms, lambda: (splash.begin_handover(), on_complete()))
            return

        label, fn, classification = steps[i]
        splash.set_current(i)

        def run(fn=fn, i=i, label=label, classification=classification):
            try:
                fn()
                splash.mark_done(i, True)
                state["i"] += 1
                QTimer.singleShot(0, next_step)
            except Exception as exc:  # noqa: BLE001 - startup must never die silently
                # NOTE: the `as exc` binding is deleted when the except block
                # ends - rebind so deferred lambdas can capture it safely.
                err_msg = str(exc)
                splash.mark_done(i, False)
                if classification == CRITICAL:
                    state["aborted"] = True
                    splash.show_failure(label, err_msg)
                    QTimer.singleShot(critical_pause_ms,
                                      lambda: on_critical(label, err_msg))
                else:
                    state["i"] += 1
                    QTimer.singleShot(0, next_step)

        QTimer.singleShot(0, run)

    QTimer.singleShot(0, next_step)


def fade_in_window(window, fade_ms=250):
    """Gentle crossfade-in for the main window at hand-over."""
    window.setWindowOpacity(0.0)
    window.show()
    state = {"i": 0}
    steps = 10
    timer = QTimer(window)
    timer.setInterval(int(fade_ms / steps))

    def tick():
        state["i"] += 1
        try:
            window.setWindowOpacity(min(1.0, state["i"] / steps))
        except RuntimeError:
            timer.stop()
            return
        if state["i"] >= steps:
            timer.stop()

    timer.timeout.connect(tick)
    timer.start()
