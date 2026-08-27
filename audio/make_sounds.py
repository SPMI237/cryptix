# audio/make_sounds.py
#
# Deterministic synthesizer for Cryptix Academy audio themes (Stage 6C).
# Renders the "Cyber Laboratory" theme: 16 semantic event sounds + 2 seamless
# ambience loops as 44.1 kHz / 16-bit mono PCM WAV files.
#
# Regenerate the complete theme with a single reproducible entry point:
#
#     python -m audio.make_sounds
#
# Determinism contract (spec section 5): no unseeded entropy, no clock, no
# machine-dependent values. The only randomness is the loop noise floor, drawn
# from random.Random(2026)/Random(2027). Regeneration is byte-identical,
# enforced by tests/test_audio.py.

import json
import math
import os
import random
import struct
import wave

SAMPLE_RATE = 44100
THEME_NAME = "cyber_lab"
THEME_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "themes", THEME_NAME)

SFX_PEAK = 0.90          # every event sound peak-normalized to one consistent level
LOOP_SECONDS = 12.0      # ambience loop length
LOOP_PEAK = 0.40         # FINAL level (~ -8 dBFS): clearly present behind the
                         # 0.90 SFX without dominating (field-tuned 6C.1)
TWO_PI = 2.0 * math.pi


# =========================================================
# LOW-LEVEL SYNTHESIS (standard library only)
# =========================================================

def _sine(num_samples, freq, amplitude=1.0):
    w = TWO_PI * freq / SAMPLE_RATE
    return [amplitude * math.sin(w * i) for i in range(num_samples)]


def _sweep(num_samples, f0, f1, amplitude=1.0):
    """Linear frequency sweep with a phase-continuous integral."""
    out = []
    phase = 0.0
    step = (f1 - f0) / num_samples
    for i in range(num_samples):
        f = f0 + step * i
        phase += TWO_PI * f / SAMPLE_RATE
        out.append(amplitude * math.sin(phase))
    return out


def _square(num_samples, freq, amplitude=1.0, harmonics=4):
    """Band-limited square wave (odd harmonics only) - warmer than a hard clip."""
    out = [0.0] * num_samples
    for k in range(1, harmonics * 2, 2):
        a = amplitude / k
        w = TWO_PI * freq * k / SAMPLE_RATE
        for i in range(num_samples):
            out[i] += a * math.sin(w * i)
    return out


def _envelope(num_samples, attack, decay_rate):
    """Short linear attack (click prevention) + exponential decay."""
    attack_n = max(1, int(attack * SAMPLE_RATE))
    env = []
    for i in range(num_samples):
        if i < attack_n:
            env.append(i / attack_n)
        else:
            t = (i - attack_n) / SAMPLE_RATE
            env.append(math.exp(-decay_rate * t))
    return env


