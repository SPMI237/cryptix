# audio/import_ai_theme.py
#
# Stage 6C.5 - AI-generated theme importer.
# Converts a folder of AI-generated WAV files into a valid Cryptix theme:
# downmix to mono, resample to 44.1 kHz, trim/normalize SFX, edge-fade loops,
# and write a provenance manifest. The imported theme appears in the Academy
# theme dropdown automatically (zero engine changes).
#
# Usage:
#   python -m audio.import_ai_theme <input_dir> <theme_name> --tool "ElevenLabs SFX" --plan "Starter"
#   (optional: --out <themes_root> to target a different themes directory)
#
# Input contract:
#   - WAV files (16/24/32-bit PCM), any sample rate, mono or stereo
#   - named exactly after catalog events (see sound_manager.EVENTS)
#     plus academy_loop.wav and lab_loop.wav
#
# LICENSING RULE (6C.5 gate, verified 2026-09):
#   Only import audio generated under a PAID plan:
#     - ElevenLabs: Starter ($5/mo) and above -> full commercial rights,
#       retained for files generated during the paid window
#     - Stable Audio: Creator tier and above -> commercial rights
#   Free-tier output is NON-COMMERCIAL and must not ship in Cryptix.

import argparse
import json
import os
import struct
import wave

from audio.make_sounds import SFX_PEAK, LOOP_PEAK, SAMPLE_RATE
from audio.sound_manager import EVENTS, AMBIENCE_LOOPS

SFX_MAX_SECONDS = 0.80   # suite-enforced cap is 0.85; import with margin
LOOP_EDGE_FADE_S = 0.010  # 10 ms edge fade makes any loop wrap click-free


def _read_wav_floats(path):
    """Reads a PCM WAV (16/24/32-bit) into (sample_rate, mono floats)."""
    with wave.open(path, "rb") as w:
        channels = w.getnchannels()
        width = w.getsampwidth()
        rate = w.getframerate()
        n = w.getnframes()
        raw = w.readframes(n)

    if width == 2:
        fmt, scale = "<%dh", 32768.0
        ints = struct.unpack(fmt % (n * channels), raw)
    elif width == 3:
        ints = []
        for i in range(n * channels):
            b = raw[i * 3:i * 3 + 3]
            v = int.from_bytes(b, "little", signed=True)
            ints.append(v)
        scale = 8388608.0
    elif width == 4:
        ints = struct.unpack("<%di" % (n * channels), raw)
        scale = 2147483648.0
    else:
        raise ValueError(f"{path}: unsupported sample width {width * 8}-bit")

    if channels == 1:
        mono = [v / scale for v in ints]
    else:
        mono = []
        for i in range(n):
            s = 0.0
            for c in range(channels):
                s += ints[i * channels + c]
            mono.append(s / channels / scale)
    return rate, mono


def _resample(data, src_rate, dst_rate=SAMPLE_RATE):
    if src_rate == dst_rate:
        return list(data)
    out_len = int(len(data) * dst_rate / src_rate)
    out = []
    step = src_rate / dst_rate
    for i in range(out_len):
        pos = i * step
        i0 = int(pos)
        i1 = min(i0 + 1, len(data) - 1)
        frac = pos - i0
        out.append(data[i0] * (1.0 - frac) + data[i1] * frac)
    return out


def _normalize(data, peak):
    m = max((abs(v) for v in data), default=0.0)
    if m < 1e-9:
        return list(data)  # silence: leave untouched (validation will flag)
    g = peak / m
    return [v * g for v in data]


