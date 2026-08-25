Cryptix Core v1.5.0 — Stage 6C: The Academy Audio Layer Architectural Specification
1. Introduction & Core Objective
Stage 6C adds a semantic audio layer to the Academy and the Tamper Lab: sound effects that reinforce learning outcomes, an opt-in generative ambience, and a user-selectable theme pack system that will later host multiple sound identities.

The central principle extends the platform's observer discipline:

💡 "Audio is a pure observer: it listens to the same semantic events the UI renders. It never judges, it never blocks, and it never touches cryptography."

The VerificationTrace already drives the terminal, the hex inspector, and the pedagogy engine. Audio becomes a fourth consumer of the same truths — never an independent evaluator.

Locked Design Decisions (approved)
Decision	Choice
Sound identity	Multiple identities as user-selectable theme packs, added one after the other
SFX sourcing	Pure synthesis now (make_sounds.py); an AI-generated theme may be added later, gated on licensing verification
Music / ambience	Generative ambient, rendered offline by our own synthesis code
Defaults on first launch	SFX on, music off
Scope	Academy + Tamper Lab only — the main encryption window stays silent
Emotional design	Three registers: mechanical (the machinery speaking), feedback (reflecting the student's result), reward (earning)
Multimedia API	Pinned to the project's PySide6==6.11.1 (Qt 6 Multimedia); no compatibility shims
2. Architectural Placement
text

cryptix_engine/            ← UNTOUCHED (cryptography only)
cryptix_academy/           ← UNTOUCHED (pedagogy & sandbox logic)
ui/
    academy_dialog.py      ← emits semantic events at existing interaction points
    tamper_lab_dialog.py   ← emits semantic events at existing interaction points
audio/
    sound_manager.py       ← pure logic: event catalog, theme resolution, toggles, volumes, fallbacks
    playback.py            ← thin Qt shell: QSoundEffect / QMediaPlayer (zero logic)
    make_sounds.py         ← the generator (make_icon.py precedent) — renders all theme WAVs
    themes/
        cyber_lab/         ← Theme 1 (this stage): manifest + generated WAVs + loop
Rules:

sound_manager.py must be importable and fully testable without Qt and without an audio device.
UI code calls exactly one function: emit(event_name). It passes data already computed (e.g., the rejection layer comes from trace.rejection_layer — audio never re-derives it).
Invariant — the UI never knows filenames. audio.emit("cryptographic_rejection") is the contract; audio.play("themes/cyber_lab/cryptographic_rejection.wav") is forbidden. Resolution from event → theme → file → volume happens exclusively inside the audio layer.
Invariant — audio can never block the UI or a security operation. Playback failure, file-loading delay, a missing audio device, or an unavailable multimedia backend must never prevent an Academy/Tamper Lab action from completing. Emissions are fire-and-forget and defensively wrapped: student clicks Run → sandbox executes → UI receives result → audio notification attempted → UI continues normally either way.
Generated WAVs are committed artifacts (small, deterministic); make_sounds.py documents how to regenerate them. No new pip dependencies — synthesis uses only the Python standard library (wave, math, struct).
3. The Event Catalog (semantic contract)
Every event has a fixed filename slot in every theme. Three registers plus ambience:

Authoritative source: the event catalog lives in exactly one place — sound_manager.EVENTS. Tests derive expected filenames from it, theme validation checks against it, and UI code may only emit names drawn from it. One event name → one contract → every theme must satisfy it. This is the same anti-drift discipline as the Stage 6B reality cross-validation: nothing duplicates the catalog — the tables below are illustrative, EVENTS is normative.

Register 1 — MECHANICAL (the machinery speaking; never punitive)
Event	Emitted from	Meaning
academy_opened	AcademyDialog	Academy entry
lab_opened	TamperLabDialog	Laboratory activation
experiment_selected	TamperLabDialog	Experiment radio chosen
experiment_started	TamperLabDialog	Run button pressed
structural_rejection	TamperLabDialog	trace.rejection_layer == "STRUCTURAL" (Layer 1 tone)
cryptographic_rejection	TamperLabDialog	trace.rejection_layer == "CRYPTOGRAPHIC" (Layer 2 tone, audibly distinct)
control_group_success	TamperLabDialog	No-Op verified — the baseline holds
Register 2 — FEEDBACK (reflecting the student's result; gentle in both directions)
Constraint: no harsh error sounds, alarms, buzzers, or failure tones — ever. A wrong prediction is useful experimental data, not a failure. The sound communicates "your hypothesis didn't match the evidence" (a soft two-note diagnostic descent), not "you failed." This is a scientific laboratory, not a game-show UI.

Event	Emitted from	Meaning
prediction_recorded	TamperLabDialog	Hypothesis locked
prediction_correct / prediction_incorrect	TamperLabDialog	Verdict at reveal
matching_correct / matching_incorrect	TamperLabDialog	Per-item result at reveal
question_correct / question_incorrect	AcademyDialog	Lesson challenge answers
Register 3 — REWARD (earning; warm)
Event	Emitted from	Meaning
challenge_completed	AcademyDialog / TamperLabDialog	Challenge or full cycle finished
xp_awarded	AcademyDialog / TamperLabDialog	XP actually granted (never zero-award replays)
Ambience (music channel, opt-in)
Event	Character
academy_loop	Calm, subtle ambient
lab_loop	Darker, technological
Critical semantic rule: a rejected container is a win for the student's understanding. structural_rejection / cryptographic_rejection must sound like an instrument correctly reporting — informative, distinct, never alarming. The Layer 1 vs Layer 2 distinction is audible because Level 7 teaches it.

Hybrid identity inside one theme: the academy_* vs lab_* event families carry the calm-Academy / darker-Lab duality. No separate "hybrid theme" exists.

4. Theme Pack Contract
text

audio/themes/<theme_name>/
    manifest.json      { "name", "description", "version", "register_notes" }
    <event>.wav        one file per catalog event (exact event names)
    academy_loop.wav   ambience (Theme 1 ships both loops)
    lab_loop.wav
Graceful degradation — precise fallback ladder:
text

Requested theme exists and is valid   → use the requested theme
Requested theme missing/invalid      → fall back to cyber_lab
cyber_lab missing/invalid            → disable audio gracefully (app unaffected)
Theme validity: a theme is valid if its manifest.json exists and parses. A missing individual event WAV never invalidates a theme — it only silences that one event.
Silence is a runtime fallback, not a packaging strategy. At runtime, missing files are skipped quietly so the user experience never degrades. At validation time (the catalog↔theme test), a missing event file is a test failure — cyber_lab cannot ship without prediction_correct.wav because the suite would go red.
Selection: settings.json → audio.theme. Themes are discovered by scanning audio/themes/.
Future themes are folder drops: Premium Minimal (6C.2), Scientific (6C.3), Cyberpunk (6C.4) require zero engine changes. If a future theme ever needs code changes, the Phase 1 abstraction leaked.
5. Synthesis Pipeline (make_sounds.py)
Pure standard library; no numpy, no external encoder; all output 44.1 kHz 16-bit PCM WAV.

Determinism requirements: make_sounds.py must not use random, secrets, OS entropy, the current time, or any machine-dependent value unless seeded with a fixed constant (random.Random(2026) for randomized detuning/noise, if ever needed). Regeneration must be byte-identical — enforced by the generator test. Anyone adding unseeded randomness breaks reproducibility and the suite catches it.

SFX design language: short tones built from sine/square/triangle partials with exponential envelopes; confirmation = rising interval; incorrect = soft two-note descent (gentle, never harsh); Layer 1 rejection = bright single "scanner" blip; Layer 2 rejection = lower, thicker dual-tone (audibly "deeper"); rewards = arpeggiated triad; XP = quick sparkle (high register, very short). Durations ≤ 0.8 s.
Ambience design language: layered detuned sine pads with slow LFO amplitude modulation, low-pass shaped noise floor, rendered so all components complete integer phase cycles over the loop length → mathematically seamless loops, no crossfade needed. ~12 s mono loops, rendered at low amplitude.
Normalization: SFX peak-normalized to one consistent level; loops rendered at ambience level (~−24 dBFS peak). One command regenerates the whole theme deterministically.
6. Playback Architecture (playback.py)
API pinning: targets the exact Qt Multimedia API of PySide6==6.11.1 — QSoundEffect for SFX; QMediaPlayer + QAudioOutput with setSource(QUrl.fromLocalFile(...)) for ambience. QMediaContent is Qt 5-only and does not exist in this environment. No compatibility shims unless a future upgrade forces one.
Ambience ownership — one rule: the Academy owns the audio session; the Tamper Lab only requests transitions:
text

Academy opens          → academy_loop starts (if music enabled)
Tamper Lab opens       → crossfade academy_loop → lab_loop
Tamper Lab closes      → crossfade lab_loop → academy_loop
Academy closes         → ambience stops
SFX: QSoundEffect pool, preloaded per active theme (low-latency WAV playback). Volume math is locked and trivially testable:
text

master_volume ∈ [0.0, 1.0]     (settings)
event_volume  ∈ [0.0, 1.0]     (per-register class level, code-defined)
effective_volume = clamp(master_volume × event_volume, 0.0, 1.0)
Ambience: one QMediaPlayer + QAudioOutput, loop mode on, volume ramped in/out on transitions instead of hard cuts.
Lifecycle: nothing plays when music_enabled is false. Focus Mode = music_enabled = false (the default). No separate mechanism.
7. Settings & UI Controls
settings.json gains one block (load-merge-save discipline as fixed in persist_settings()):

JSON

"audio": {
    "theme": "cyber_lab",
    "sfx_enabled": true,
    "music_enabled": false,
    "master_volume": 0.8
}
Migration behavior (explicit): an existing user's settings.json that contains no audio block gets the defaults above merged in without touching any other key — the exact load-merge-save discipline fixed in persist_settings(). dark_mode, learning_profile, hardware_profile, and every future key must survive an audio save unchanged, and an audio-less profile must survive any other save unchanged.

UI (Academy-only, per scope decision):

Compact 🔊/🎵 toggle row in the Academy header; the Tamper Lab shows the same controls in its title area.
An "Audio" settings card: theme selector (from audio/themes/), master volume slider. Toggling music starts/stops ambience immediately.
8. UI Integration Points (emission only)
Emissions happen at interaction points that already exist — no new logic, one line each:

academy_dialog.py: dialog open, answer submission results, challenge completion, XP award.
tamper_lab_dialog.py: dialog open, experiment selection, prediction recording, experiment run, trace.rejection_layer result, control-group success, reveal verdicts, XP award.
Rejection sounds key off trace.rejection_layer (already computed); prediction/matching sounds key off session reveal state (already computed). Audio never re-evaluates anything.
9. Test Plan (tests/test_audio.py)
All headless — no audio device, no Qt playback required:

Baseline (verified 2026-08-25): 49 existing tests, all green — 40 from Stages 1–6, +2 Stage 6 hardening (test_sandbox.py = 13), +7 Stage 6B pedagogy (test_tamper_pedagogy.py = 7). Stage 6C target = 49 + audio tests, with zero existing tests modified.

Catalog ↔ theme contract: every event in sound_manager.EVENTS (the single authoritative catalog — tests derive expected filenames from it, never from a duplicated list) has a file in every shipped theme; manifest is valid; no orphan files. A missing event file here is a test failure — runtime silence must never mask a packaging gap.
Theme resolution & fallback: correct theme loads; unknown theme falls back to cyber_lab; missing theme folder disables audio cleanly.
Settings round-trip: audio block persists; pre-existing keys (dark_mode, learning_profile, hardware_profile) preserved.
Toggle/volume logic: disabled SFX emits nothing; volume math multiplies correctly.
Generator validation: make_sounds.py output files are valid WAVs (stdlib wave module), correct duration bounds, non-silent, peak-normalized within tolerance; regeneration is deterministic (byte-identical).
Event names: emission points in UI reference only catalog events (guards against typos drifting in silently).
10. Phasing (locked: "one after the other")
Phase	Content	Engine changes?
6C.1 (this stage)	Engine + generator + Theme 1 "Cyber Laboratory" + UI wiring + settings + tests	—
6C.2	Theme: Premium Minimal	none — folder drop
6C.3	Theme: Scientific Instrument	none — folder drop
6C.4	Theme: Cyberpunk	none — folder drop
6C.5 (optional)	AI-generated theme — gated: verify the generation tool's commercial licensing terms first; record provenance in the theme manifest	none — folder drop
11. Explicit Non-Goals
No audio anywhere in the main Cryptix encryption window.
No per-event remapping UI, no import UI for user sounds (post-v1.5 candidates).
No streaming or online sounds; no new pip dependencies; no MP3/OGG encoders.
No sounds for events that carry no learning signal (hover, resize, scroll).
No changes to cryptix_engine/, cryptix_academy/, container format, or existing tests.
12. Deliverables & Order of Work
Step	File	Content
1	audio/make_sounds.py	Synthesis engine + Theme 1 rendering (SFX + loops)
2	audio/sound_manager.py	Event catalog, theme resolution, settings, fallbacks (pure logic)
3	audio/playback.py	Thin Qt playback shell
4	tests/test_audio.py	The six test groups above
5	ui/academy_dialog.py, ui/tamper_lab_dialog.py	Emission points + toggle controls + audio settings card
6	build.py / cryptix_installer.iss	Include audio/ in packaging
Each step ends with pytest -v green before the next begins.