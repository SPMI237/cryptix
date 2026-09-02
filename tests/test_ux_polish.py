# tests/test_ux_polish.py
#
# Stage 7 UX polish - headless offscreen UI tests.
# 7A.1: the Tamper Lab stage stepper is a pure presentation component
# driven exclusively by TamperChallengeSession.state.

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QWidget

from cryptix_academy.models import LearningProgress
from cryptix_academy.tamper_pedagogy import TamperChallengeSession
from ui.tamper_lab_dialog import TamperLabDialog


class StubAudio:
    """Audio stub: captures events, plays nothing."""

    def __init__(self):
        self.events = []

    def emit(self, event):
        self.events.append(event)

    def sequence(self, *events, **kwargs):
        self.events.extend(events)

    def start_ambience(self, loop_name):
        pass

    def transition_to(self, loop_name):
        pass

    def stop_ambience(self):
        pass

    def update_setting(self, key, value):
        pass

    def audio_settings(self):
        from audio.sound_manager import DEFAULT_AUDIO_SETTINGS
        return dict(DEFAULT_AUDIO_SETTINGS)


def _app():
    return QApplication.instance() or QApplication([])


def _chip_states(lab):
    return [chip.property("state") for chip in lab.stepper_chips]


def _make_lab():
    parent = QWidget()  # returned to the caller: GC of the parent deletes the dialog
    lab = TamperLabDialog(parent, progress=LearningProgress(), audio=StubAudio())
    lab.show()
    _app().processEvents()
    return parent, lab


def test_stage_stepper_reflects_session_states():
    """The stepper truth table, driven by real UI clicks at every phase."""
    app = _app()
    parent, lab = _make_lab()

    # STATE_PREDICTION: only PREDICT active
    assert lab.session.state == TamperChallengeSession.STATE_PREDICTION
    assert _chip_states(lab) == ["active", "pending", "pending", "pending", "pending"]

    # STATE_ARMED: prediction recorded via the real button
    lab.predict_radios[1].setChecked(True)
    lab.record_prediction_action()
    assert lab.session.state == TamperChallengeSession.STATE_ARMED
    assert _chip_states(lab) == ["done", "active", "pending", "pending", "pending"]

    # STATE_MATCHING: experiment run by real click (evidence rendered first)
    lab.run_btn.click()
    app.processEvents()
    assert lab.session.state == TamperChallengeSession.STATE_MATCHING
    assert _chip_states(lab) == ["done", "done", "done", "active", "pending"]

    # STATE_REVEALED: matching submitted
    for _, combo in lab.match_rows:
        combo.setCurrentIndex(0)
    lab.submit_matching_action()
    app.processEvents()
    assert lab.session.state == TamperChallengeSession.STATE_REVEALED
    assert _chip_states(lab) == ["done", "done", "done", "done", "active"]


def test_stage_stepper_resets_on_experiment_switch():
    app = _app()
    parent, lab = _make_lab()

    lab.predict_radios[0].setChecked(True)
    lab.record_prediction_action()
    assert _chip_states(lab)[0] == "done"

    lab.exp_group.buttons()[1].click()  # switch to another experiment
    app.processEvents()
    assert lab.session.state == TamperChallengeSession.STATE_PREDICTION
    assert _chip_states(lab) == ["active", "pending", "pending", "pending", "pending"]


def test_stage_stepper_done_chips_show_checkmarks():
    _app()
    parent, lab = _make_lab()

    lab.predict_radios[2].setChecked(True)
    lab.record_prediction_action()

    done_chip = lab.stepper_chips[0]
    active_chip = lab.stepper_chips[1]
    pending_chip = lab.stepper_chips[2]

    assert done_chip.text().startswith("✓") and "PREDICT" in done_chip.text()
    assert done_chip.styleSheet() == lab._CHIP_STYLES["done"]
    assert "EXPERIMENT" in active_chip.text() and not active_chip.text().startswith("✓")
    assert active_chip.styleSheet() == lab._CHIP_STYLES["active"]
    assert pending_chip.styleSheet() == lab._CHIP_STYLES["pending"]


def test_stage_stepper_mapping_covers_every_session_state():
    """Anti-drift: every possible session state maps to a valid 5-chip profile."""
    _app()
    parent, lab = _make_lab()

    for state in (
        TamperChallengeSession.STATE_PREDICTION,
        TamperChallengeSession.STATE_ARMED,
        TamperChallengeSession.STATE_MATCHING,
        TamperChallengeSession.STATE_REVEALED,
    ):
        lab.session.state = state  # force directly; stepper must render it
        lab.update_stage_stepper()
        profile = _chip_states(lab)
        assert len(profile) == 5
        assert all(p in ("pending", "active", "done") for p in profile)
        assert profile.count("active") == 1  # exactly one 'you are here' chip
        # no chip after the active one may be done (progress is linear)
        active_idx = profile.index("active")
        assert all(p == "pending" for p in profile[active_idx + 1:])
