Cryptix Core v1.5.0 — Stage 7: UX Polish Architectural Specification
1. Introduction & Core Objective
Stage 7 polishes what the user feels: flow, feedback, and clarity — with zero visual redesign and zero architectural change. The discipline is the same as every previous stage: audit → specification → implementation → tests.

The stage motto:

💡 "Make the right thing obvious, the current state visible, and the feedback immediate — without moving anything the user already knows."

Locked Design Decisions (approved)
Decision	Choice
Scope	Two passes: 7A (Academy + Tamper Lab) first, then 7B (main window)
Popup reduction	Balanced: wrong answers become inline feedback; completions/level-ups keep celebratory popups
Style centralization (ui/theme.py)	Postponed to v1.6 — inline styles stay for v1.5
Out of scope	Light theme, user theming, navigation redesign, new features, localization, animations everywhere
Audit summary — already solved, will NOT be redone
Adaptive window sizing/scrolling · gated Prediction→Reveal cycle with locked/unlocked controls · Layer 1/2 textual distinction (terminal + actual-outcome label) · live XP transparency badge · visible audio toggle/theme states · password strength meter + generator + core tooltips · disabled-until-valid buttons · mastery % computation (currently text-only) · theme dropdown actionable empty state.

2. Stage 7A — Academy & Tamper Lab
7A.1 Tamper Lab stage stepper
A five-chip progress strip at the top of the Tamper Lab, always visible:

text

[🔮 PREDICT] → [⚔️ EXPERIMENT] → [🔍 INVESTIGATE] → [🔗 MATCH] → [📖 REVEAL]
Chip states: PENDING (dim), ACTIVE (cyan, emphasized border), DONE (green check, muted).

State mapping (driven exclusively by TamperChallengeSession.state plus the evidence-rendered moment — the UI adds no logic of its own):

Session state	PREDICT	EXPERIMENT	INVESTIGATE	MATCH	REVEAL
STATE_PREDICTION	ACTIVE	—	—	—	—
STATE_ARMED	DONE	ACTIVE	—	—	—
STATE_MATCHING (evidence rendered)	DONE	DONE	DONE	ACTIVE	—
STATE_REVEALED	DONE	DONE	DONE	DONE	ACTIVE
Experiment switching resets the stepper with the cycle. Acceptance: an offscreen UI test drives a full cycle by real button clicks and asserts chip states at every phase.

7A.2 Layer identity chips
The Security Property Assessment card gains a badge driven by trace.rejection_layer (never re-derived by the UI):

STRUCTURAL → amber chip: LAYER 1 — STRUCTURAL VALIDATION
CRYPTOGRAPHIC → cyan chip: LAYER 2 — AEAD VERIFICATION
control-group success → green chip: VERIFIED — BASELINE HOLDS
The chip also appears as a header line in the terminal summary. This makes the two-layer defense glanceable, reinforcing what Level 7 and the audio registers already teach.

7A.3 Inline wrong-answer feedback (Academy)
The modal ❌ Incorrect popup is replaced by a feedback panel inside the challenge page: a red-tinted card below the options showing res.feedback plus "Try again — or press H for a hint." The panel appears immediately, clears when the student changes their selection, and the question stays active exactly as today. Engine untouched: the feedback text already comes from ChallengeSession.get_mistake_feedback().

Completion, lesson-complete, and level-up popups are unchanged (stop-the-world moments deserve celebration).

7A.4 XP fly-up
When XP is actually granted (Academy challenge, Tamper reveal), a +N XP label rises ~30 px and fades near the XP header over ~900 ms (QTimer steps; QGraphicsOpacityEffect with a color-step fallback). Zero-award events animate nothing.

7A.5 Dashboard mastery bars
Each lesson row gains a slim progress bar fed by the existing calculate_lesson_mastery() (currently rendered only as text): cyan while in progress, green at 100%, dimmed for locked lessons, with the % retained as right-aligned text.

7A.6 Keyboard support
Academy challenge page: Enter = submit · 1–4 = select option (booleans: 1/2) · H = request hint
Tamper Lab: Enter = the primary enabled action (record prediction → run experiment → submit matching, following the gate)
Esc closes dialogs (already Qt default — documented, not re-implemented)
Shortcuts attach to the active page only, never globally.

3. Stage 7B — Main Cryptix Window
7B.1 Status banner system
One consistent banner area (QFrame) in the main window with three styles — info (cyan), success (green), error (red) — used for operation results currently delivered via message boxes. Banner text is selectable, with a copy button (copyable errors). Confirmation questions (Yes/No dialogs) remain popups. The banner clears when the next operation starts; errors persist until the next action.

7B.2 Working state
During encrypt/decrypt/verify/analyze: action buttons visually locked, the progress bar switches to busy mode (setRange(0,0)), and the banner shows an elapsed-time counter ("⏳ Encrypting… 3.2 s"). Reuses the existing progress signals — presentation only, no threading changes.

7B.3 Long filename handling
The selected-file display elides long names with a middle ellipsis (fontMetrics().elidedText) and carries the full path as tooltip.

4. Explicit Non-Goals
Style centralization (v1.6) · removing completion/level-up popups · repositioning main-window buttons (v1.4 layout is deliberate; 7B changes states, not structure) · any behavioral change to engine, sandbox, pedagogy, audio, or file formats · new settings.

5. Test Plan (tests/test_ux_polish.py — headless, offscreen)
Stepper truth table: full Tamper cycle via real clicks; chip states asserted at every session state; switching experiments resets the strip.
Layer chips: Version run → amber/Layer 1 chip; Ciphertext run → cyan/Layer 2; No-Op → green verified; chip text derived from trace.rejection_layer.
Inline feedback: wrong submit → panel visible with engine feedback, session still active; correct submit afterwards → completes; selection change clears the panel.
Mastery bars: stubbed progress → correct bar values/colors per lesson state (locked/in-progress/complete).
Keyboard: Qt.keyClick drives a full challenge (select via 1–4, hint via H, submit via Enter) and the Tamper Lab gate (Enter follows the enabled action).
Banner & filename: banner states set/clear; error text selectable + copy puts it on the clipboard; elided label carries the full-path tooltip.
The existing 70 tests remain green and unmodified.

6. Order of Work
Step	Item	Ends with
1	7A.1 stepper	pytest green + stepper test
2	7A.2 layer chips	pytest green + chip test
3	7A.3 inline feedback	pytest green + flow test
4	7A.4 XP fly-up	pytest green
5	7A.5 mastery bars	pytest green
6	7A.6 keyboard	pytest green + key-driving test
7	7B.1 banner	pytest green + banner tests
8	7B.2 working state	pytest green
9	7B.3 filename elision	pytest green + final full suite
Each step ships with a short manual visual checklist for the field machine.