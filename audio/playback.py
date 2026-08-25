# audio/playback.py
#
# Stage 6C - the thin Qt Multimedia playback shell.
# Contains NO semantic logic: every decision (which file, which volume,
# whether audio is enabled) comes from audio/sound_manager.py.
#
# Architectural invariants (spec section 2):
#   - audio can never block or break the UI: every public method is
#     defensively wrapped; a missing multimedia backend degrades to no-op
#   - the UI only ever calls emit(event) / ambience controls / update_setting

from audio.sound_manager import resolve_emission, resolve_ambience, update_audio_settings

try:
    from PySide6.QtCore import QObject, QUrl, QPropertyAnimation
    from PySide6.QtMultimedia import QSoundEffect, QMediaPlayer, QAudioOutput
    _QT_AVAILABLE = True
except Exception:  # missing multimedia backend must never break the app
    _QT_AVAILABLE = False

# QMediaPlayer.Loops.Infinite == -1 (stable across Qt 6.x)
_LOOP_FOREVER = -1


class SoundService:
    """Owns QSoundEffect instances (SFX) and one QMediaPlayer (ambience).
    Parent it to the Academy dialog; the Academy owns the audio session."""

    def __init__(self, parent=None):
        self._parent = parent
        self._effects = {}
        self._player = None
        self._audio_out = None
        self._fade_anim = None
        self._current_loop = None
        self._ambience_gen = 0  # ignores stale fade callbacks

        self._settings = {}
        try:
            from utils.settings import load_settings
            self._settings = load_settings()
        except Exception:
            pass

    def audio_settings(self):
        """Current validated audio settings (never raises)."""
        try:
            from audio.sound_manager import merge_audio_defaults, DEFAULT_AUDIO_SETTINGS
            return merge_audio_defaults(self._settings)
        except Exception:
            from audio.sound_manager import DEFAULT_AUDIO_SETTINGS
            return dict(DEFAULT_AUDIO_SETTINGS)

    # ---------------------------------------------------------
    # SFX emission (the one function the UI calls)
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
            if effect is None:
                effect = QSoundEffect(self._parent)
                effect.setSource(QUrl.fromLocalFile(path))
                self._effects[path] = effect
            effect.setVolume(volume)
            effect.play()
        except Exception:
            pass  # invariant: audio failure must never surface in the UI

    # ---------------------------------------------------------
    # Settings (load-merge-save via the shared settings store)
    # ---------------------------------------------------------

    def update_setting(self, key, value):
        try:
            from utils.settings import load_settings, save_settings
            settings = update_audio_settings(load_settings(), {key: value})
            save_settings(settings)
            self._settings = settings

            if key == "theme":
                self._effects.clear()  # reload lazily on next emit

            if key == "master_volume" and self._current_loop is not None:
                resolved = resolve_ambience(self._current_loop, self._settings)
                if resolved and self._audio_out is not None:
                    self._audio_out.setVolume(resolved[1])
        except Exception:
            pass

    # ---------------------------------------------------------
    # Ambience (Academy owns the session; the Lab only transitions)
    # ---------------------------------------------------------

    def start_ambience(self, loop_name):
        if not _QT_AVAILABLE:
            return
        try:
            self._ambience_gen += 1
            gen = self._ambience_gen

            resolved = resolve_ambience(loop_name, self._settings)
            if resolved is None:
                self._hard_stop_ambience()
                return
            path, volume = resolved

            self._ensure_player()
            self._current_loop = loop_name
            self._player.setSource(QUrl.fromLocalFile(path))
            self._player.setLoops(_LOOP_FOREVER)
            self._audio_out.setVolume(0.0)
            self._player.play()
            self._fade_volume_to(volume, 600, None, gen)
        except Exception:
            pass

    def stop_ambience(self, fade_ms=400):
        if not _QT_AVAILABLE:
            return
        try:
            self._ambience_gen += 1
            gen = self._ambience_gen
            self._current_loop = None

            if self._player is None:
                return
            self._fade_volume_to(0.0, fade_ms, lambda: self._finalize_stop(gen), gen)
        except Exception:
            self._hard_stop_ambience()

    def transition_to(self, loop_name):
        """Crossfade-style transition: fade out whatever plays, fade in the new
        loop. If music is disabled, resolve_ambience returns None and this
        simply fades out (graceful)."""
        if not _QT_AVAILABLE:
            return
        try:
            self._ambience_gen += 1
            gen = self._ambience_gen

            resolved = resolve_ambience(loop_name, self._settings)

            if resolved is None:
                self._current_loop = None
                if self._player is not None:
                    self._fade_volume_to(0.0, 400, lambda: self._finalize_stop(gen), gen)
                return

            path, volume = resolved

            def begin_new_loop():
                if gen != self._ambience_gen:
                    return
                self._ensure_player()
                self._current_loop = loop_name
                self._player.setSource(QUrl.fromLocalFile(path))
                self._player.setLoops(_LOOP_FOREVER)
                self._audio_out.setVolume(0.0)
                self._player.play()
                self._fade_volume_to(volume, 600, None, gen)

            playing = (self._player is not None
                       and self._player.playbackState() != QMediaPlayer.PlaybackState.StoppedState)
            if playing:
                self._fade_volume_to(0.0, 400, begin_new_loop, gen)
            else:
                begin_new_loop()
        except Exception:
            self._hard_stop_ambience()

    # ---------------------------------------------------------
    # internals
    # ---------------------------------------------------------

    def _ensure_player(self):
        if self._player is None:
            self._player = QMediaPlayer(self._parent)
            self._audio_out = QAudioOutput(self._parent)
            self._player.setAudioOutput(self._audio_out)

    def _fade_volume_to(self, target, duration_ms, finished_cb, gen):
        if self._audio_out is None:
            if finished_cb:
                finished_cb()
            return
        if self._fade_anim is not None:
            self._fade_anim.stop()

        anim = QPropertyAnimation(self._audio_out, b"volume", self._parent)
        anim.setDuration(int(duration_ms))
        anim.setStartValue(float(self._audio_out.volume()))
        anim.setEndValue(float(max(0.0, min(1.0, target))))
        if finished_cb is not None:
            def _done():
                if gen is None or gen == self._ambience_gen:
                    finished_cb()
            anim.finished.connect(_done)
        anim.start()
        self._fade_anim = anim

    def _finalize_stop(self, gen):
        if gen != self._ambience_gen:
            return
        try:
            if self._player is not None:
                self._player.stop()
                self._player.setSource(QUrl())
        except Exception:
            pass
        self._current_loop = None

    def _hard_stop_ambience(self):
        try:
            if self._player is not None:
                self._player.stop()
                self._player.setSource(QUrl())
        except Exception:
            pass
        self._current_loop = None
