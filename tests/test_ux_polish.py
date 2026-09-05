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


def _run_experiment(lab, app, exp_index):
    """Drives one full gated cycle far enough to produce a trace."""
    lab.exp_group.buttons()[exp_index].click()
    app.processEvents()
    lab.predict_radios[0].setChecked(True)
    lab.record_prediction_action()
    lab.run_btn.click()
    app.processEvents()


def test_layer_identity_chips():
    """7A.2: chip text/colors derive from trace.rejection_layer only."""
    app = _app()
    parent, lab = _make_lab()

    # Version Mutation -> Layer 1 structural (amber)
    _run_experiment(lab, app, 3)
    assert "LAYER 1" in lab.layer_chip.text()
    assert "#FFA500" in lab.layer_chip.styleSheet()
    assert not lab.layer_chip.isHidden()

    # Ciphertext Mutation -> Layer 2 cryptographic (cyan)
    _run_experiment(lab, app, 1)
    assert "LAYER 2" in lab.layer_chip.text()
    assert "#00F0FF" in lab.layer_chip.styleSheet()

    # Control Group -> verified baseline (green)
    _run_experiment(lab, app, 0)
    assert "VERIFIED" in lab.layer_chip.text()
    assert "#00FF66" in lab.layer_chip.styleSheet()

    # Switching experiments clears the chip until the next run
    lab.exp_group.buttons()[2].click()
    app.processEvents()
    assert lab.layer_chip.isHidden() or lab.layer_chip.text() == ""


def test_inline_wrong_answer_feedback():
    """7A.3: wrong answers render in-page; question stays active; panel clears."""
    from ui.academy_dialog import AcademyDialog
    from cryptix_academy.models import LearningProgress
    from cryptix_academy.engine import STATE_ACTIVE, STATE_FAILED_ATTEMPT

    app = _app()
    parent = QWidget()
    academy = AcademyDialog(parent, audio=StubAudio())
    academy.progress = LearningProgress()  # isolated fresh profile

    lesson = next(l for l in academy.lessons if l.id == "kdf_argon2id")
    academy.open_challenge(lesson)
    q = academy.active_question
    assert q.question_type == "choice"
    correct_idx = "ABCD".index(q.correct_answer)
    wrong_idx = (correct_idx + 1) % len(q.options)

    academy.options_buttons[wrong_idx].setChecked(True)
    academy.submit_answer(lesson)
    app.processEvents()

    # Inline panel visible, question still active, attempt counted
    assert not academy.inline_feedback_label.isHidden()
    assert "Try again" in academy.inline_feedback_label.text()
    assert academy.active_session.state in (STATE_ACTIVE, STATE_FAILED_ATTEMPT)
    assert academy.active_session.attempts == 2
    assert "question_incorrect" in academy.audio.events  # audio still reflects result

    # Changing the selection clears the panel
    academy.options_buttons[correct_idx].click()
    assert academy.inline_feedback_label.isHidden()


def test_xp_fly_up_animates_only_real_awards():
    """7A.4: the fly-up appears for a real award and cleans itself up."""
    from ui.academy_dialog import AcademyDialog
    from PySide6.QtCore import QEventLoop, QTimer as QTim

    app = _app()
    parent = QWidget()
    academy = AcademyDialog(parent, audio=StubAudio())
    academy._fly_xp(15)
    app.processEvents()

    fly_labels = [c for c in academy.findChildren(type(academy.xp_label))
                  if c.text() == "+15 XP"]
    assert len(fly_labels) == 1

    loop = QEventLoop()
    QTim.singleShot(1400, loop.quit)  # animation is ~900 ms
    loop.exec()
    fly_labels = [c for c in academy.findChildren(type(academy.xp_label))
                  if c.text() == "+15 XP" and not c.isHidden()]
    assert fly_labels == []  # animation finished and hid itself


def test_dashboard_mastery_bars():
    """7A.5: bars reflect mastery values and per-state colors."""
    from ui.academy_dialog import AcademyDialog
    from cryptix_academy.models import LearningProgress
    from cryptix_academy.curriculum import get_questions_for_lesson

    app = _app()
    parent = QWidget()
    academy = AcademyDialog(parent, audio=StubAudio())

    # Craft progress: lesson 1 fully mastered (all first-attempt), lesson 2 becomes current
    progress = LearningProgress()
    for q in get_questions_for_lesson(academy.lessons[0].id):
        progress.completed_challenges[q.id] = {"attempts": 1, "hints_used": 0, "xp": 10, "first_attempt": True}
    progress.completed_lessons.append(academy.lessons[0].id)
    academy.progress = progress
    academy.refresh_dashboard()
    app.processEvents()

    bars = academy.mastery_bars
    assert len(bars) == len(academy.lessons)

    # Lesson 1: complete -> green, 100%
    first = bars[academy.lessons[0].id]
    assert first.value() == 100
    assert "#00FF66" in first.styleSheet()

    # Lesson 2: current/unlocked -> cyan bar (value may be 0)
    second = bars[academy.lessons[1].id]
    assert "#00F0FF" in second.styleSheet()

    # Lesson 3+: locked -> dim bar, disabled button
    third = bars[academy.lessons[2].id]
    assert "#262F3F" in third.styleSheet()


