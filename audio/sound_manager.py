# audio/sound_manager.py
#
# Stage 6C - the pure semantic audio logic layer.
# Qt-free, playback-free, fully testable headlessly (no audio device needed).
#
# This module owns:
#   - EVENTS: the single authoritative event catalog (spec section 3)
#   - theme discovery, validity, and the precise fallback ladder (spec section 4)
#   - settings merge/migration semantics (spec section 7)
#   - volume math (spec section 6)
#   - emission resolution: event -> (file path, effective volume) or None
#
# Architectural invariants enforced here:
#   - the UI never knows filenames; it only emits catalog event names
#   - nothing in this module can raise into the UI for a missing/broken theme

import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
THEMES_DIR = os.path.join(BASE_DIR, "themes")
DEFAULT_THEME = "cyber_lab"

# ---------------------------------------------------------
# Registers (spec section 3)
# ---------------------------------------------------------

REGISTER_MECHANICAL = "mechanical"   # the machinery speaking; never punitive
REGISTER_FEEDBACK = "feedback"       # reflecting the student's result; gentle both ways
REGISTER_REWARD = "reward"           # earning; warm
REGISTER_AMBIENCE = "ambience"       # opt-in music channel

# ---------------------------------------------------------
# THE AUTHORITATIVE EVENT CATALOG
# One event name -> one contract -> every theme must satisfy it.
# event -> (register, default event_volume in [0.0, 1.0])
# ---------------------------------------------------------

EVENTS = {
    "academy_opened":          (REGISTER_MECHANICAL, 0.90),
    "lab_opened":              (REGISTER_MECHANICAL, 0.90),
    "experiment_selected":     (REGISTER_MECHANICAL, 0.60),
    "experiment_started":      (REGISTER_MECHANICAL, 0.85),
    "structural_rejection":    (REGISTER_MECHANICAL, 0.95),
    "cryptographic_rejection": (REGISTER_MECHANICAL, 0.95),
    "control_group_success":   (REGISTER_MECHANICAL, 0.85),
    "prediction_recorded":     (REGISTER_FEEDBACK, 0.70),
    "prediction_correct":      (REGISTER_FEEDBACK, 0.75),
    "prediction_incorrect":    (REGISTER_FEEDBACK, 0.60),
    "matching_correct":        (REGISTER_FEEDBACK, 0.70),
    "matching_incorrect":      (REGISTER_FEEDBACK, 0.60),
    "question_correct":        (REGISTER_FEEDBACK, 0.75),
    "question_incorrect":      (REGISTER_FEEDBACK, 0.60),
    "challenge_completed":     (REGISTER_REWARD, 0.95),
    "xp_awarded":              (REGISTER_REWARD, 0.90),
}

AMBIENCE_LOOPS = ("academy_loop", "lab_loop")

# ---------------------------------------------------------
# Settings (spec section 7)
# ---------------------------------------------------------

DEFAULT_AUDIO_SETTINGS = {
    "theme": DEFAULT_THEME,
    "sfx_enabled": True,
    "music_enabled": False,
    "master_volume": 0.8,
}


