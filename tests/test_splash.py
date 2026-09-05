# tests/test_splash.py
#
# Responsive splash screen (v1.5) - headless offscreen tests:
# milestone contract, state rendering, two-class failure semantics, hand-over.

import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from ui.splash import (
    CryptixSplash,
    startup_steps,
    run_startup_sequence,
    CRITICAL,
    RECOVERABLE,
)


def _app():
    return QApplication.instance() or QApplication([])


def _wait_until(cond, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        _app().processEvents()
        if cond():
            return True
        time.sleep(0.01)
    return False


def test_milestone_contract():
    """The 6 real milestones: ordered, classified, and every one executes."""
    _app()  # the interface step constructs a QMainWindow - QApp must exist first
    holder = {}
    steps = startup_steps(initial_file=None, window_holder=holder)
    assert len(steps) == 6
    assert [s[0] for s in steps] == [
        "Cryptographic engine", "Local configuration", "Hardware profile",
        "Academy curriculum", "Audio themes", "Constructing interface",
    ]
    # two-class amendment: engine + interface are critical, the rest recoverable
    assert steps[0][2] == CRITICAL and steps[5][2] == CRITICAL
    assert all(s[2] == RECOVERABLE for s in steps[1:5])

    for label, fn, classification in steps:
        fn()  # every real milestone must execute headlessly

    assert holder["window"] is not None  # interface step really built the window
    from audio.sound_manager import list_themes
    assert "cyber_lab" in list_themes()


def test_splash_state_rendering():
    _app()
    splash = CryptixSplash(["a", "b", "c"])
    splash.set_current(0)
    assert splash.row_states() == ["current", "pending", "pending"]
    splash.mark_done(0)
    splash.set_current(1)
    assert splash.row_states() == ["done", "current", "pending"]
    assert splash.progress() == pytest.approx(1 / 3)

    assert not splash.is_final_message_visible()
    splash.show_final_message()
    assert splash.is_final_message_visible()

    splash.mark_done(1, ok=False)
    assert splash.row_states()[1] == "error"


def test_recoverable_failure_continues():
    """Recoverable failure: red check, sequence continues, no abort."""
    _app()

    def boom():
        raise ValueError("theme scan exploded")

    steps = [
        ("one", lambda: None, RECOVERABLE),
        ("two", boom, RECOVERABLE),
        ("three", lambda: None, CRITICAL),
    ]
    splash = CryptixSplash([s[0] for s in steps])
    events = []
    run_startup_sequence(splash, steps,
                         on_complete=lambda: events.append("complete"),
                         on_critical=lambda *a: events.append("critical"),
                         final_hold_ms=10)
    assert _wait_until(lambda: bool(events))
    assert events == ["complete"]
    assert splash.row_states() == ["done", "error", "done"]
    assert splash.failure() is None  # never claimed a safe abort


def test_critical_failure_aborts_safely():
    """Critical failure: startup aborts, completion never fires, failure shown."""
    _app()

    def boom():
        raise RuntimeError("engine import failed")

    steps = [
        ("engine", boom, CRITICAL),
        ("later", lambda: None, RECOVERABLE),
    ]
    splash = CryptixSplash([s[0] for s in steps])
    events = []
    run_startup_sequence(splash, steps,
                         on_complete=lambda: events.append("complete"),
                         on_critical=lambda label, err: events.append((label, str(err))),
                         critical_pause_ms=30)
    assert _wait_until(lambda: bool(events))
    assert events == [("engine", "engine import failed")]
    assert splash.failure() == ("engine", "engine import failed")
    assert splash.row_states() == ["error", "pending"]  # sequence never continued


def test_success_handover_closes_splash():
    """Success: final message, fade hand-over, splash closes, window callback runs."""
    _app()
    steps = [("only", lambda: None, RECOVERABLE)]
    splash = CryptixSplash(["only"])
    completed = []
    run_startup_sequence(splash, steps,
                         on_complete=lambda: completed.append(True),
                         on_critical=lambda *a: None,
                         final_hold_ms=10)
    assert _wait_until(lambda: completed and splash.isHidden(), timeout=4.0)
    assert splash.is_final_message_visible()