def _shortcut(widgets, seq):
    from PySide6.QtGui import QShortcut
    matches = [s for s in widgets if isinstance(s, QShortcut)
               and s.key().toString() == seq]
    assert matches, f"no shortcut for {seq}"
    return matches[0]


def test_keyboard_drives_academy_challenge(monkeypatch):
    """7A.6: 1-4 select, Enter submits, H hints - wired via QShortcut."""
    from ui.academy_dialog import AcademyDialog
    import ui.academy_dialog as academy_module
    from cryptix_academy.models import LearningProgress

    app = _app()
    parent = QWidget()
    academy = AcademyDialog(parent, audio=StubAudio())
    academy.progress = LearningProgress()
    lesson = next(l for l in academy.lessons if l.id == "kdf_argon2id")
    academy.open_challenge(lesson)
    academy.show()
    app.processEvents()

    monkeypatch.setattr(academy_module.QMessageBox, "information", lambda *a, **k: None)

    q = academy.active_question
    correct_idx = "ABCD".index(q.correct_answer)
    wrong_idx = (correct_idx + 1) % len(q.options)

    # Key '2' selects the second option (index 1) via the shortcut wiring
    _shortcut(academy._page_shortcuts, "2").activated.emit()
    assert academy.options_buttons[1].isChecked()

    # Select a deliberately WRONG option, submit via Enter -> inline feedback
    _shortcut(academy._page_shortcuts, str(wrong_idx + 1)).activated.emit()
    _shortcut(academy._page_shortcuts, "Return").activated.emit()
    app.processEvents()
    assert not academy.inline_feedback_label.isHidden()
    assert academy.active_session.attempts == 2

    # 'H' requests a hint (XP badge drops accordingly)
    _shortcut(academy._page_shortcuts, "H").activated.emit()
    assert academy.active_session.hint_level == 1

    # Shortcuts are retired and rebuilt when a new challenge opens
    before = list(academy._page_shortcuts)
    academy.open_challenge(lesson.next if False else lesson)  # same lesson -> review mode
    app.processEvents()
    assert all(s is not old for s in academy._page_shortcuts for old in before)


def test_keyboard_enter_follows_tamper_gate():
    """7A.6: Enter advances the gated Tamper Lab cycle at every stage."""
    app = _app()
    parent, lab = _make_lab()

    # Enter with no selection: harmless warning, still PREDICTION
    _shortcut(lab._enter_shortcuts, "Return").activated.emit()
    assert lab.session.state == TamperChallengeSession.STATE_PREDICTION

    # Predict -> Enter records
    lab.predict_radios[1].setChecked(True)
    _shortcut(lab._enter_shortcuts, "Return").activated.emit()
    assert lab.session.state == TamperChallengeSession.STATE_ARMED

    # Enter runs the experiment
    _shortcut(lab._enter_shortcuts, "Enter").activated.emit()
    app.processEvents()
    assert lab.session.state == TamperChallengeSession.STATE_MATCHING

    # Enter submits the matching
    for _, combo in lab.match_rows:
        combo.setCurrentIndex(0)
    _shortcut(lab._enter_shortcuts, "Return").activated.emit()
    app.processEvents()
    assert lab.session.state == TamperChallengeSession.STATE_REVEALED


def _make_main_window():
    from ui.main_window import MainWindow
    parent = QWidget()  # referenced by the test: prevents GC deletion
    mw = MainWindow()
    mw.show()
    _app().processEvents()
    return mw


def test_status_banner_states_and_copy():
    """7B.1: banner shows info/success/error with copyable text."""
    from PySide6.QtWidgets import QApplication

    app = _app()
    mw = _make_main_window()

    mw.show_banner("error", "boom: AuthenticationError tag mismatch")
    assert not mw.status_banner.isHidden()
    assert "boom" in mw.banner_label.text()
    assert "FF3B3B" in mw.status_banner.styleSheet()

    mw._copy_banner()
    assert QApplication.clipboard().text() == "boom: AuthenticationError tag mismatch"

    mw.show_banner("success", "✓ Encrypt completed")
    mw.clear_banner()
    assert mw.status_banner.isHidden()


def test_working_state_busy_and_elapsed():
    """7B.2: PROCESSING -> indeterminate bar + live elapsed banner; completion stops it."""
    app = _app()
    mw = _make_main_window()

    mw.set_ui_state("PROCESSING")
    assert mw.progress_bar.isVisible()
    assert mw.progress_bar.maximum() == 0  # indeterminate (busy) mode
    assert mw._busy_timer.isActive()

    mw._tick_busy()
    assert "Working" in mw.banner_label.text()  # elapsed banner is live

    mw.on_error("simulated failure")
    app.processEvents()
    assert not mw._busy_timer.isActive()
    assert not mw.progress_bar.isVisible()
    assert not mw.status_banner.isHidden()      # error persists
    assert "simulated failure" in mw.banner_label.text()

    mw.set_ui_state("PROCESSING")               # next action clears stale errors
    mw._stop_busy()
    app.processEvents()


