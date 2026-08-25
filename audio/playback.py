# audio/playback.py
#
# Stage 6C - the thin Qt playback shell.
# Contains NO semantic logic: every decision (which file, which volume,
# whether audio is enabled) comes from audio/sound_manager.py.
#
# Architectural invariants (spec section 2):
#   - audio can never block or break the UI: every public method is
#     defensively wrapped; a missing multimedia backend degrades to no-op
#   - the UI only ever calls emit(event) / sequence(...) / ambience controls
#     / update_setting
#
# Engine choice (Windows/FFmpeg hard lessons, 6C.1):
#   - ALL audio - effects AND ambience loops - plays through QSoundEffect.
#     QSoundEffect is the engine proven reliable on the field machine: no
#     FFmpeg demuxer involvement, no media-session crashes, no silent
#     QPropertyAnimation failures.
#   - QMediaPlayer is NOT used anywhere. On Windows, Qt's FFmpeg backend
#     logged the WAVs, then produced silence and hard process exits.
#   - Ambience loops via QSoundEffect.Loops.Infinite (documented, stable),
#     volume fades via plain QTimer steps calling setVolume() directly.
#   - Related reveal sounds are staggered via sequence(): never stack
#     simultaneous effects.

import os

from audio.sound_manager import resolve_emission, resolve_ambience, update_audio_settings

try:
    from PySide6.QtCore import QUrl, QTimer
    from PySide6.QtMultimedia import QSoundEffect
    _QT_AVAILABLE = True
    # QSoundEffect.Loops.Infinite (Qt 6 style); fall back to the flat name.
    try:
        _INFINITE = QSoundEffect.Loops.Infinite
    except AttributeError:
        _INFINITE = QSoundEffect.Infinite
except Exception:  # missing multimedia backend must never break the app
    _QT_AVAILABLE = False
    _INFINITE = -1

SEQUENCE_GAP_MS = 180  # audible spacing between chained event sounds

# Audio layer build marker - lets anyone verify which version is running:
#   python -c "from audio.playback import LAYER_VERSION; print(LAYER_VERSION)"
LAYER_VERSION = "6C.1.4"


