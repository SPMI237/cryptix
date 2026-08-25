# tests/test_audio.py

import json
import os
import struct
import wave

import pytest

from audio.make_sounds import (
    EVENT_SOUNDS,
    LOOP_SOUNDS,
    THEME_DIR,
    SAMPLE_RATE,
    LOOP_SECONDS,
    SFX_PEAK,
    generate_theme,
)
from audio import sound_manager as sm


# ---------------------------------------------------------
# helpers
# ---------------------------------------------------------

def _read_wav(path):
    with wave.open(path, "rb") as w:
        n = w.getnframes()
        meta = (w.getnchannels(), w.getsampwidth(), w.getframerate())
        data = struct.unpack("<%dh" % n, w.readframes(n))
    return meta, n, data


def _theme_wav_names(directory):
    return sorted(f for f in os.listdir(directory) if f.endswith(".wav"))


# ---------------------------------------------------------
# 1. Generator: theme files complete and valid
# ---------------------------------------------------------

def test_theme_files_complete():
    expected = sorted([e + ".wav" for e in EVENT_SOUNDS] + [l + ".wav" for l in LOOP_SOUNDS])
    assert _theme_wav_names(THEME_DIR) == expected  # complete AND no orphans

    with open(os.path.join(THEME_DIR, "manifest.json"), "r", encoding="utf-8") as f:
        manifest = json.load(f)
    assert manifest["name"] == "cyber_lab"
    assert sorted(manifest["events"]) == sorted(EVENT_SOUNDS.keys())
    assert sorted(manifest["loops"]) == sorted(LOOP_SOUNDS.keys())


def test_sfx_files_are_valid_wavs():
    for event in sorted(EVENT_SOUNDS):
        meta, n, data = _read_wav(os.path.join(THEME_DIR, event + ".wav"))
        assert meta == (1, 2, SAMPLE_RATE), f"{event}: bad format {meta}"
        duration = n / SAMPLE_RATE
        assert duration <= 0.85, f"{event}: too long ({duration:.3f}s)"
        peak = max(abs(v) for v in data)
        # uniformly peak-normalized (silence here would be a packaging failure)
        assert int(0.75 * SFX_PEAK * 32767) <= peak <= 32767, f"{event}: peak={peak}"


def test_loops_are_valid_and_seamless():
    for loop in sorted(LOOP_SOUNDS):
        meta, n, data = _read_wav(os.path.join(THEME_DIR, loop + ".wav"))
        assert meta == (1, 2, SAMPLE_RATE), f"{loop}: bad format {meta}"
        assert n == int(LOOP_SECONDS * SAMPLE_RATE), f"{loop}: wrong loop length"
        peak = max(abs(v) for v in data)
        assert 1200 <= peak <= 2600, f"{loop}: ambience level peak={peak}"
        # seamlessness tripwire: the wrap-around jump must be inaudible
        jump = abs(data[-1] - data[0])
        assert jump < 3000, f"{loop}: loop boundary jump {jump}"


def test_generation_is_deterministic(tmp_path):
    result = generate_theme(str(tmp_path))
    assert result["files"]
    for name in _theme_wav_names(THEME_DIR) + ["manifest.json"]:
        with open(os.path.join(THEME_DIR, name), "rb") as f:
            committed = f.read()
        with open(os.path.join(str(tmp_path), name), "rb") as f:
            regenerated = f.read()
        assert committed == regenerated, f"{name}: regeneration is not byte-identical"


# ---------------------------------------------------------
# 2. Sound manager: catalog contract, resolution, fallbacks
# ---------------------------------------------------------

def test_catalog_matches_theme_files():
    # The authoritative catalog (EVENTS + AMBIENCE_LOOPS) must exactly equal
    # the files shipped in every theme - currently cyber_lab.
    expected = sorted(list(EVENT_SOUNDS.keys()) + list(sm.AMBIENCE_LOOPS))
    assert _theme_wav_names(THEME_DIR) == sorted(e + ".wav" for e in expected)


