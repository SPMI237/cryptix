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
    LOOP_PEAK,
    generate_theme,
    render_all_themes,
)
from audio import sound_manager as sm
from audio import playback as pb


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

def _all_theme_dirs():
    return [os.path.join(sm.THEMES_DIR, name) for name in sm.list_themes()]


def test_theme_files_complete():
    theme_dirs = _all_theme_dirs()
    assert len(theme_dirs) >= 4  # cyber_lab, premium_minimal, scientific, cyberpunk

    expected = sorted([e + ".wav" for e in EVENT_SOUNDS] + [l + ".wav" for l in LOOP_SOUNDS])
    for theme_dir in theme_dirs:
        assert _theme_wav_names(theme_dir) == expected, theme_dir  # complete AND no orphans

        with open(os.path.join(theme_dir, "manifest.json"), "r", encoding="utf-8") as f:
            manifest = json.load(f)
        assert manifest["name"] == os.path.basename(theme_dir)
        assert sorted(manifest["events"]) == sorted(EVENT_SOUNDS.keys())
        assert sorted(manifest["loops"]) == sorted(LOOP_SOUNDS.keys())


def test_sfx_files_are_valid_wavs():
    for theme_dir in _all_theme_dirs():
        for event in sorted(EVENT_SOUNDS):
            meta, n, data = _read_wav(os.path.join(theme_dir, event + ".wav"))
            assert meta == (1, 2, SAMPLE_RATE), f"{theme_dir}/{event}: bad format {meta}"
            duration = n / SAMPLE_RATE
            assert duration <= 0.85, f"{theme_dir}/{event}: too long ({duration:.3f}s)"
            peak = max(abs(v) for v in data)
            # uniformly peak-normalized (silence here would be a packaging failure)
            assert int(0.75 * SFX_PEAK * 32767) <= peak <= 32767, f"{theme_dir}/{event}: peak={peak}"


def test_loops_are_valid_and_seamless():
    for theme_dir in _all_theme_dirs():
        for loop in sorted(LOOP_SOUNDS):
            meta, n, data = _read_wav(os.path.join(theme_dir, loop + ".wav"))
            assert meta == (1, 2, SAMPLE_RATE), f"{theme_dir}/{loop}: bad format {meta}"
            assert n == int(LOOP_SECONDS * SAMPLE_RATE), f"{theme_dir}/{loop}: wrong loop length"
            peak = max(abs(v) for v in data)
            expected = LOOP_PEAK * 32767
            assert 0.85 * expected <= peak <= 1.05 * expected, f"{theme_dir}/{loop}: level peak={peak}"
            # seamlessness tripwire: the wrap-around jump must be inaudible
            jump = abs(data[-1] - data[0])
            assert jump < 3000, f"{theme_dir}/{loop}: loop boundary jump {jump}"


def test_generation_is_deterministic(tmp_path):
    results = render_all_themes(str(tmp_path))
    assert len(results) >= 4
    for theme_dir in _all_theme_dirs():
        theme_name = os.path.basename(theme_dir)
        for name in _theme_wav_names(theme_dir) + ["manifest.json"]:
            with open(os.path.join(theme_dir, name), "rb") as f:
                committed = f.read()
            with open(os.path.join(str(tmp_path), theme_name, name), "rb") as f:
                regenerated = f.read()
            assert committed == regenerated, f"{theme_name}/{name}: regeneration is not byte-identical"


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

    def sequence(self, *events, gap_ms=180):
        # Mirrors SoundService.sequence: order preserved, staggered in time.
        for event in events:
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


# ---------------------------------------------------------
# 4. Software mixer (Stage 6C.2 engine core) - pure, headless
# ---------------------------------------------------------

from audio.mixer import Mixer, Voice, load_wav_samples


def test_wav_loader_returns_pcm_samples():
    samples = load_wav_samples(os.path.join(THEME_DIR, "xp_awarded.wav"))
    assert len(samples) > 1000
    assert all(isinstance(s, int) for s in samples[:50])
    assert max(abs(s) for s in samples) > 10000  # audible content


def test_mixer_silent_when_idle():
    m = Mixer()
    assert m.idle
    assert m.tick(100) == [0] * 100


def test_mixer_event_plays_and_finishes():
    m = Mixer()
    m.add(Voice([1000] * 500, volume=1.0, name="ev"))
    assert not m.idle
    assert all(s == 1000 for s in m.tick(200))
    m.tick(200)
    m.tick(100)
    last = m.tick(200)  # voice exhausted (500 < 600 consumed) -> dropped
    assert m.idle
    assert all(s == 0 for s in last[100:])  # beyond the voice: silence


