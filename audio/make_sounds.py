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
LOOP_PEAK = 0.85         # DIAGNOSTIC LOUD (-1.4 dBFS) - intentionally at SFX
                         # level so a working loop cannot be missed. Set back
                         # to a comfortable background level (~0.30-0.45)
                         # once playback is confirmed on the field machine.
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
# THEME GENERATION
# =========================================================

def generate_theme(out_dir=None):
    """Renders every event sound and loop, writes manifest.json.
    Deterministic: identical inputs produce byte-identical output."""
    out_dir = out_dir or THEME_DIR
    os.makedirs(out_dir, exist_ok=True)

    written = []

    for event in sorted(EVENT_SOUNDS):
        samples = _fade_edges(_normalize(EVENT_SOUNDS[event](), SFX_PEAK))
        path = os.path.join(out_dir, event + ".wav")
        _write_wav(path, samples)
        written.append(event + ".wav")

    for loop in sorted(LOOP_SOUNDS):
        path = os.path.join(out_dir, loop + ".wav")
        _write_wav(path, LOOP_SOUNDS[loop]())
        written.append(loop + ".wav")

    manifest = {
        "description": "Cyber Laboratory - Cryptix Academy Theme 1: synthesized "
                       "terminal/laboratory identity (calm Academy, darker Lab).",
        "events": sorted(EVENT_SOUNDS.keys()),
        "generated_by": "python -m audio.make_sounds",
        "license": "Generated in-house by Cryptix make_sounds.py (pure Python, "
                   "deterministic). No third-party assets.",
        "loops": sorted(LOOP_SOUNDS.keys()),
        "name": THEME_NAME,
        "register_notes": "mechanical=informative-never-punitive; "
                          "feedback=reflecting-the-students-result; reward=warm",
        "sample_rate": SAMPLE_RATE,
        "version": "1.1.0",
    }

    manifest_path = os.path.join(out_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, sort_keys=True, ensure_ascii=False)
        f.write("\n")

    return {"dir": out_dir, "files": written, "manifest": manifest}


if __name__ == "__main__":
    result = generate_theme()
    print(f"Cryptix audio theme '{THEME_NAME}' generated at {result['dir']}")
    for name in result["files"]:
        size = os.path.getsize(os.path.join(result["dir"], name))
        print(f"  {name:<32} {size:>8,} bytes")
    print(f"  {'manifest.json':<32} written")