def test_long_filename_elision():
    """7B.3: long names middle-elide; full path in tooltip."""
    app = _app()
    mw = _make_main_window()

    long_name = "annual_security_audit_report_" + "confidential_" * 12 + "final_v9.txt"
    full_path = f"C:/Users/dell/Documents/{long_name}"
    mw._set_file_label(f"Selected: {long_name}", full_path)

    assert mw.file_label.toolTip() == full_path
    assert "…" in mw.file_label.text() or len(mw.file_label.text()) < len(f"Selected: {long_name}")
    assert mw.file_label.text() != f"Selected: {long_name}"  # definitely elided


def test_banner_dismiss_button_clears_errors():
    """Fix: error banners persist (readable/copyable) until explicitly dismissed."""
    _app()
    mw = _make_main_window()

    mw.show_banner("error", "✗ AuthenticationError: MAC check failed")
    assert not mw.status_banner.isHidden()

    mw.banner_dismiss_btn.click()  # the X button
    assert mw.status_banner.isHidden()


def test_success_banner_auto_clears():
    """Fix: success banners fade on their own; errors do not."""
    from PySide6.QtCore import QEventLoop, QTimer as QTim

    _app()
    mw = _make_main_window()
    mw._BANNER_AUTO_CLEAR_MS = 60  # speed the test up

    mw.show_banner("success", "✓ Encrypt completed")
    assert not mw.status_banner.isHidden()

    loop = QEventLoop()
    QTim.singleShot(300, loop.quit)
    loop.exec()
    assert mw.status_banner.isHidden()  # auto-cleared

    mw.show_banner("error", "✗ stays until dismissed")
    loop2 = QEventLoop()
    QTim.singleShot(300, loop2.quit)
    loop2.exec()
    assert not mw.status_banner.isHidden()  # errors persist


def test_learning_toggle_never_pushes_audit_button_out():
    """Fix: Academy + Audit Log share one row - the footprint is constant."""
    from PySide6.QtCore import QPoint

    app = _app()
    mw = _make_main_window()

    # Be independent of whatever learning_mode was persisted by earlier runs
    mw.learning_toggle.setChecked(False)
    app.processEvents()
    assert mw.academy_button.isHidden()

    try:
        mw.learning_toggle.setChecked(True)   # shows the Academy button
        app.processEvents()
        assert not mw.academy_button.isHidden()

        # Both buttons must sit fully INSIDE the visible window
        for btn in (mw.academy_button, mw.view_log_button):
            pos = btn.mapTo(mw, QPoint(0, 0))
            assert pos.y() >= 0, f"{btn.text()} above the window"
            assert pos.y() + btn.height() <= mw.height(), (
                f"{btn.text()} clipped: bottom {pos.y() + btn.height()} > window {mw.height()}"
            )
            assert btn.isVisible()
    finally:
        mw.learning_toggle.setChecked(False)  # never leak state into other tests
        app.processEvents()


def test_banner_never_shifts_layout():
    """Fix: the banner lives in a permanent fixed slot - no control may move
    when it appears or disappears (DPI-safe by construction)."""
    from PySide6.QtCore import QPoint

    app = _app()
    mw = _make_main_window()

    def audit_y():
        return mw.view_log_button.mapTo(mw, QPoint(0, 0)).y()

    before = audit_y()
    mw.show_banner("error", "✗ long error line one\nline two\nline three")
    app.processEvents()
    during = audit_y()
    mw.clear_banner()
    app.processEvents()
    after = audit_y()

    assert before == during == after, f"layout shifted: {before} -> {during} -> {after}"
    assert mw.status_banner.height() == 52  # fixed slot in both states
    assert mw.status_banner.isHidden()


def test_shortcut_hints_are_visible():
    """Fix: shortcuts are discoverable - hint labels exist on both surfaces."""
    from ui.academy_dialog import AcademyDialog
    from PySide6.QtWidgets import QLabel

    app = _app()
    parent = QWidget()
    academy = AcademyDialog(parent, audio=StubAudio())
    academy.progress = LearningProgress()
    lesson = next(l for l in academy.lessons if l.id == "kdf_argon2id")
    academy.open_challenge(lesson)
    app.processEvents()
    assert "Enter" in academy.shortcut_hint_label.text()
    assert "H" in academy.shortcut_hint_label.text()  # hint key documented

    parent2, lab = _make_lab()
    hints = [l for l in lab.findChildren(QLabel) if "Enter" in l.text() and "Esc" in l.text()]
    assert hints, "Tamper Lab shortcut hint label missing"