def _fade_edges(samples, fade=0.003):
    """3 ms fade-in/out on the final mix to guarantee click-free tails."""
    n = int(fade * SAMPLE_RATE)
    total = len(samples)
    for i in range(min(n, total // 2)):
        g = i / n
        samples[i] *= g
        samples[total - 1 - i] *= g
    return samples


def _place(base, src, offset_seconds):
    """Mixes src into base at a time offset, extending base as needed."""
    start = int(offset_seconds * SAMPLE_RATE)
    need = start + len(src)
    if need > len(base):
        base.extend([0.0] * (need - len(base)))
    for i, v in enumerate(src):
        base[start + i] += v
    return base


def _normalize(samples, peak):
    m = max((abs(v) for v in samples), default=0.0) or 1.0
    g = peak / m
    return [v * g for v in samples]


def _to_int16(samples):
    """Scales float samples (nominal range [-1.0, 1.0]) into 16-bit PCM.
    NOTE: the scale factor is required - int(0.9) truncates to 0!"""
    return struct.pack(
        "<%dh" % len(samples),
        *[max(-32768, min(32767, round(v * 32767.0))) for v in samples],
    )


def _write_wav(path, samples):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(_to_int16(samples))


def tone(freq, duration, kind="sine", decay=6.0, amp=1.0, sweep_to=None, attack=0.004):
    """One enveloped note. kind: 'sine' | 'square'."""
    n = int(duration * SAMPLE_RATE)
    if sweep_to is not None:
        raw = _sweep(n, freq, sweep_to, amp)
    elif kind == "square":
        raw = _square(n, freq, amp)
    else:
        raw = _sine(n, freq, amp)
    env = _envelope(n, attack, decay)
    return [s * e for s, e in zip(raw, env)]


# =========================================================
# AMBIENCE (seamless by construction: integer phase cycles)
# =========================================================

def _loop_freq(freq):
    """Quantizes a frequency to an integer number of cycles per loop
    so the waveform is perfectly continuous across the loop boundary."""
    cycles = max(1, round(freq * LOOP_SECONDS))
    return cycles / LOOP_SECONDS


def _pad(freq, amp, lfo_cycles, lfo_phase=0.0):
    """One sine pad component with an integer-cycle amplitude LFO."""
    n = int(LOOP_SECONDS * SAMPLE_RATE)
    f = _loop_freq(freq)
    lfo_f = lfo_cycles / LOOP_SECONDS
    w = TWO_PI * f / SAMPLE_RATE
    wl = TWO_PI * lfo_f / SAMPLE_RATE
    return [
        amp * (0.65 + 0.35 * math.sin(wl * i + lfo_phase)) * math.sin(w * i)
        for i in range(n)
    ]


def _noise_floor(amp, cutoff_hz, seed):
    """Low-passed noise floor, made loopable by folding the tail into the head
    (classic crossfade loop technique - deterministic, seed-fixed)."""
    n = int(LOOP_SECONDS * SAMPLE_RATE)
    fade_n = int(0.5 * SAMPLE_RATE)
    rng = random.Random(seed)
    raw = [rng.uniform(-1.0, 1.0) for _ in range(n + fade_n)]

    a = 1.0 - math.exp(-TWO_PI * cutoff_hz / SAMPLE_RATE)
    out = []
    y = 0.0
    for x in raw:
        y += a * (x - y)
        out.append(y)

    for i in range(fade_n):
        g = i / fade_n
        out[i] = out[i] * g + out[n + i] * (1.0 - g)

    return [amp * v for v in out[:n]]


def _mix(*tracks):
    total = [0.0] * max(len(t) for t in tracks)
    for t in tracks:
        for i, v in enumerate(t):
            total[i] += v
    return total


def _ramp_env(n, attack_s, release_s):
    """Raised-cosine attack/release envelope: exactly zero at both edges,
    so pad segments concatenate click-free and the loop wraps seamlessly."""
    env = [0.0] * n
    a = max(1, int(attack_s * SAMPLE_RATE))
    r = max(1, int(release_s * SAMPLE_RATE))
    for i in range(n):
        g = 1.0
        if i < a:
            g = 0.5 * (1.0 - math.cos(math.pi * i / a))
        elif i > n - r:
            j = n - i
            g = 0.5 * (1.0 - math.cos(math.pi * j / r))
        env[i] = g
    return env


def _pad_note(freq, amp, start_s, dur_s, attack_s=0.45, release_s=0.45):
    """One pad voice over a segment, zero at the segment edges."""
    n = int(dur_s * SAMPLE_RATE)
    sine = _sine(n, freq, amp)
    env = _ramp_env(n, attack_s, release_s)
    return [s * e for s, e in zip(sine, env)], start_s


def _render_academy_loop():
    """Actual music: C - Am - F - G progression, warm pads, bell arpeggio.
    All content in laptop-audible ranges (130-800 Hz); zero at loop edges."""
    buf = [0.0] * int(LOOP_SECONDS * SAMPLE_RATE)
    seg = LOOP_SECONDS / 4.0

    chords = [
        ([261.63, 329.63, 392.00], 130.81),   # C   (pads, sub root)
        ([220.00, 261.63, 329.63], 110.00),   # Am
        ([174.61, 220.00, 261.63], 87.31),    # F
        ([196.00, 246.94, 293.66], 98.00),    # G
    ]

    for ci, (pads, sub) in enumerate(chords):
        t0 = ci * seg
        for f in pads:
            voice, at = _pad_note(f, 0.55, t0, seg)
            buf = _place(buf, voice, at)
        sub_voice, at = _pad_note(sub, 0.50, t0, seg, attack_s=0.6, release_s=0.6)
        buf = _place(buf, sub_voice, at)

        # Gentle bell arpeggio: root, third, fifth (one octave up), octave root
        bells = [pads[0] * 2, pads[1] * 2, pads[2] * 2, pads[0] * 4]
        onsets = [0.50, 1.25, 2.00, 2.40]
        for f, dt in zip(bells, onsets):
            buf = _place(buf, tone(f, 0.5, decay=6.0, amp=0.30), t0 + dt)

    buf = buf[:int(LOOP_SECONDS * SAMPLE_RATE)]  # exact loop-length guarantee
    return _normalize(buf, LOOP_PEAK)


def _render_lab_loop():
    """Darker music: Dm - Bb - Gm - A progression, lower bells, sparser rhythm.
    Still laptop-audible (110-440 Hz); zero at loop edges."""
    buf = [0.0] * int(LOOP_SECONDS * SAMPLE_RATE)
    seg = LOOP_SECONDS / 4.0

    chords = [
        ([146.83, 174.61, 220.00], 73.42),    # Dm
        ([116.54, 146.83, 174.61], 58.27),    # Bb
        ([98.00, 116.54, 146.83], 49.00),     # Gm
        ([110.00, 138.59, 164.81], 55.00),    # A  (harmonic-minor tension)
    ]

    for ci, (pads, sub) in enumerate(chords):
        t0 = ci * seg
        for f in pads:
            voice, at = _pad_note(f, 0.60, t0, seg, attack_s=0.6, release_s=0.6)
            buf = _place(buf, voice, at)
        sub_voice, at = _pad_note(sub, 0.45, t0, seg, attack_s=0.8, release_s=0.8)
        buf = _place(buf, sub_voice, at)

        # Sparser, lower bells: root, fifth, octave root
        bells = [pads[0] * 2, pads[2] * 2, pads[0] * 4]
        onsets = [0.75, 1.75, 2.40]
        for f, dt in zip(bells, onsets):
            buf = _place(buf, tone(f, 0.5, decay=5.0, amp=0.32), t0 + dt)

    buf = buf[:int(LOOP_SECONDS * SAMPLE_RATE)]  # exact loop-length guarantee
    return _normalize(buf, LOOP_PEAK)


# =========================================================
# EVENT SOUND RECIPES - "Cyber Laboratory" identity
# Register discipline (spec section 3):
#   mechanical = informative, never punitive
#   feedback   = reflecting the student's result, gentle both ways
#   reward     = warm
# =========================================================

def _academy_opened():
    base = tone(523.25, 0.40, decay=7.0)
    return _place(base, tone(659.25, 0.30, decay=7.0), 0.12)


def _lab_opened():
    base = tone(55.0, 0.55, decay=3.5)
    base = _place(base, tone(110.0, 0.50, kind="square", decay=3.0, amp=0.4), 0.02)
    return _place(base, tone(220.0, 0.35, sweep_to=440.0, decay=5.0, amp=0.5), 0.18)


def _experiment_selected():
    return tone(1500.0, 0.05, decay=30.0, amp=0.8)


def _experiment_started():
    return tone(220.0, 0.24, sweep_to=880.0, decay=4.0)


def _structural_rejection():
    # Layer 1: bright double scanner blip - the parser reporting, not an alarm
    base = tone(1250.0, 0.07, kind="square", decay=18.0, amp=0.8)
    return _place(base, tone(1250.0, 0.07, kind="square", decay=18.0, amp=0.8), 0.13)


def _cryptographic_rejection():
    # Layer 2: lower, thicker dual tone - audibly deeper than Layer 1
    base = tone(175.0, 0.48, decay=5.0)
    return _place(base, tone(233.0, 0.44, decay=5.0, amp=0.85), 0.0)


def _control_group_success():
    base = tone(440.00, 0.30, decay=7.0)
    base = _place(base, tone(554.37, 0.28, decay=7.0), 0.10)
    return _place(base, tone(659.25, 0.30, decay=6.0), 0.20)


def _prediction_recorded():
    return tone(880.0, 0.18, decay=10.0)


def _prediction_correct():
    base = tone(523.25, 0.16, decay=8.0)
    return _place(base, tone(659.25, 0.22, decay=8.0), 0.14)


def _prediction_incorrect():
    # Gentle two-note descent: "your hypothesis didn't match the evidence"
    base = tone(392.00, 0.18, decay=7.0, amp=0.8)
    return _place(base, tone(311.13, 0.26, decay=6.0, amp=0.8), 0.16)


def _matching_correct():
    return tone(987.77, 0.12, decay=12.0)


def _matching_incorrect():
    base = tone(349.23, 0.14, decay=8.0, amp=0.6)
    return _place(base, tone(293.66, 0.18, decay=7.0, amp=0.6), 0.12)


def _question_correct():
    base = tone(587.33, 0.14, decay=8.0)
    return _place(base, tone(739.99, 0.20, decay=8.0), 0.12)


def _question_incorrect():
    base = tone(440.00, 0.16, decay=7.0, amp=0.7)
    return _place(base, tone(369.99, 0.22, decay=6.0, amp=0.7), 0.14)


def _challenge_completed():
    base = tone(523.25, 0.28, decay=6.0)
    base = _place(base, tone(659.25, 0.26, decay=6.0), 0.11)
    return _place(base, tone(783.99, 0.30, decay=5.0), 0.22)


def _xp_awarded():
    base = tone(1567.98, 0.09, decay=14.0, amp=0.8)
    return _place(base, tone(2093.00, 0.12, decay=12.0, amp=0.8), 0.08)


EVENT_SOUNDS = {
    "academy_opened": _academy_opened,
    "lab_opened": _lab_opened,
    "experiment_selected": _experiment_selected,
    "experiment_started": _experiment_started,
    "structural_rejection": _structural_rejection,
    "cryptographic_rejection": _cryptographic_rejection,
    "control_group_success": _control_group_success,
    "prediction_recorded": _prediction_recorded,
    "prediction_correct": _prediction_correct,
    "prediction_incorrect": _prediction_incorrect,
    "matching_correct": _matching_correct,
    "matching_incorrect": _matching_incorrect,
    "question_correct": _question_correct,
    "question_incorrect": _question_incorrect,
    "challenge_completed": _challenge_completed,
    "xp_awarded": _xp_awarded,
}

LOOP_SOUNDS = {
    "academy_loop": _render_academy_loop,
    "lab_loop": _render_lab_loop,
}


# =========================================================
# GENERIC PROGRESSION ENGINE + THEME REGISTRY (6C.2-6C.4)
# Each theme is a folder drop: 16 event recipes + 2 loops + metadata.
# cyber_lab (above) keeps its approved hand-tuned recipes unchanged.
# =========================================================

def _progression_loop(chords, bell_spec, pad_attack, pad_release, pad_amp,
                      sub_amp, sub_attack=None, thump_spec=None):
    """Parameterized musical loop renderer.
    bell_spec(pads) -> list of (freq, onset_s, amp, decay, attack, kind)
    thump_spec      -> list of (freq, onset_s, amp, decay) low pulses, or None
    """
    buf = [0.0] * int(LOOP_SECONDS * SAMPLE_RATE)
    seg = LOOP_SECONDS / len(chords)

    for ci, (pads, sub) in enumerate(chords):
        t0 = ci * seg
        for f in pads:
            voice, at = _pad_note(f, pad_amp, t0, seg,
                                  attack_s=pad_attack, release_s=pad_release)
            buf = _place(buf, voice, at)
        sv, at = _pad_note(sub, sub_amp, t0, seg,
                           attack_s=sub_attack or pad_attack,
                           release_s=sub_attack or pad_release)
        buf = _place(buf, sv, at)

        for freq, onset, amp, decay, attack, kind in bell_spec(pads):
            buf = _place(buf, tone(freq, 0.5, kind=kind, decay=decay,
                                   amp=amp, attack=attack), t0 + onset)

        if thump_spec:
            for freq, onset, amp, decay in thump_spec:
                buf = _place(buf, tone(freq, 0.15, decay=decay, amp=amp), t0 + onset)

    buf = buf[:int(LOOP_SECONDS * SAMPLE_RATE)]  # exact loop-length guarantee
    return _normalize(buf, LOOP_PEAK)


# ---------------- Theme 2: premium_minimal (6C.2) ----------------
# Apple/Linear-like: rounded soft sines, slow attacks, nothing sharp.

def _pm_events():
    def soft(f, dur, decay=5.0, amp=1.0):
        return tone(f, dur, decay=decay, amp=amp, attack=0.05)
    def pair(f1, f2, dur, gap, decay=5.0, amp=1.0):
        return _place(soft(f1, dur, decay, amp), soft(f2, dur, decay, amp), gap)
    return {
        "academy_opened": lambda: pair(523.25, 659.25, 0.32, 0.15),
        "lab_opened": lambda: pair(392.00, 493.88, 0.38, 0.18),
        "experiment_selected": lambda: soft(1318.51, 0.05, decay=22, amp=0.6),
        "experiment_started": lambda: pair(440.00, 554.37, 0.22, 0.12),
        "structural_rejection": lambda: pair(987.77, 987.77, 0.06, 0.12, decay=14, amp=0.7),
        "cryptographic_rejection": lambda: _place(soft(261.63, 0.45), soft(311.13, 0.42, amp=0.85), 0.0),
        "control_group_success": lambda: _place(pair(523.25, 659.25, 0.26, 0.12),
                                                soft(783.99, 0.26), 0.24),
        "prediction_recorded": lambda: soft(783.99, 0.15),
        "prediction_correct": lambda: pair(587.33, 739.99, 0.18, 0.14),
        "prediction_incorrect": lambda: pair(493.88, 440.00, 0.18, 0.16, amp=0.8),
        "matching_correct": lambda: soft(880.00, 0.12),
        "matching_incorrect": lambda: pair(415.30, 369.99, 0.14, 0.14, amp=0.7),
        "question_correct": lambda: pair(659.26, 783.99, 0.16, 0.14),
        "question_incorrect": lambda: pair(493.88, 440.00, 0.16, 0.16, amp=0.8),
        "challenge_completed": lambda: _place(pair(523.25, 659.25, 0.24, 0.12),
                                              soft(783.99, 0.26), 0.24),
        "xp_awarded": lambda: soft(1174.66, 0.10, amp=0.8),
    }


def _pm_academy_loop():
    chords = [
        ([261.63, 329.63, 392.00, 493.88], 130.81),  # Cmaj7
        ([220.00, 261.63, 329.63, 392.00], 110.00),  # Am7
        ([174.61, 220.00, 261.63, 329.63], 87.31),   # Fmaj7
        ([196.00, 246.94, 293.66, 392.00], 98.00),   # G6
    ]
    def bells(pads):
        return [(pads[1] * 2, 0.90, 0.20, 4.0, 0.06, "sine"),
                (pads[3] * 1.0, 2.30, 0.14, 4.0, 0.06, "sine")]
    return _progression_loop(chords, bells, pad_attack=0.8, pad_release=0.8,
                             pad_amp=0.55, sub_amp=0.45)


def _pm_lab_loop():
    chords = [
        ([246.94, 293.66, 349.23], 123.47),          # Bm
        ([207.65, 246.94, 311.13], 103.83),          # Gbm
        ([220.00, 261.63, 329.63], 110.00),          # Am
        ([233.08, 277.18, 349.23], 116.54),          # Bbm
    ]
    def bells(pads):
        return [(pads[0] * 2, 1.10, 0.18, 4.0, 0.07, "sine"),
                (pads[2] * 1.0, 2.50, 0.12, 4.0, 0.07, "sine")]
    return _progression_loop(chords, bells, pad_attack=0.9, pad_release=0.9,
                             pad_amp=0.55, sub_amp=0.42)


# ---------------- Theme 3: scientific (6C.3) ----------------
# Clean analytical instrument: pure precise sines, calibration beeps.

def _sc_events():
    def ping(f, dur, decay=6.0, amp=1.0):
        return tone(f, dur, decay=decay, amp=amp, attack=0.002)
    def pair(f1, f2, dur, gap, decay=6.0, amp=1.0):
        return _place(ping(f1, dur, decay, amp), ping(f2, dur, decay, amp), gap)
    return {
        "academy_opened": lambda: pair(659.26, 880.00, 0.26, 0.14),
        "lab_opened": lambda: _place(ping(220.00, 0.45, decay=4), ping(440.00, 0.30), 0.20),
        "experiment_selected": lambda: ping(2000.00, 0.03, decay=30, amp=0.55),
        "experiment_started": lambda: tone(440.00, 0.22, sweep_to=1320.00, decay=5, attack=0.002),
        "structural_rejection": lambda: pair(1760.00, 1760.00, 0.05, 0.11, decay=16, amp=0.7),
        "cryptographic_rejection": lambda: _place(ping(220.00, 0.40), ping(277.18, 0.38, amp=0.85), 0.0),
        "control_group_success": lambda: _place(pair(659.26, 880.00, 0.22, 0.10),
                                                ping(1046.50, 0.22), 0.20),
        "prediction_recorded": lambda: ping(987.77, 0.12),
        "prediction_correct": lambda: pair(783.99, 987.77, 0.14, 0.12),
        "prediction_incorrect": lambda: pair(659.26, 523.25, 0.16, 0.15, amp=0.75),
        "matching_correct": lambda: ping(1244.51, 0.10),
        "matching_incorrect": lambda: pair(587.33, 523.25, 0.13, 0.13, amp=0.7),
        "question_correct": lambda: pair(880.00, 1046.50, 0.14, 0.12),
        "question_incorrect": lambda: pair(659.26, 587.33, 0.14, 0.14, amp=0.75),
        "challenge_completed": lambda: _place(pair(659.26, 783.99, 0.20, 0.11),
                                              ping(987.77, 0.22), 0.22),
        "xp_awarded": lambda: ping(1975.53, 0.07, amp=0.8),
    }


def _sc_academy_loop():
    chords = [
        ([261.63, 329.63, 392.00], 130.81),          # C
        ([196.00, 246.94, 293.66], 98.00),           # G
        ([220.00, 261.63, 329.63], 110.00),          # Am
        ([174.61, 220.00, 261.63], 87.31),           # F
    ]
    def ticks(pads):
        return [(pads[0] * 2, 0.50, 0.15, 12.0, 0.002, "sine"),
                (pads[0] * 2, 1.50, 0.12, 12.0, 0.002, "sine"),
                (pads[0] * 2, 2.50, 0.15, 12.0, 0.002, "sine")]
    return _progression_loop(chords, ticks, pad_attack=0.5, pad_release=0.5,
                             pad_amp=0.50, sub_amp=0.40)


def _sc_lab_loop():
    chords = [
        ([146.83, 174.61, 220.00], 73.42),           # Dm
        ([164.81, 196.00, 246.94], 82.41),           # Em
        ([130.81, 164.81, 196.00], 65.41),           # C low
        ([155.56, 185.00, 233.08], 77.78),           # Dbm
    ]
    def ticks(pads):
        return [(pads[0] * 2, 0.75, 0.16, 10.0, 0.002, "sine"),
                (pads[0] * 2, 1.75, 0.12, 10.0, 0.002, "sine"),
                (pads[0] * 2, 2.50, 0.16, 10.0, 0.002, "sine")]
    return _progression_loop(chords, ticks, pad_attack=0.55, pad_release=0.55,
                             pad_amp=0.50, sub_amp=0.38)


# ---------------- Theme 4: cyberpunk (6C.4) ----------------
# Neon synthwave: band-limited square edge, sub thumps, dramatic sweeps.

def _cp_events():
    def edge(f, dur, decay=6.0, amp=0.8):
        return tone(f, dur, kind="square", decay=decay, amp=amp)
    def pair(f1, f2, dur, gap, decay=6.0, amp=0.8):
        return _place(edge(f1, dur, decay, amp), edge(f2, dur, decay, amp), gap)
    return {
        "academy_opened": lambda: pair(261.63, 392.00, 0.28, 0.14, amp=0.6),
        "lab_opened": lambda: _place(_place(edge(49.00, 0.55, decay=3.5),
                                            tone(110.00, 0.35, sweep_to=440.00, decay=5, amp=0.6), 0.18),
                                     edge(987.77, 0.10, decay=12, amp=0.5), 0.40),
        "experiment_selected": lambda: edge(2500.00, 0.035, decay=30, amp=0.5),
        "experiment_started": lambda: tone(165.00, 0.22, kind="square", sweep_to=990.00, decay=4.5, amp=0.75),
        "structural_rejection": lambda: pair(1567.98, 1567.98, 0.06, 0.12, decay=16, amp=0.6),
        "cryptographic_rejection": lambda: _place(_place(edge(138.59, 0.45, decay=5),
                                                         edge(174.61, 0.42, decay=5, amp=0.85), 0.0),
                                                  edge(46.25, 0.45, decay=4, amp=0.6), 0.0),
        "control_group_success": lambda: _place(pair(440.00, 554.37, 0.24, 0.10, amp=0.6),
                                                edge(659.26, 0.26, amp=0.6), 0.20),
        "prediction_recorded": lambda: edge(987.77, 0.15),
        "prediction_correct": lambda: pair(659.26, 987.77, 0.16, 0.14),
        "prediction_incorrect": lambda: pair(554.37, 415.30, 0.18, 0.16, amp=0.7),
        "matching_correct": lambda: edge(1318.51, 0.10),
        "matching_incorrect": lambda: pair(493.88, 392.00, 0.14, 0.14, amp=0.7),
        "question_correct": lambda: pair(739.99, 987.77, 0.15, 0.12),
        "question_incorrect": lambda: pair(587.33, 462.25, 0.16, 0.15, amp=0.7),
        "challenge_completed": lambda: _place(pair(523.25, 659.26, 0.22, 0.11, amp=0.7),
                                              edge(783.99, 0.28, amp=0.7), 0.22),
        "xp_awarded": lambda: tone(1318.51, 0.12, sweep_to=2637.02, decay=10, amp=0.7),
    }


def _cp_academy_loop():
    chords = [
        ([220.00, 261.63, 329.63], 110.00),          # Am
        ([174.61, 220.00, 261.63], 87.31),           # F
        ([261.63, 329.63, 392.00], 130.81),          # C
        ([164.81, 207.65, 246.94], 82.41),           # E
    ]
    def bells(pads):
        return [(pads[0] * 2, 0.60, 0.24, 5.0, 0.004, "square"),
                (pads[2] * 2, 1.80, 0.20, 5.0, 0.004, "square")]
    thumps = [(49.00, 0.00, 0.5, 7.0), (49.00, 1.20, 0.4, 7.0), (49.00, 2.40, 0.5, 7.0)]
    return _progression_loop(chords, bells, pad_attack=0.4, pad_release=0.4,
                             pad_amp=0.55, sub_amp=0.45, thump_spec=thumps)


def _cp_lab_loop():
    chords = [
        ([185.00, 220.00, 277.18], 92.50),           # F#m
        ([146.83, 174.61, 220.00], 73.42),           # Dm
        ([155.56, 196.00, 233.08], 77.78),           # Ebm
        ([138.59, 174.61, 207.65], 69.30),           # Cm
    ]
    def bells(pads):
        return [(pads[0] * 2, 0.75, 0.26, 4.5, 0.004, "square"),
                (pads[1] * 4, 1.90, 0.18, 4.5, 0.004, "square")]
    thumps = [(43.65, 0.00, 0.55, 7.0), (43.65, 1.50, 0.45, 7.0), (43.65, 2.55, 0.55, 7.0)]
    return _progression_loop(chords, bells, pad_attack=0.45, pad_release=0.45,
                             pad_amp=0.55, sub_amp=0.45, thump_spec=thumps)


# ---------------- The registry ----------------

THEMES = {
    "cyber_lab": {
        "events": lambda: EVENT_SOUNDS,
        "loops": lambda: LOOP_SOUNDS,
        "description": "Cyber Laboratory - synthesized terminal identity: "
                       "bright scanner blips, chord-progression ambience.",
        "version": "1.1.0",
    },
    "premium_minimal": {
        "events": _pm_events,
        "loops": lambda: {"academy_loop": _pm_academy_loop, "lab_loop": _pm_lab_loop},
        "description": "Premium Minimal - rounded soft sines, slow attacks, "
                       "quiet modern-software aesthetic.",
        "version": "1.0.0",
    },
    "scientific": {
        "events": _sc_events,
        "loops": lambda: {"academy_loop": _sc_academy_loop, "lab_loop": _sc_lab_loop},
        "description": "Scientific Instrument - pure precise calibration beeps, "
                       "measured tick patterns, analytical feel.",
        "version": "1.0.0",
    },
    "cyberpunk": {
        "events": _cp_events,
        "loops": lambda: {"academy_loop": _cp_academy_loop, "lab_loop": _cp_lab_loop},
        "description": "Cyberpunk - neon synthwave: square-edge tones, sub "
                       "thumps, dramatic sweeps.",
        "version": "1.0.0",
    },
}


# =========================================================
# THEME GENERATION
# =========================================================

def render_theme(theme_name, out_dir=None):
    """Renders one theme from the registry: every event sound + loops + manifest.
    Deterministic: identical inputs produce byte-identical output."""
    if theme_name not in THEMES:
        raise ValueError(f"Unknown theme '{theme_name}'. Available: {sorted(THEMES)}")
    spec = THEMES[theme_name]
    events = spec["events"]()
    loops = spec["loops"]()

    themes_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "themes")
    out_dir = out_dir or os.path.join(themes_root, theme_name)
    os.makedirs(out_dir, exist_ok=True)

    written = []

    for event in sorted(events):
        samples = _fade_edges(_normalize(events[event](), SFX_PEAK))
        path = os.path.join(out_dir, event + ".wav")
        _write_wav(path, samples)
        written.append(event + ".wav")

    for loop in sorted(loops):
        path = os.path.join(out_dir, loop + ".wav")
        _write_wav(path, loops[loop]())
        written.append(loop + ".wav")

    manifest = {
        "description": spec["description"],
        "events": sorted(events.keys()),
        "generated_by": "python -m audio.make_sounds",
        "license": "Generated in-house by Cryptix make_sounds.py (pure Python, "
                   "deterministic). No third-party assets.",
        "loops": sorted(loops.keys()),
        "name": theme_name,
        "register_notes": "mechanical=informative-never-punitive; "
                          "feedback=reflecting-the-students-result; reward=warm",
        "sample_rate": SAMPLE_RATE,
        "version": spec["version"],
    }

    manifest_path = os.path.join(out_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, sort_keys=True, ensure_ascii=False)
        f.write("\n")

    return {"dir": out_dir, "files": written, "manifest": manifest}


def render_all_themes(themes_dir=None):
    """Regenerates every registered theme (the single reproducible entry point)."""
    themes_dir = themes_dir or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "themes")
    results = {}
    for theme_name in sorted(THEMES):
        results[theme_name] = render_theme(theme_name, os.path.join(themes_dir, theme_name))
    return results


def generate_theme(out_dir=None):
    """Backward-compatible wrapper: renders the default cyber_lab theme."""
    return render_theme(THEME_NAME, out_dir)


if __name__ == "__main__":
    results = render_all_themes()
    for theme_name, result in results.items():
        print(f"Cryptix audio theme '{theme_name}' -> {result['dir']}")
        for name in result["files"]:
            size = os.path.getsize(os.path.join(result["dir"], name))
            print(f"  {name:<32} {size:>8,} bytes")
        print(f"  {'manifest.json':<32} written")