def test_mixer_loop_wraps_forever_sample_accurately():
    m = Mixer()
    m.add(Voice([100, -100], volume=1.0, loop=True, name="amb"))
    total = 0
    for _ in range(2000):
        chunk = m.tick(7)  # odd step forces wrap across the boundary
        total += sum(abs(s) for s in chunk)
        assert not m.idle
    assert total == 2000 * 7 * 100  # every sample present, nothing lost at wraps


def test_mixer_sums_voices_and_clamps():
    m = Mixer()
    m.add(Voice([20000] * 100, volume=1.0, name="a"))
    m.add(Voice([20000] * 100, volume=1.0, name="b"))
    assert m.tick(50)[0] == 32767  # 40000 clamps to int16 max

    m2 = Mixer()
    m2.add(Voice([20000] * 100, volume=0.5, name="half"))
    assert m2.tick(1)[0] == 10000  # per-voice volume scaling


def test_mixer_remove_by_name_stops_only_that_voice():
    m = Mixer()
    m.add(Voice([500] * 100, loop=True, name="ambience"))
    m.add(Voice([10] * 50, name="ev"))
    m.remove("ambience")
    assert not m.has("ambience")
    assert m.has("ev")
    assert all(s == 10 for s in m.tick(10))


def test_service_headless_api_never_raises():
    svc = pb.SoundService()
    svc.emit("xp_awarded")
    svc.sequence("prediction_correct", "challenge_completed")
    svc.start_ambience("academy_loop")
    svc.transition_to("lab_loop")
    svc.stop_ambience()
    svc.update_setting("music_enabled", True)
    svc.update_setting("master_volume", 0.5)
    svc.update_setting("theme", "cyber_lab")
    assert svc.audio_settings()["theme"] == "cyber_lab"


# ---------------------------------------------------------
# 5. AI theme importer (Stage 6C.5) - converts foreign WAVs
# ---------------------------------------------------------

def test_ai_theme_importer_end_to_end(tmp_path):
    import struct as _struct
    import wave as _wave
    from audio.import_ai_theme import import_theme

    def fake_ai_wav(path, rate, channels, seconds, amp, value=0.6):
        frames = int(rate * seconds)
        samples = []
        for i in range(frames):
            v = amp * value if i % 3 else amp  # non-silent, non-uniform
            samples.extend([v] * channels)
        payload = _struct.pack("<%dh" % (frames * channels),
                               *[max(-32768, min(32767, int(s * 32767))) for s in samples])
        with _wave.open(str(path), "wb") as w:
            w.setnchannels(channels)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(payload)

    src_dir = tmp_path / "ai_output"
    src_dir.mkdir()
    for event in sm.EVENTS:
        fake_ai_wav(src_dir / f"{event}.wav", rate=48000, channels=2,
                    seconds=1.2, amp=0.2)  # stereo 48k, too long, too quiet
    for loop in sm.AMBIENCE_LOOPS:
        fake_ai_wav(src_dir / f"{loop}.wav", rate=44100, channels=1,
                    seconds=5.0, amp=0.3)  # clicky edges (no fade)

    themes_root = tmp_path / "themes"
    report = import_theme(str(src_dir), "ai_field_pack", out_root=str(themes_root),
                          tool="ElevenLabs SFX", plan="Starter")

    assert report["missing"] == []
    assert "ai_field_pack" in sm.list_themes(str(themes_root))  # dropdown discovery

    theme_dir = themes_root / "ai_field_pack"
    for event in sm.EVENTS:  # SFX: trimmed, normalized, mono 44.1k
        meta, n, data = _read_wav(str(theme_dir / f"{event}.wav"))
        assert meta == (1, 2, 44100), event
        assert n / 44100 <= 0.85, event
        assert max(abs(v) for v in data) >= int(0.75 * SFX_PEAK * 32767), event

    for loop in sm.AMBIENCE_LOOPS:  # loops: edge-faded to zero, level-correct
        meta, n, data = _read_wav(str(theme_dir / f"{loop}.wav"))
        assert meta == (1, 2, 44100), loop
        assert abs(data[0]) < 120 and abs(data[-1]) < 120, loop  # seamless wrap
        assert max(abs(v) for v in data) >= int(0.85 * LOOP_PEAK * 32767), loop

    manifest = json.load(open(theme_dir / "manifest.json"))
    assert manifest["provenance"] == {"tool": "ElevenLabs SFX", "plan": "Starter",
                                      "pipeline": "import"}
    assert sorted(manifest["events"]) == sorted(sm.EVENTS.keys())

    # Partial import must never be fatal - missing events are reported
    partial_dir = tmp_path / "partial"
    partial_dir.mkdir()
    fake_ai_wav(partial_dir / "xp_awarded.wav", 44100, 1, 0.3, 0.5)
    report2 = import_theme(str(partial_dir), "ai_partial", out_root=str(themes_root))
    assert "xp_awarded" in report2["imported"]
    assert len(report2["missing"]) == len(sm.EVENTS) + len(sm.AMBIENCE_LOOPS) - 1


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