def clamp01(value):
    """Clamps a numeric to [0.0, 1.0]; non-numeric returns None."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(1.0, v))


def effective_volume(master_volume, event_volume):
    """Locked volume math (spec section 6): clamp(master x event, 0, 1).
    The clamp applies to the product, exactly as specified; non-numeric
    inputs never raise and yield silence."""
    try:
        m = float(master_volume)
        e = float(event_volume)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, m * e))


def _sanitize_audio(raw):
    """Validates one raw audio block into a complete, sanitized one."""
    raw = raw if isinstance(raw, dict) else {}

    theme = raw.get("theme", DEFAULT_AUDIO_SETTINGS["theme"])
    if not isinstance(theme, str) or not theme.strip():
        theme = DEFAULT_AUDIO_SETTINGS["theme"]

    sfx = raw.get("sfx_enabled", DEFAULT_AUDIO_SETTINGS["sfx_enabled"])
    music = raw.get("music_enabled", DEFAULT_AUDIO_SETTINGS["music_enabled"])

    volume = clamp01(raw.get("master_volume", DEFAULT_AUDIO_SETTINGS["master_volume"]))
    if volume is None:
        volume = DEFAULT_AUDIO_SETTINGS["master_volume"]

    return {
        "theme": theme,
        "sfx_enabled": bool(sfx),
        "music_enabled": bool(music),
        "master_volume": volume,
    }


def merge_audio_defaults(settings):
    """Returns a fully validated audio settings dict, filling any missing key
    from the defaults (migration behavior, spec section 7). Pure: never mutates
    the input and never touches any non-audio key."""
    raw = {}
    if isinstance(settings, dict):
        candidate = settings.get("audio")
        if isinstance(candidate, dict):
            raw = candidate
    return _sanitize_audio(raw)


def update_audio_settings(settings, changes):
    """Applies validated changes to the audio block of a settings dict and
    returns a NEW settings dict (load-merge-save discipline: other keys are
    preserved untouched). The caller persists via the normal settings store."""
    merged = dict(settings) if isinstance(settings, dict) else {}
    current_raw = merged.get("audio") if isinstance(merged.get("audio"), dict) else {}
    current = _sanitize_audio(current_raw)
    for key in ("theme", "sfx_enabled", "music_enabled", "master_volume"):
        if key in changes:
            current[key] = changes[key]
    merged["audio"] = _sanitize_audio(current)
    return merged


# ---------------------------------------------------------
# Theme discovery & the precise fallback ladder (spec section 4)
# ---------------------------------------------------------

def theme_is_valid(theme_dir):
    """A theme is valid if its manifest.json exists and parses.
    A missing individual event WAV never invalidates a theme -
    it only silences that one event (runtime fallback)."""
    if not theme_dir or not os.path.isdir(theme_dir):
        return False
    manifest_path = os.path.join(theme_dir, "manifest.json")
    if not os.path.isfile(manifest_path):
        return False
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            json.load(f)
        return True
    except (OSError, ValueError):
        return False


def list_themes(themes_dir=THEMES_DIR):
    """Returns sorted names of all valid themes found on disk."""
    if not os.path.isdir(themes_dir):
        return []
    names = []
    for entry in os.listdir(themes_dir):
        if theme_is_valid(os.path.join(themes_dir, entry)):
            names.append(entry)
    return sorted(names)


def resolve_theme(selected, themes_dir=THEMES_DIR):
    """The fallback ladder:
        requested theme valid  -> requested theme dir
        requested invalid      -> DEFAULT_THEME dir (if valid)
        default also invalid   -> None (audio disabled gracefully)."""
    if selected:
        candidate = os.path.join(themes_dir, selected)
        if theme_is_valid(candidate):
            return candidate
    fallback = os.path.join(themes_dir, DEFAULT_THEME)
    if theme_is_valid(fallback):
        return fallback
    return None


# ---------------------------------------------------------
# Emission resolution (the UI-facing contract)
# ---------------------------------------------------------

def event_register(event):
    """Register of a catalog event, or None for unknown events."""
    entry = EVENTS.get(event)
    return entry[0] if entry else None


def resolve_emission(event, settings, themes_dir=THEMES_DIR):
    """Pure resolution: event -> (wav_path, effective_volume) or None.

    ``settings`` is the FULL settings dict (as loaded from settings.json);
    audio defaults are merged inside, so a missing 'audio' block is fine.

    Returns None (never raises) when:
      - the event is not in the catalog (typo guard)
      - SFX are disabled
      - no valid theme exists
      - the theme lacks that event's file (runtime silence fallback)
    """
    entry = EVENTS.get(event)
    if entry is None:
        return None

    audio = merge_audio_defaults(settings)
    if not audio["sfx_enabled"]:
        return None

    theme_dir = resolve_theme(audio["theme"], themes_dir)
    if theme_dir is None:
        return None

    path = os.path.join(theme_dir, event + ".wav")
    if not os.path.isfile(path):
        return None

    volume = effective_volume(audio["master_volume"], entry[1])
    return (path, volume)


def resolve_ambience(loop_name, settings, themes_dir=THEMES_DIR):
    """Pure resolution for an ambience loop: -> (wav_path, master_volume) or None.
    Takes the FULL settings dict; honors music_enabled rather than sfx_enabled."""
    if loop_name not in AMBIENCE_LOOPS:
        return None

    audio = merge_audio_defaults(settings)
    if not audio["music_enabled"]:
        return None

    theme_dir = resolve_theme(audio["theme"], themes_dir)
    if theme_dir is None:
        return None

    path = os.path.join(theme_dir, loop_name + ".wav")
    if not os.path.isfile(path):
        return None

    return (path, audio["master_volume"])