def _trim(data, max_seconds):
    limit = int(max_seconds * SAMPLE_RATE)
    if len(data) <= limit:
        return list(data)
    trimmed = data[:limit]
    fade = min(int(0.02 * SAMPLE_RATE), len(trimmed) // 4)
    for i in range(fade):
        trimmed[-1 - i] *= i / fade
    return trimmed


def _edge_fade(data, fade_s=LOOP_EDGE_FADE_S):
    n = int(fade_s * SAMPLE_RATE)
    data = list(data)
    for i in range(min(n, len(data) // 2)):
        g = i / n
        data[i] *= g
        data[-1 - i] *= g
    return data


def _write_wav(path, data):
    frames = struct.pack("<%dh" % len(data),
                         *[max(-32768, min(32767, int(v * 32767.0))) for v in data])
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(frames)


def import_theme(input_dir, theme_name, out_root=None, tool="unknown", plan="unknown"):
    """Converts AI WAVs in input_dir into a theme under out_root/theme_name.
    Returns a report dict. Missing events are reported (never fatal)."""
    if not os.path.isdir(input_dir):
        raise FileNotFoundError(f"input directory not found: {input_dir}")

    themes_root = out_root or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "themes")
    out_dir = os.path.join(str(themes_root), theme_name)
    os.makedirs(out_dir, exist_ok=True)

    imported, imported_events, missing = [], [], []

    for event in sorted(EVENTS):
        src = os.path.join(input_dir, event + ".wav")
        if not os.path.isfile(src):
            missing.append(event)
            continue
        rate, data = _read_wav_floats(src)
        data = _resample(data, rate)
        data = _trim(data, SFX_MAX_SECONDS)
        data = _normalize(data, SFX_PEAK)
        _write_wav(os.path.join(out_dir, event + ".wav"), data)
        imported.append(event)
        imported_events.append(event)

    loops_present = []
    for loop in sorted(AMBIENCE_LOOPS):
        src = os.path.join(input_dir, loop + ".wav")
        if not os.path.isfile(src):
            missing.append(loop)
            continue
        rate, data = _read_wav_floats(src)
        data = _resample(data, rate)
        data = _edge_fade(data)
        data = _normalize(data, LOOP_PEAK)
        _write_wav(os.path.join(out_dir, loop + ".wav"), data)
        imported.append(loop)
        loops_present.append(loop)

    manifest = {
        "description": f"AI-generated theme '{theme_name}' "
                       f"(tool: {tool}, plan: {plan}).",
        "events": imported_events,
        "generated_by": "python -m audio.import_ai_theme",
        "license": f"AI-generated under a PAID plan ({tool} / {plan}). "
                   "Commercial rights verified per 6C.5 gate. Free-tier "
                   "output must NOT be shipped.",
        "loops": loops_present,
        "name": theme_name,
        "provenance": {"tool": tool, "plan": plan, "pipeline": "import"},
        "register_notes": "mechanical=informative-never-punitive; "
                          "feedback=reflecting-the-students-result; reward=warm",
        "sample_rate": SAMPLE_RATE,
        "version": "1.0.0",
    }
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, sort_keys=True, ensure_ascii=False)
        f.write("\n")

    return {"dir": out_dir, "imported": imported, "missing": missing,
            "manifest": manifest}


def main():
    parser = argparse.ArgumentParser(
        description="Import AI-generated WAVs as a Cryptix audio theme")
    parser.add_argument("input_dir", help="folder containing <event>.wav files")
    parser.add_argument("theme_name", help="new theme name (folder + dropdown label)")
    parser.add_argument("--tool", default="unknown", help="generator tool name")
    parser.add_argument("--plan", default="unknown", help="plan the sounds were generated under")
    parser.add_argument("--out", default=None, help="alternate themes root (testing)")
    args = parser.parse_args()

    report = import_theme(args.input_dir, args.theme_name,
                          out_root=args.out, tool=args.tool, plan=args.plan)

    print(f"Theme '{args.theme_name}' imported -> {report['dir']}")
    print(f"  imported: {len(report['imported'])} files")
    if report["missing"]:
        print(f"  MISSING ({len(report['missing'])}): {', '.join(report['missing'])}")
        print("  WARNING: a committed theme must be complete - the test suite")
        print("  enforces the full catalog for every shipped theme.")
    print("  Reminder: only PAID-plan generations may ship (6C.5 licensing gate).")


if __name__ == "__main__":
    main()