def test_resolve_emission_matrix():
    ok_settings = {"audio": {"theme": "cyber_lab", "sfx_enabled": True,
                             "music_enabled": False, "master_volume": 1.0}}

    # unknown event (typo guard) -> None, never a raise
    assert sm.resolve_emission("not_a_real_event", ok_settings) is None

    # valid event -> (path, volume); volume = master x event_volume
    resolved = sm.resolve_emission("xp_awarded", ok_settings)
    assert resolved is not None
    path, vol = resolved
    assert path.endswith("xp_awarded.wav") and os.path.isfile(path)
    assert vol == pytest.approx(1.0 * sm.EVENTS["xp_awarded"][1])

    # SFX disabled -> None
    assert sm.resolve_emission("xp_awarded", {"audio": {**ok_settings["audio"], "sfx_enabled": False}}) is None

    # missing audio block entirely -> defaults (migration behavior)
    resolved = sm.resolve_emission("xp_awarded", {})
    assert resolved is not None

    # music respects music_enabled, not sfx_enabled
    assert sm.resolve_ambience("academy_loop", ok_settings) is None
    music_on = {"audio": {**ok_settings["audio"], "music_enabled": True}}
    amb = sm.resolve_ambience("academy_loop", music_on)
    assert amb is not None and os.path.isfile(amb[0])
    assert sm.resolve_ambience("not_a_loop", music_on) is None


def test_volume_math():
    assert sm.effective_volume(0.8, 0.9) == pytest.approx(0.72)
    assert sm.effective_volume(2.0, 0.5) == 1.0     # clamped high
    assert sm.effective_volume(-1.0, 0.5) == 0.0    # clamped low
    assert sm.effective_volume("broken", 0.5) == 0.0  # non-numeric never raises


def test_theme_fallback_ladder(tmp_path):
    # Build two valid fake themes + one invalid
    def make_theme(name, valid=True):
        d = tmp_path / name
        d.mkdir()
        if valid:
            (d / "manifest.json").write_text('{"name": "%s"}' % name)
        return str(d)

    make_theme("alpha")                     # valid
    make_theme("broken", valid=False)       # invalid: no manifest
    sm_dir = os.path.join(str(tmp_path), sm.DEFAULT_THEME)
    os.makedirs(sm_dir, exist_ok=True)
    with open(os.path.join(sm_dir, "manifest.json"), "w") as f:
        f.write('{"name": "default"}')

    # requested valid -> requested
    assert sm.resolve_theme("alpha", str(tmp_path)) == os.path.join(str(tmp_path), "alpha")
    # requested invalid -> default theme
    assert sm.resolve_theme("broken", str(tmp_path)) == sm_dir
    assert sm.resolve_theme("does_not_exist", str(tmp_path)) == sm_dir
    assert sm.resolve_theme(None, str(tmp_path)) == sm_dir
    # empty themes dir -> audio disabled (None)
    empty = tmp_path / "empty"
    empty.mkdir()
    assert sm.resolve_theme("alpha", str(empty)) is None
    # discovery lists only valid themes
    assert sm.list_themes(str(tmp_path)) == ["alpha", "cyber_lab"]


def test_settings_merge_preserves_everything_else():
    settings = {
        "dark_mode": True,
        "learning_profile": {"xp": 100},
        "hardware_profile": {"cpu": "x"},
    }
    merged = sm.merge_audio_defaults(settings)
    assert merged["theme"] == "cyber_lab"
    assert merged["sfx_enabled"] is True
    assert merged["music_enabled"] is False
    assert merged["master_volume"] == 0.8
    # the input dict is untouched (purity)
    assert "audio" not in settings

    # partial audio blocks are filled; invalid values sanitized
    partial = sm.merge_audio_defaults({"audio": {"theme": "", "master_volume": "junk"}})
    assert partial["theme"] == "cyber_lab"
    assert partial["master_volume"] == 0.8

    # update path preserves sibling keys
    updated = sm.update_audio_settings(settings, {"music_enabled": True})
    assert updated["audio"]["music_enabled"] is True
    assert updated["dark_mode"] is True
    assert updated["learning_profile"] == {"xp": 100}
    assert "audio" not in settings  # original untouched


# ---------------------------------------------------------
# 3. UI emission wiring (headless, offscreen, no audio device)
# ---------------------------------------------------------

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class RecordingAudio:
    """Stub capturing every semantic call the UI makes."""

    def __init__(self):
        self.events = []

    def emit(self, event):
        self.events.append(event)

    def start_ambience(self, loop_name):
        self.events.append("ambience:" + loop_name)

    def transition_to(self, loop_name):
        self.events.append("ambience:" + loop_name)

    def stop_ambience(self):
        self.events.append("ambience:stop")

    def update_setting(self, key, value):
        pass

    def audio_settings(self):
        return dict(sm.DEFAULT_AUDIO_SETTINGS)


