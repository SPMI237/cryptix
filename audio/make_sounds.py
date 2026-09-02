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
    """One enveloped note. kind: 'sine' | 'square' | 'triangle'."""
    n = int(duration * SAMPLE_RATE)
    if sweep_to is not None:
        raw = _sweep(n, freq, sweep_to, amp)
    elif kind == "square":
        raw = _square(n, freq, amp)
    elif kind == "triangle":
        raw = _triangle(n, freq, amp)
    else:
        raw = _sine(n, freq, amp)
    env = _envelope(n, attack, decay)
    return [s * e for s, e in zip(raw, env)]


def _triangle(num_samples, freq, amplitude=1.0, harmonics=5):
    """Triangle wave: odd harmonics falling off at 1/k^2 - warm and hollow."""
    out = [0.0] * num_samples
    k = 1
    sign = 1.0
    while k <= harmonics * 2:
        a = amplitude * sign / (k * k)
        w = TWO_PI * freq * k / SAMPLE_RATE
        for i in range(num_samples):
            out[i] += a * math.sin(w * i)
        k += 2
        sign = -sign
    return out


def noise_hit(duration, decay=18.0, amp=1.0, cutoff_hz=8000, seed=99):
    """Seeded noise percussion burst (hats/ticks). Deterministic per seed."""
    n = int(duration * SAMPLE_RATE)
    rng = random.Random(seed)
    raw = [rng.uniform(-1.0, 1.0) for _ in range(n)]
    a = 1.0 - math.exp(-TWO_PI * cutoff_hz / SAMPLE_RATE)
    y = 0.0
    lp = []
    for x in raw:
        y += a * (x - y)
        lp.append(y)
    m = max((abs(v) for v in lp), default=0.0) or 1.0
    env = _envelope(n, 0.001, decay)
    return [s / m * e * amp for s, e in zip(lp, env)]


def fm_bell(freq, duration, ratio=3.5, index=3.0, decay=7.0, amp=1.0):
    """FM metallic bell: carrier modulated at an inharmonic ratio with a
    decaying modulation index - bright attack, clangorous tail."""
    n = int(duration * SAMPLE_RATE)
    wc = TWO_PI * freq / SAMPLE_RATE
    wm = TWO_PI * freq * ratio / SAMPLE_RATE
    out = []
    for i in range(n):
        t = i / SAMPLE_RATE
        idx = index * math.exp(-decay * 0.7 * t)
        out.append(amp * math.sin(wc * i + idx * math.sin(wm * i)))
    env = _envelope(n, 0.002, decay)
    return [s * e for s, e in zip(out, env)]


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

        for spec in bell_spec(pads):
            freq, onset, amp, decay, attack, kind = spec
            if kind == "hat":
                snd = noise_hit(0.03, decay=decay, amp=amp, cutoff_hz=9000,
                                seed=4242 + ci * 13 + int(onset * 10))
            elif kind == "fm":
                snd = fm_bell(freq, 0.5, decay=decay, amp=amp)
            else:
                snd = tone(freq, 0.5, kind=kind, decay=decay, amp=amp, attack=attack)
            buf = _place(buf, snd, t0 + onset)

        if thump_spec:
            for freq, onset, amp, decay in thump_spec:
                buf = _place(buf, tone(freq, 0.15, decay=decay, amp=amp), t0 + onset)

    buf = buf[:int(LOOP_SECONDS * SAMPLE_RATE)]  # exact loop-length guarantee
    return _normalize(buf, LOOP_PEAK)


# ---------------- Theme 2: premium_minimal (6C.2) ----------------
# Apple/Linear-like: warm TRIANGLE timbre, felt-soft attacks, SPARSE single
# gestures (often one note where other themes play two or three).

