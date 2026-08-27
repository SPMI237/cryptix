# audio/playback.py
#
# Stage 6C.2 - the Qt playback shell over QAudioSink + our own mixer.
# Contains NO semantic logic: every decision (which file, which volume,
# whether audio is enabled) comes from audio/sound_manager.py.
#
# Architectural invariants (spec section 2):
#   - audio can never block or break the UI: every public method is
#     defensively wrapped; a missing multimedia backend degrades to no-op
#   - the UI only ever calls emit(event) / sequence(...) / ambience controls
#     / update_setting
#
# Engine choice (Windows/FFmpeg hard lessons, 6C.1 -> 6C.2):
#   - QSoundEffect: one-shots worked, but infinite loops were SILENT and the
#     effect session died after extended use. Retired.
#   - QMediaPlayer/FFmpeg: silent loops + hard process exits. Retired.
#   - QAudioSink: raw PCM streaming straight to the OS audio endpoint
#     (WASAPI on Windows). No media session, no demuxer, no loop API to
#     trust. We decode our own WAVs (stdlib), mix them ourselves
#     (audio/mixer.py), and loop by wrapping our own playhead. The only
#     remaining dependency is the raw audio device itself.

import os
import time

from audio.sound_manager import resolve_emission, resolve_ambience, update_audio_settings

try:
    from PySide6.QtCore import QTimer
    from PySide6.QtMultimedia import QAudioSink, QAudioFormat
    _QT_AVAILABLE = True
except Exception:  # missing multimedia backend must never break the app
    _QT_AVAILABLE = False

from audio.mixer import Mixer, Voice, load_wav_samples, samples_to_bytes

# Audio layer build marker - lets anyone verify which version is running:
#   python -c "from audio.playback import LAYER_VERSION; print(LAYER_VERSION)"
LAYER_VERSION = "6C.2.0"

SAMPLE_RATE = 44100
TICK_MS = 50        # pump cadence
CHUNK_MS = 100      # samples generated per mixer tick
BUFFER_MS = 300     # target queued audio ahead of the device

AMBIENCE_VOICE = "ambience"


class SoundService:
    """One QAudioSink (push mode) fed by the software Mixer.
    Parent it to the Academy dialog; the Academy owns the audio session."""

    def __init__(self, parent=None):
        self._parent = parent
        self._mixer = Mixer()
        self._sink = None
        self._stream = None       # QIODevice from sink.start() (push mode)
        self._timer = None
        self._idle_since = None
        self._ambience_loop = None

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

            if key == "theme" and self._mixer.has(AMBIENCE_VOICE):
                # swap the running ambience onto the new theme
                resolved = resolve_ambience(self._ambience_loop, self._settings)
                if resolved is not None:
                    self._start_loop_voice(resolved[0], resolved[1])
                else:
                    self._mixer.remove(AMBIENCE_VOICE)

            if key == "master_volume" and self._mixer.has(AMBIENCE_VOICE):
                resolved = resolve_ambience(self._ambience_loop, self._settings)
                if resolved is not None:
                    for v in self._mixer.voices:
                        if v.name == AMBIENCE_VOICE:
                            v.volume = resolved[1]
        except Exception:
            pass

    # ---------------------------------------------------------
    # SFX emission (the functions the UI calls)
    # ---------------------------------------------------------

    def emit(self, event):
        try:
            resolved = resolve_emission(event, self._settings)
            if resolved is None:
                return
            path, volume = resolved
            samples = load_wav_samples(path)
            self._mixer.add(Voice(samples, volume=volume, name=event))
            self._start_engine()
        except Exception:
            pass  # invariant: audio failure must never surface in the UI

    def sequence(self, *events, gap_ms=180):
        """Plays related events one after another (staggered, never stacked)."""
        try:
            delay = 0
            for event in events:
                if _QT_AVAILABLE:
                    QTimer.singleShot(delay, lambda e=event: self.emit(e))
                else:
                    self.emit(event)  # headless/testing fallback
                delay += gap_ms
        except Exception:
            pass

    # ---------------------------------------------------------
    # Ambience (Academy owns the session; the Lab only transitions)
    # ---------------------------------------------------------

    def start_ambience(self, loop_name):
        try:
            resolved = resolve_ambience(loop_name, self._settings)
            if resolved is None:
                self._mixer.remove(AMBIENCE_VOICE)
                return
            self._start_loop_voice(resolved[0], resolved[1])
        except Exception:
            pass

    def stop_ambience(self):
        try:
            self._mixer.remove(AMBIENCE_VOICE)
        except Exception:
            pass

    def transition_to(self, loop_name):
        """Switches the ambience loop. If music is disabled, resolves to
        None and simply stops the current loop."""
        self.start_ambience(loop_name)

    # ---------------------------------------------------------
    # Engine: QAudioSink push mode + timer-driven mixer pump
    # ---------------------------------------------------------

    def _start_loop_voice(self, path, volume):
        samples = load_wav_samples(path)
        self._mixer.remove(AMBIENCE_VOICE)  # replace any running loop
        self._mixer.add(Voice(samples, volume=volume, loop=True, name=AMBIENCE_VOICE))
        self._ambience_loop = self._loop_name_from_path(path)
        self._start_engine()

    def _start_engine(self):
        if not _QT_AVAILABLE:
            return
        try:
            if self._sink is None:
                fmt = QAudioFormat()
                fmt.setSampleRate(SAMPLE_RATE)
                fmt.setChannelCount(1)
                fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
                self._sink = QAudioSink(fmt, self._parent)
                self._sink.setVolume(1.0)  # per-voice volumes already include master
            if self._stream is None:
                self._stream = self._sink.start()  # push mode QIODevice
            if self._timer is None:
                self._timer = QTimer(self._parent)
                self._timer.setInterval(TICK_MS)
                self._timer.timeout.connect(self._pump)
            if not self._timer.isActive():
                self._timer.start()
        except Exception:
            self._teardown_engine()

    def _pump(self):
        """Generates and queues audio. Self-healing: any engine error
        tears the sink down so the next emit() rebuilds it cleanly."""
        try:
            if self._mixer.idle:
                # Let the queued tail finish before releasing the device,
                # otherwise the last ~300 ms of a sound gets clipped.
                now = time.monotonic()
                if self._idle_since is None:
                    self._idle_since = now
                    return
                if now - self._idle_since < (BUFFER_MS / 1000.0 + 0.1):
                    return
                self._teardown_engine()
                return
            self._idle_since = None

            if self._stream is None or self._sink is None:
                self._teardown_engine()
                self._start_engine()
                if self._stream is None:
                    return

            chunk_frames = SAMPLE_RATE * CHUNK_MS // 1000
            target_bytes = SAMPLE_RATE * 2 * BUFFER_MS // 1000
            queued = self._sink.bufferSize() - self._sink.bytesFree()  # bytes

            while queued < target_bytes:
                mixed = self._mixer.tick(chunk_frames)
                written = self._stream.write(samples_to_bytes(mixed))
                if written <= 0:
                    raise OSError("audio stream write failed")
                queued += written
        except Exception:
            self._teardown_engine()

    def _teardown_engine(self):
        try:
            if self._timer is not None:
                self._timer.stop()
            if self._sink is not None:
                self._sink.stop()
        except Exception:
            pass
        self._stream = None
        self._sink = None

    @staticmethod
    def _loop_name_from_path(path):
        base = os.path.basename(path) if path else ""
        return base[:-4] if base.endswith(".wav") else base
