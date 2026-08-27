# audio/mixer.py
#
# Stage 6C.2 - the pure software mixer. NO Qt, NO audio device: fully
# testable headlessly. Voices are 16-bit PCM sample buffers; the mixer
# sums active voices per tick and clamps to the int16 range.
#
# Why this exists: both QSoundEffect (silent infinite loops, session death
# after extended use) and QMediaPlayer (silent playback + hard crashes via
# the FFmpeg backend) failed on the field machine. Playback now streams raw
# PCM through QAudioSink, and THIS module owns mixing/looping in pure Python.

import struct
import wave

_SAMPLE_CACHE = {}


def load_wav_samples(path):
    """Loads a mono 16-bit 44.1 kHz WAV into a tuple of int samples.
    Cached: themes are small and emit() is frequent."""
    if path in _SAMPLE_CACHE:
        return _SAMPLE_CACHE[path]
    with wave.open(path, "rb") as w:
        channels = w.getnchannels()
        sample_width = w.getsampwidth()
        rate = w.getframerate()
        if (channels, sample_width, rate) != (1, 2, 44100):
            raise ValueError(
                f"{path}: expected mono/16-bit/44100 WAV, got "
                f"ch={channels} width={sample_width} rate={rate}"
            )
        frames = w.getnframes()
        samples = struct.unpack("<%dh" % frames, w.readframes(frames))
    _SAMPLE_CACHE[path] = samples
    return samples


def samples_to_bytes(samples):
    """int sample iterable -> little-endian 16-bit PCM bytes."""
    return struct.pack("<%dh" % len(samples),
                       *[max(-32768, min(32767, int(s))) for s in samples])


class Voice:
    """One playing sound: samples + playhead + volume + loop flag."""
    __slots__ = ("samples", "pos", "volume", "loop", "name")

    def __init__(self, samples, volume=1.0, loop=False, name=""):
        self.samples = samples
        self.pos = 0
        self.volume = volume
        self.loop = loop
        self.name = name

    @property
    def finished(self):
        return (not self.loop) and self.pos >= len(self.samples)


class Mixer:
    """Summing mixer over Voice objects. tick(n) advances every voice by n
    samples and returns n mixed (clamped) samples. Finished one-shot voices
    are dropped; loop voices wrap around forever, sample-accurately."""

    def __init__(self):
        self.voices = []

    def add(self, voice):
        self.voices.append(voice)

    def remove(self, name):
        self.voices = [v for v in self.voices if v.name != name]

    def has(self, name):
        return any(v.name == name for v in self.voices)

    @property
    def idle(self):
        return not self.voices

    def tick(self, n):
        out = [0] * n
        alive = []
        for v in self.voices:
            samples = v.samples
            length = len(samples)
            volume = v.volume
            if v.loop:
                for i in range(n):
                    out[i] += int(samples[v.pos] * volume)
                    v.pos += 1
                    if v.pos >= length:
                        v.pos = 0
                alive.append(v)
            else:
                remaining = length - v.pos
                take = min(n, remaining)
                for i in range(take):
                    out[i] += int(samples[v.pos] * volume)
                    v.pos += 1
                if v.pos < length:
                    alive.append(v)
        self.voices = alive
        return [max(-32768, min(32767, s)) for s in out]