def _pm_events():
    def tap(f, dur, decay=5.0, amp=1.0):
        return tone(f, dur, kind="triangle", decay=decay, amp=amp, attack=0.02)
    def soft2(f1, f2, dur, gap, decay=5.0, amp=1.0):
        return _place(tap(f1, dur, decay, amp), tap(f2, dur, decay, amp), gap)
    return {
        "academy_opened": lambda: _place(tap(261.63, 0.50, decay=4, amp=0.9), tap(392.00, 0.40, decay=4), 0.05),
        "lab_opened": lambda: tap(174.61, 0.55, decay=3.5, amp=0.9),
        "experiment_selected": lambda: tap(659.26, 0.04, decay=35, amp=0.45),
        "experiment_started": lambda: soft2(329.63, 440.00, 0.16, 0.12, amp=0.8),
        "structural_rejection": lambda: tap(987.77, 0.06, decay=20, amp=0.5),
        "cryptographic_rejection": lambda: _place(tap(220.00, 0.45, decay=4), tap(261.63, 0.42, decay=4, amp=0.85), 0.0),
        "control_group_success": lambda: _place(_place(tap(392.00, 0.24, decay=5), tap(493.88, 0.22, decay=5), 0.12), tap(587.33, 0.24, decay=4), 0.24),
        "prediction_recorded": lambda: tap(659.26, 0.14),
        "prediction_correct": lambda: soft2(523.25, 659.26, 0.16, 0.14),
        "prediction_incorrect": lambda: soft2(440.00, 392.00, 0.16, 0.16, amp=0.7),
        "matching_correct": lambda: tap(880.00, 0.10, amp=0.8),
        "matching_incorrect": lambda: soft2(392.00, 329.63, 0.13, 0.14, amp=0.6),
        "question_correct": lambda: soft2(587.33, 739.99, 0.15, 0.13),
        "question_incorrect": lambda: soft2(440.00, 392.00, 0.15, 0.15, amp=0.7),
        "challenge_completed": lambda: _place(_place(tap(523.25, 0.22, decay=5), tap(659.26, 0.20, decay=5), 0.11), tap(783.99, 0.24, decay=4), 0.22),
        "xp_awarded": lambda: tap(1046.50, 0.09, amp=0.75),
    }


def _pm_academy_loop():
    chords = [
        ([261.63, 329.63, 392.00, 493.88], 130.81),  # Cmaj7
        ([220.00, 261.63, 329.63, 392.00], 110.00),  # Am7
        ([174.61, 220.00, 261.63, 329.63], 87.31),   # Fmaj7
        ([196.00, 246.94, 293.66, 392.00], 98.00),   # G6
    ]
    def sparse(pads):
        return [(pads[1] * 2, 1.40, 0.22, 3.5, 0.08, "triangle")]
    return _progression_loop(chords, sparse, pad_attack=0.9, pad_release=0.9,
                             pad_amp=0.40, sub_amp=0.50)


def _pm_lab_loop():
    chords = [
        ([246.94, 293.66, 349.23], 123.47),          # Bm
        ([207.65, 246.94, 311.13], 103.83),          # Gbm
        ([220.00, 261.63, 329.63], 110.00),          # Am
        ([233.08, 277.18, 349.23], 116.54),          # Bbm
    ]
    def sparse(pads):
        return [(pads[0] * 2, 1.80, 0.18, 3.5, 0.09, "triangle")]
    return _progression_loop(chords, sparse, pad_attack=1.0, pad_release=1.0,
                             pad_amp=0.40, sub_amp=0.46)


# ---------------- Theme 3: scientific (6C.3) ----------------
# Analytical instrument: crystal SINE pings with long clean decays, Geiger
# noise ticks, and measurement frequency sweeps. High, precise, clinical.

def _sc_events():
    def ping(f, dur, decay=9.0, amp=1.0):
        return tone(f, dur, decay=decay, amp=amp, attack=0.001)
    def ping2(f1, f2, dur, gap, decay=9.0, amp=1.0):
        return _place(ping(f1, dur, decay, amp), ping(f2, dur, decay, amp), gap)
    def tick(seed=7):
        return noise_hit(0.018, decay=40, amp=0.5, cutoff_hz=9000, seed=seed)
    return {
        "academy_opened": lambda: ping2(880.00, 1318.51, 0.34, 0.15),
        "lab_opened": lambda: _place(ping(220.00, 0.55, decay=4), tick(11), 0.30),
        "experiment_selected": lambda: tick(3),
        "experiment_started": lambda: tone(440.00, 0.26, sweep_to=1760.00, decay=5, attack=0.001),
        "structural_rejection": lambda: _place(tick(5), tick(5), 0.12),
        "cryptographic_rejection": lambda: _place(ping(196.00, 0.55, decay=5), ping(246.94, 0.50, decay=5, amp=0.85), 0.0),
        "control_group_success": lambda: _place(ping2(659.26, 880.00, 0.24, 0.10), ping(1046.50, 0.24), 0.20),
        "prediction_recorded": lambda: ping(987.77, 0.14),
        "prediction_correct": lambda: ping2(783.99, 987.77, 0.16, 0.12),
        "prediction_incorrect": lambda: ping2(659.26, 523.25, 0.17, 0.15, amp=0.75),
        "matching_correct": lambda: ping(1244.51, 0.12),
        "matching_incorrect": lambda: ping2(587.33, 523.25, 0.14, 0.13, amp=0.7),
        "question_correct": lambda: ping2(880.00, 1046.50, 0.15, 0.12),
        "question_incorrect": lambda: ping2(659.26, 587.33, 0.15, 0.14, amp=0.75),
        "challenge_completed": lambda: _place(ping2(659.26, 783.99, 0.20, 0.10), ping(987.77, 0.26), 0.20),
        "xp_awarded": lambda: ping(1975.53, 0.09, amp=0.8),
    }