def _qt_app():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_tamper_lab_emission_wiring():
    app = _qt_app()
    from PySide6.QtWidgets import QWidget
    from cryptix_academy.models import LearningProgress
    from ui.tamper_lab_dialog import TamperLabDialog

    stub = RecordingAudio()
    parent = QWidget()  # keep a reference: GC of the parent deletes the dialog
    lab = TamperLabDialog(parent, progress=LearningProgress(), audio=stub)
    lab.show()
    app.processEvents()
    assert "lab_opened" in stub.events
    assert "ambience:lab_loop" in stub.events

    # --- Version experiment: must produce a Layer 1 structural rejection ---
    lab.exp_group.buttons()[3].click()  # Format Version Mutation
    assert "experiment_selected" in stub.events

    challenge = lab.session.challenge
    lab.predict_radios[challenge.prediction_correct].setChecked(True)
    lab.record_prediction_action()
    assert "prediction_recorded" in stub.events

    lab.run_btn.click()
    app.processEvents()
    assert "experiment_started" in stub.events
    assert "structural_rejection" in stub.events
    assert "cryptographic_rejection" not in stub.events

    for (_, combo), item in zip(lab.match_rows, challenge.matching_items):
        combo.setCurrentIndex(item.correct)
    lab.submit_matching_action()
    app.processEvents()
    assert "prediction_correct" in stub.events
    assert "matching_correct" in stub.events
    assert "challenge_completed" in stub.events
    assert "xp_awarded" in stub.events

    # --- Ciphertext experiment: must produce a Layer 2 cryptographic rejection ---
    stub.events.clear()
    lab.exp_group.buttons()[1].click()  # Ciphertext Mutation
    challenge = lab.session.challenge
    lab.predict_radios[challenge.prediction_correct].setChecked(True)
    lab.record_prediction_action()
    lab.run_btn.click()
    app.processEvents()
    assert "cryptographic_rejection" in stub.events
    assert "structural_rejection" not in stub.events

    # --- Control group: success tone, no rejection tones ---
    stub.events.clear()
    lab.exp_group.buttons()[0].click()  # Control Group (No-Op)
    challenge = lab.session.challenge
    lab.predict_radios[challenge.prediction_correct].setChecked(True)
    lab.record_prediction_action()
    lab.run_btn.click()
    app.processEvents()
    assert "control_group_success" in stub.events
    assert "structural_rejection" not in stub.events
    assert "cryptographic_rejection" not in stub.events


def test_academy_emission_and_audio_controls():
    app = _qt_app()
    from PySide6.QtWidgets import QWidget
    from ui.academy_dialog import AcademyDialog

    stub = RecordingAudio()
    parent = QWidget()  # keep a reference: GC of the parent deletes the dialog
    academy = AcademyDialog(parent, audio=stub)
    academy.show()
    app.processEvents()
    assert "academy_opened" in stub.events
    assert "ambience:academy_loop" in stub.events

    # the audio bar exists and reflects default state
    assert academy.sfx_toggle.isChecked() is True
    assert academy.music_toggle.isChecked() is False
    assert academy.theme_selector.count() >= 1

    academy.accept()  # closing the session must not raise


def test_academy_missing_themes_is_actionable(monkeypatch, tmp_path):
    """When audio/themes/ is missing, the app must SAY so - never fail silently."""
    app = _qt_app()
    from PySide6.QtWidgets import QWidget
    import ui.academy_dialog as academy_module

    monkeypatch.setattr(academy_module, "list_themes", lambda *a, **k: [])
    monkeypatch.setattr(academy_module.QMessageBox, "warning", lambda *a, **k: None)

    stub = RecordingAudio()
    parent = QWidget()
    academy = academy_module.AcademyDialog(parent, audio=stub)
    academy.show()  # triggers the one-time missing-themes warning (stubbed)
    app.processEvents()

    assert "no audio themes" in academy.theme_selector.currentText().lower()
    # selecting the hint entry must not corrupt settings
    academy.change_audio_theme(academy.theme_selector.currentText())
    academy.accept()