class SoundService:
    """Owns the QSoundEffect pool (SFX + the active ambience loop).
    Parent it to the Academy dialog; the Academy owns the audio session."""

    def __init__(self, parent=None):
        self._parent = parent
        self._effects = {}
        self._loop_effect = None   # the one active ambience QSoundEffect
        self._loop_name = None
        self._fade_timer = None
        self._fade_gen = 0         # ignores stale fade callbacks

        self._settings = {}
        try:
            from utils.settings import load_settings
            self._settings = load_settings()
        except Exception:
            pass

    # ---------------------------------------------------------
    # Settings (load-merge-save via the shared settings store)
    # ---------------------------------------------------------

    def audio_settings(self):
        """Current validated audio settings (never raises)."""
        try:
            from audio.sound_manager import merge_audio_defaults, DEFAULT_AUDIO_SETTINGS
            return merge_audio_defaults(self._settings)
        except Exception:
            from audio.sound_manager import DEFAULT_AUDIO_SETTINGS
            return dict(DEFAULT_AUDIO_SETTINGS)

    def update_setting(self, key, value):
        try:
            from utils.settings import load_settings, save_settings
            settings = update_audio_settings(load_settings(), {key: value})
            save_settings(settings)
            self._settings = settings

            if key == "theme":
                self._effects.clear()  # reload lazily on next emit
                # Restart the ambience on the new theme if one is playing
                if self._loop_name is not None:
                    resolved = resolve_ambience(self._loop_name, self._settings)
                    if resolved is not None:
                        self._fade_gen += 1
                        self._play_loop(resolved[0], resolved[1], self._fade_gen, fade_ms=350)
                    else:
                        self._stop_loop_now()

            if key == "master_volume" and self._loop_name is not None:
                resolved = resolve_ambience(self._loop_name, self._settings)
                if resolved and self._loop_effect is not None:
                    self._loop_effect.setVolume(resolved[1])
        except Exception:
            pass

    # ---------------------------------------------------------
    # SFX emission (the functions the UI calls)
    # ---------------------------------------------------------

    def emit(self, event):
        if not _QT_AVAILABLE:
            return
        try:
            resolved = resolve_emission(event, self._settings)
            if resolved is None:
                return
            path, volume = resolved

            effect = self._effects.get(path)
            # Recreate effects that fell into the error state (dead session
            # recovery) instead of silently keeping them around forever.
            if effect is not None and effect.status() == QSoundEffect.Status.Error:
                self._effects.pop(path, None)
                effect = None
            if effect is None:
                effect = QSoundEffect(self._parent)
                effect.setSource(QUrl.fromLocalFile(path))
                self._effects[path] = effect

            effect.setVolume(volume)
            effect.play()
        except Exception:
            pass  # invariant: audio failure must never surface in the UI

    def sequence(self, *events, gap_ms=SEQUENCE_GAP_MS):
        """Plays related events one after another - never stacks
        simultaneous effects (concurrent bursts killed the session before)."""
        for i, event in enumerate(events):
            if _QT_AVAILABLE:
                try:
                    QTimer.singleShot(i * gap_ms, lambda e=event: self.emit(e))
                except Exception:
                    pass
            else:
                self.emit(event)  # headless/testing fallback: immediate order

    # ---------------------------------------------------------
    # Ambience (Academy owns the session; the Lab only transitions)
    # ---------------------------------------------------------

    def start_ambience(self, loop_name):
        if not _QT_AVAILABLE:
            return
        try:
            self._fade_gen += 1
            gen = self._fade_gen

            resolved = resolve_ambience(loop_name, self._settings)
            if resolved is None:
                self._fade_out_loop(300, gen)
                return
            path, volume = resolved
            self._play_loop(path, volume, gen, fade_ms=700)
        except Exception:
            self._stop_loop_now()

    def stop_ambience(self, fade_ms=400):
        if not _QT_AVAILABLE:
            return
        try:
            self._fade_gen += 1
            gen = self._fade_gen
            self._loop_name = None
            if self._loop_effect is None:
                return
            self._fade_out_loop(fade_ms, gen)
        except Exception:
            self._stop_loop_now()

    def transition_to(self, loop_name):
        """Fade out whatever plays, then fade in the new loop. If music is
        disabled, resolve_ambience returns None and this simply fades out."""
        if not _QT_AVAILABLE:
            return
        try:
            self._fade_gen += 1
            gen = self._fade_gen

            resolved = resolve_ambience(loop_name, self._settings)
            if resolved is None:
                self._loop_name = None
                self._fade_out_loop(300, gen)
                return

            path, volume = resolved

            def begin():
                if gen != self._fade_gen:
                    return
                self._play_loop(path, volume, gen, fade_ms=700)

            if self._loop_effect is not None and self._loop_name is not None:
                self._fade_out_loop(300, gen, done=begin)
            else:
                begin()
        except Exception:
            self._stop_loop_now()

    # ---------------------------------------------------------
    # internals
    # ---------------------------------------------------------

    def _play_loop(self, path, volume, gen, fade_ms):
        self._dispose_loop_effect()

        try:
            effect = QSoundEffect(self._parent)
            effect.setSource(QUrl.fromLocalFile(path))
            effect.setLoops(_INFINITE)
            self._loop_effect = effect
            self._loop_name = self._loop_name_from_path(path)
            effect.setVolume(0.0 if fade_ms > 0 else volume)
            effect.play()
            if fade_ms > 0:
                self._ramp_effect_volume(effect, volume, fade_ms, gen)
        except Exception:
            self._stop_loop_now()

    def _fade_out_loop(self, fade_ms, gen, done=None):
        effect = self._loop_effect
        if effect is None:
            self._loop_name = None
            if done is not None:
                done()
            return
        self._ramp_effect_volume(
            effect, 0.0, fade_ms, gen,
            done=lambda: self._finalize_stop(gen, done),
        )

    def _finalize_stop(self, gen, done=None):
        if gen != self._fade_gen:
            if done is not None:
                done()
            return
        self._stop_loop_now()
        if done is not None:
            done()

    def _stop_loop_now(self):
        self._dispose_loop_effect()
        self._loop_name = None

    def _dispose_loop_effect(self):
        effect = self._loop_effect
        self._loop_effect = None
        if effect is not None:
            try:
                effect.stop()
                effect.setSource(QUrl())
            except Exception:
                pass

    @staticmethod
    def _loop_name_from_path(path):
        base = os.path.basename(path) if path else ""
        return base[:-4] if base.endswith(".wav") else base

    def _ramp_effect_volume(self, effect, target, duration_ms, gen, done=None):
        """Plain QTimer-stepped volume ramp: direct setVolume() calls only -
        no QPropertyAnimation (unreliable on some multimedia builds)."""
        if self._fade_timer is not None:
            self._fade_timer.stop()
            self._fade_timer = None

        steps = max(1, int(duration_ms) // 40)
        interval = max(1, int(duration_ms) / steps)
        state = {"i": 0}

        timer = QTimer(self._parent)
        timer.setInterval(int(interval))

        def tick():
            if gen is not None and gen != self._fade_gen:
                timer.stop()
                self._fade_timer = None
                return
            state["i"] += 1
            frac = min(1.0, state["i"] / steps)
            try:
                start = state.get("start")
                if start is None:
                    start = state["start"] = float(effect.volume())
                value = start + (target - start) * frac
                effect.setVolume(max(0.0, min(1.0, value)))
            except Exception:
                pass
            if state["i"] >= steps:
                timer.stop()
                self._fade_timer = None
                if done is not None and (gen is None or gen == self._fade_gen):
                    done()

        timer.timeout.connect(tick)
        timer.start()
        self._fade_timer = timer