def _sc_academy_loop():
    chords = [
        ([261.63, 329.63, 392.00], 130.81),          # C
        ([196.00, 246.94, 293.66], 98.00),           # G
        ([220.00, 261.63, 329.63], 110.00),          # Am
        ([174.61, 220.00, 261.63], 87.31),           # F
    ]
    def grid(pads):
        out = []
        for k in range(6):  # metronome grid: a quiet tick every 0.5 s
            out.append((0, 0.50 * k, 0.11 if k % 3 else 0.16, 30, 0.001, "hat"))
        out.append((pads[2] * 4, 1.00, 0.14, 8.0, 0.001, "sine"))  # one crystal ping
        return out
    return _progression_loop(chords, grid, pad_attack=0.5, pad_release=0.5,
                             pad_amp=0.34, sub_amp=0.38)


def _sc_lab_loop():
    chords = [
        ([146.83, 174.61, 220.00], 73.42),           # Dm
        ([164.81, 196.00, 246.94], 82.41),           # Em
        ([130.81, 164.81, 196.00], 65.41),           # C low
        ([155.56, 185.00, 233.08], 77.78),           # Dbm
    ]
    def grid(pads):
        out = []
        for k in range(4):  # lazier grid: every 0.75 s
            out.append((0, 0.75 * k, 0.12 if k % 2 else 0.17, 28, 0.001, "hat"))
        out.append((pads[0] * 4, 1.50, 0.15, 7.0, 0.001, "sine"))
        return out
    return _progression_loop(chords, grid, pad_attack=0.55, pad_release=0.55,
                             pad_amp=0.34, sub_amp=0.36)


# ---------------- Theme 4: cyberpunk (6C.4) ----------------
# Neon synthwave: FM METALLIC bells, NOISE hi-hats, SUB-BASS slides, fast
# rising square arpeggios. Rhythmic, punchy, dramatic.

