Cryptix Core v1.5.0 — Responsive Splash Screen Architectural Specification

1. Introduction & Core Objective
Replace the current static splash (blank pixmap, fixed 1500 ms fake delay) with a responsive, animated splash that reports real startup milestones and closes the moment real work finishes.

The design statement:

💡 "The splash is a transparency statement: Cryptix shows exactly what it is doing while it wakes up — nothing more, nothing less."

Locked Design Decisions (approved)
Decision	Choice
Flavor	Responsive + animated — real milestones, progress bar, pulsing shield, fade-out. No user interaction
Duration	Real work only — no minimum display time, no artificial delay. Even a 0.3 s startup shows a 0.3 s splash
Final message	Kept verbatim: "Initializing Secure Modules..." — the closing beat
Assets	Painted in code (QPainter); reuses cryptix.ico. Zero new files beyond code
Removal	The current fixed QTimer.singleShot(1500, ...) delay is deleted

2. Architecture
text

main.py                      ← orchestrator: runs milestones, owns the hand-over
ui/splash.py                 ← CryptixSplash(QWidget): painted surface, no logic
    MILESTONES               ← pure list of (label, callable) - real startup work
tests/test_splash.py         ← headless component tests
CryptixSplash is a renderer: it displays a milestone list state and a progress fraction. It knows nothing about what the steps do.
The orchestrator (in main.py) executes milestones chained via QTimer.singleShot(0, ...) so the event loop breathes between steps — animations keep moving, the UI never freezes.
Each milestone callable is a real, cheap, verifiable startup operation. No step sleeps, no step pretends.

3. The Real Milestone Contract
Ordered registry, each step actually executed at startup:

#	Label	Real work	Class
1	Cryptographic engine	import cryptix_engine modules (aead, container, kdf)	CRITICAL
2	Local configuration	load_settings() — settings + audio defaults merge	recoverable
3	Hardware profile	load cached performance profile (read-only; full calibration stays on demand as today)	recoverable
4	Academy curriculum	validate_curriculum() + validate_pedagogy() — the real validators	recoverable
5	Audio themes	sound_manager.list_themes() scan	recoverable
6	Constructing interface	MainWindow(...) construction (the genuinely heavy step)	CRITICAL
Failure semantics (amendment — approved)
Milestones are classified recoverable or critical:

Recoverable (✓/✗ → continue with fallback): configuration, hardware profile, academy validation, audio themes. A ✗ is shown in red and logged; the app continues exactly as it would today without that optional subsystem (defaults / silent audio / etc.).
Critical (✗ → startup aborted safely): the cryptographic engine and interface construction. The splash shows the failure state — ✗ <step> plus "Startup aborted safely" — holds long enough to be read, then a clear error dialog presents the failure and the process exits non-zero. The splash never claims success when a foundational component failed.
Completion behavior:

After the final step, the splash shows the closing beat — "Initializing Secure Modules..." — with the milestone rows visually converging toward it, then begins the hand-over (~300 ms crossfade: splash fades out, main window fades in).
Step chaining uses QTimer.singleShot(0, ...) — zero added delay; the only fixed beat is a ~350 ms hold on the final message so it can actually be read.
If the main window becomes ready before all animations settle, the window always wins — the splash closes unconditionally at hand-over.

4. Visual Design (painted, no assets)
text

┌────────────────────────────────────┐
│         (pulsing shield)           │  cryptix.ico + breathing radial glow
│            CRYPTIX CORE            │  title, tracked-out caps
│         ────────────────           │  thin progress bar (completed/total)
│   ✓ Cryptographic engine           │
│   ✓ Local configuration            │  done: green check, dim text
│   ⟳ Hardware profile               │  current: cyan spinner glyph, bright
│      Audio themes                  │  pending: dim
│                                    │
│      Initializing Secure Modules...│  closing beat (final message) — appears
└────────────────────────────────────┘  when the last step begins
Dark palette consistent with the app (#0B0F19 bg, #00F0FF accent, #00FF66 done, #FF3B3B error).
Pulsing shield: QTimer phase → radial-gradient glow radius; subtle (breathing, not strobing).
Frameless, WindowStaysOnTopHint, non-click-blocking (no interaction at all).

5. Explicit Non-Goals
No user interaction of any kind (no skip button, no hover, no details toggle — deliberately out per decision).
No artificial delays, no fake steps, no minimum display time.
No threading changes — milestones are sequential single-shot steps on the GUI thread (each is fast; MainWindow construction is the only heavy one and stays synchronous as today).
No changes to engine/academy logic — steps only call existing pure functions.

6. Test Plan (tests/test_splash.py — headless, offscreen)
Milestone contract: MILESTONES has ≥ 6 ordered entries; every callable executes without raising (engine import, settings load, cached profile, validators, theme scan); list_themes() includes cyber_lab.
Splash state rendering: construct CryptixSplash offscreen; feed it milestone completions; assert per-row states (done/current/pending/error), progress fraction, and that the final message appears only when the last step begins.
Error resilience (two classes): a raising recoverable step marks ✗ and the sequence continues; a raising critical step aborts safely — failure state shown, completion callback never invoked, critical handler invoked.
Hand-over: when all steps complete, the splash emits its finished signal and closes itself within the fade window (timed assertion), regardless of animation state.
No regression: full existing suite stays green (92 tests).

7. Order of Work
Step	File	Ends with
1	ui/splash.py — CryptixSplash + MILESTONES	component builds, paints offscreen
2	tests/test_splash.py	new tests green
3	main.py — orchestrator replaces the fixed-timer block	full suite green
4	Manual visual check on the field machine	hand-over timing + fade verified by eye