def _cp_events():
    def bell(f, dur=0.30, decay=8.0, amp=0.9):
        return fm_bell(f, dur, ratio=3.5, index=3.2, decay=decay, amp=amp)
    def arp(*freqs, dur=0.11, gap=0.07, amp=0.8):
        base = tone(freqs[0], dur, kind="square", decay=9, amp=amp)
        for i, f in enumerate(freqs[1:], start=1):
            base = _place(base, tone(f, dur, kind="square", decay=9, amp=amp), i * gap)
        return base
    def hat(seed=21, amp=0.55):
        return noise_hit(0.025, decay=35, amp=amp, cutoff_hz=9500, seed=seed)
    def sub(f=49.00, dur=0.30, amp=0.8, decay=7.0):
        return tone(f, dur, decay=decay, amp=amp, attack=0.002)
    return {
        "academy_opened": lambda: _place(bell(523.25, 0.32), sub(65.41, 0.30, 0.6), 0.0),
        "lab_opened": lambda: _place(_place(tone(110.00, 0.40, kind="square", sweep_to=55.00, decay=5, amp=0.85), bell(220.00, 0.30, amp=0.6), 0.12), hat(31, 0.5), 0.30),
        "experiment_selected": lambda: _place(hat(13, 0.5), tone(2500.00, 0.03, kind="square", decay=30, amp=0.4), 0.0),
        "experiment_started": lambda: arp(220.00, 329.63, 440.00, 659.26, dur=0.09, gap=0.05),
        "structural_rejection": lambda: _place(fm_bell(1567.98, 0.07, ratio=2.0, index=2.0, decay=18, amp=0.7), fm_bell(1567.98, 0.07, ratio=2.0, index=2.0, decay=18, amp=0.7), 0.12),
        "cryptographic_rejection": lambda: _place(_place(bell(138.59, 0.42, decay=5), bell(174.61, 0.40, decay=5, amp=0.85), 0.0), sub(46.25, 0.42, 0.7), 0.0),
        "control_group_success": lambda: _place(arp(440.00, 554.37, 659.26, dur=0.10, gap=0.08, amp=0.75), sub(55.00, 0.26, 0.6), 0.0),
        "prediction_recorded": lambda: bell(987.77, 0.16, decay=10, amp=0.8),
        "prediction_correct": lambda: arp(659.26, 987.77, dur=0.10, gap=0.07),
        "prediction_incorrect": lambda: _place(tone(554.37, 0.16, kind="square", decay=8, amp=0.7), tone(415.30, 0.18, kind="square", decay=7, amp=0.7), 0.15),
        "matching_correct": lambda: bell(1318.51, 0.12, decay=11, amp=0.8),
        "matching_incorrect": lambda: _place(tone(493.88, 0.13, kind="square", decay=9, amp=0.7), tone(392.00, 0.15, kind="square", decay=8, amp=0.7), 0.12),
        "question_correct": lambda: arp(739.99, 987.77, dur=0.10, gap=0.06),
        "question_incorrect": lambda: _place(tone(587.33, 0.14, kind="square", decay=8, amp=0.7), tone(462.25, 0.16, kind="square", decay=7, amp=0.7), 0.14),
        "challenge_completed": lambda: _place(_place(arp(523.25, 659.26, 783.99, dur=0.11, gap=0.09, amp=0.85), sub(49.00, 0.30, 0.8), 0.0), hat(77, 0.6), 0.28),
        "xp_awarded": lambda: tone(1318.51, 0.14, kind="square", sweep_to=2637.02, decay=10, amp=0.7),
    }


def _cp_academy_loop():
    chords = [
        ([220.00, 261.63, 329.63], 110.00),          # Am
        ([174.61, 220.00, 261.63], 87.31),           # F
        ([261.63, 329.63, 392.00], 130.81),          # C
        ([164.81, 207.65, 246.94], 82.41),           # E
    ]
    def groove(pads):
        out = []
        for k in range(8):  # 8th-note hi-hat grid
            out.append((0, 0.375 * k, 0.12 if k % 2 else 0.18, 32, 0.001, "hat"))
        out.append((pads[0] * 2, 0.60, 0.22, 5.0, 0.004, "fm"))
        out.append((pads[2] * 2, 1.80, 0.18, 5.0, 0.004, "fm"))
        return out
    thumps = [(49.00, 0.00, 0.5, 7.0), (49.00, 1.20, 0.4, 7.0), (49.00, 2.40, 0.5, 7.0)]
    return _progression_loop(chords, groove, pad_attack=0.4, pad_release=0.4,
                             pad_amp=0.42, sub_amp=0.45, thump_spec=thumps)


def _cp_lab_loop():
    chords = [
        ([185.00, 220.00, 277.18], 92.50),           # F#m
        ([146.83, 174.61, 220.00], 73.42),           # Dm
        ([155.56, 196.00, 233.08], 77.78),           # Ebm
        ([138.59, 174.61, 207.65], 69.30),           # Cm
    ]
    def groove(pads):
        out = []
        for k in range(8):
            out.append((0, 0.375 * k + 0.19, 0.10 if k % 2 else 0.16, 30, 0.001, "hat"))
        out.append((pads[0] * 2, 0.75, 0.24, 4.5, 0.004, "fm"))
        out.append((pads[1] * 4, 1.90, 0.18, 4.5, 0.004, "fm"))
        return out
    thumps = [(43.65, 0.00, 0.55, 7.0), (43.65, 1.50, 0.45, 7.0), (43.65, 2.55, 0.55, 7.0)]
    return _progression_loop(chords, groove, pad_attack=0.45, pad_release=0.45,
                             pad_amp=0.42, sub_amp=0.45, thump_spec=thumps)


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
