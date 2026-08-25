# Cryptix Core v1.5.0 — Stage 6B: The Scientific Method Layer Architectural Specification

## 1. Introduction & Core Objective

Stage 6 delivered the Tamper Lab as a **memory-isolated attack environment**: a real temporary Cryptix container, deterministic mutations, and the real Cryptix parser/verifier producing structured evidence.

Stage 6B transforms that security demonstration into an **interactive cryptography laboratory** by wrapping the existing execution pipeline in a proper scientific learning cycle:

```text
🔮 PREDICTION  →  ⚔️ EXPERIMENT  →  🔍 INVESTIGATION  →  🔗 MATCHING  →  📖 REVEAL
 (hypothesis)      (real attack)     (real evidence)      (interpretation)  (delayed answer)
```

The central principle remains:

> 💡 **"The UI observes Cryptix's security machinery; it never simulates it — and the pedagogy layer never reveals answers before the student has reasoned through the evidence."**

### Locked Design Decisions (approved)

| Decision | Choice |
|---|---|
| UI shape | **Gated linear flow** inside the existing dialog — no QTabWidget, no redesign |
| XP integration | **Yes** — the Matching cycle *is* the diagnostic-challenge mechanism; no XP for clicks |
| Reveal timing | **Only after Matching is submitted** — prediction verdict is hidden until then |
| Control Group | **Full cycle** — the No-Op baseline gets a prediction and matching set too |

---

## 2. Architectural Placement

The new educational engine sits **above** the sandbox and **beside** the existing academy modules. Nothing below it changes:

```text
cryptix_engine/                 ← UNTOUCHED (pure crypto machinery)
cryptix_academy/
    sandbox.py                  ← UNTOUCHED (attacks + real verification evidence)
    tamper_pedagogy.py          ← NEW: predictions, matching pairs, delayed reveal, XP
    progress.py                 ← REUSED as-is (existing store, existing schema)
ui/
    tamper_lab_dialog.py        ← EXTENDED: renders pedagogy states only (renderer, never judge)
    academy_dialog.py           ← 1-line change: pass progress into TamperLabDialog
```

Rules preserved from Stage 6:
*   `sandbox.py` stays security-focused — no pedagogy strings, no XP logic inside it.
*   The UI never evaluates correctness and never decides when answers are shown; it renders the state the pedagogy engine exposes.
*   `cryptix_engine/` remains completely free of learning-mode code.

---

## 3. Pedagogy Data Model (`cryptix_academy/tamper_pedagogy.py`)

```python
@dataclass
class MatchingItem:
    prompt: str          # e.g. "Defense Layer Engaged"
    options: list        # e.g. ["None", "Layer 1 — Structural", "Layer 2 — Cryptographic"]
    correct: int         # index into options

@dataclass
class TamperChallenge:
    experiment_name: str          # links 1:1 to a TamperExperiment.name
    prediction_question: str
    prediction_options: list      # exactly 4
    prediction_correct: int
    prediction_feedback: dict     # per-option feedback (mirrors Question.feedback_by_answer)
    matching_items: list          # exactly 3 MatchingItem entries
    explanation: str              # full delayed explanation, revealed only at the end
```

### 3.1 Matching Dimensions (identical across all 7 challenges)

1.  **Defense Layer Engaged** — `None` / `Layer 1 — Structural Format Validation` / `Layer 2 — Cryptographic AEAD Verification`
2.  **Defense Mechanism** — challenge-specific options (AEAD tag over ciphertext, AAD binding, format parser guard, streaming tag verification, ...)
3.  **Security Property Demonstrated** — challenge-specific options (Integrity, Authenticity, Format validity, System integrity compliance, ...)

### 3.2 Canonical Challenge Content (7 challenges)

| Experiment | Prediction question ( essence ) | Correct answer | Layer | Mechanism | Property |
|---|---|---|---|---|---|
| Control Group (No-Op) | What happens to the pristine container? | Decrypts & authenticates successfully | None | AEAD tag verified over ciphertext + AAD | System integrity compliance |
| Ciphertext Mutation | One ciphertext bit flips — then what? | Authentication failure, plaintext blocked | Layer 2 | AEAD tag over ciphertext | Integrity |
| Metadata (Filename) Mutation | Filename is public — can it be edited freely? | No — AAD mismatch aborts verification | Layer 2 | AAD binding of the filename | Authenticity |
| Format Version Mutation | Will verification even be reached? | No — parser rejects at VERSION stage | Layer 1 | Format parser guard | Format validity |
| Algorithm Selector Mutation | Can AES ciphertext be relabeled as ChaCha? | No — wrong cipher keystream fails the tag | Layer 2 | AEAD tag (algorithm binding) | Integrity |
| Container Truncation | What if the stream ends prematurely? | Missing bytes break the tag check | Layer 2 | Streaming tag verification | Integrity (completeness) |
| Authentication Tag Mutation | Can the seal itself be edited? | No — computed vs stored tag mismatch | Layer 2 | Tag comparison | Authenticity |

Every incorrect prediction option carries individual `prediction_feedback` so wrong hypotheses are diagnosable at reveal time (same discipline as `curriculum.py`).

---

## 4. Session State Machine (`TamperChallengeSession`)

The delayed reveal is **structural, not cosmetic**: verdict values are not exposed by the engine until the terminal state is reached.

```text
STATE_PREDICTION ──record_prediction(i)──▶ STATE_ARMED ──record_experiment_run()──▶ STATE_MATCHING ──submit_matching([...])──▶ STATE_REVEALED
       │                                        │                                          │                                     │
 Run LOCKED                              Run UNLOCKED                          Matching card active               All verdicts,
                                       (experiment executes)                    (investigation happens here)        answers, explanation,
                                                                                                                                 XP exposed
```

*   `record_prediction(index)` — validates index in range; single-shot (cannot be re-recorded without `reset()`).
*   `record_experiment_run()` — called by the UI **after** `sandbox.run_experiment()` produced its trace.
*   `submit_matching(selections)` — evaluates all 3 items, computes XP, transitions to `STATE_REVEALED`.
*   `reset()` — invoked when the student switches experiments; returns to `STATE_PREDICTION` for the new challenge.
*   Verdict properties (`prediction_verdict`, `matching_results`, `explanation`, `xp_earned`) return `None` unless in `STATE_REVEALED`.

---

## 5. XP & Progress Integration

Locked decision: the Tamper Lab awards XP **through this diagnostic cycle only** — never for experiment clicks.

| Event | XP |
|---|---|
| Correct prediction | +10 |
| All 3 matches correct | +15 |
| Exactly 2 of 3 matches correct | +5 |
| Re-completing an already completed challenge | 0 (mirrors the engine.py resubmission rule) |

Persistence:
*   Reuses `LearningProgress.completed_challenges` under stable keys: `tamper_control_group`, `tamper_ciphertext`, `tamper_metadata`, `tamper_version`, `tamper_algorithm`, `tamper_truncation`, `tamper_tag`.
*   Reuses the existing per-challenge structure `{attempts, hints_used, xp, first_attempt}` — **no schema change**, `schema_version` stays `1`.
*   The AcademyDialog passes its loaded progress into `TamperLabDialog`; the lab saves through the same `ProgressStore` (the fix pattern from `persist_settings()` applies: load → update → save, never overwrite wholesale).

---

## 6. UI Integration (gated linear flow)

All additions render inside the existing dialog layout — the current terminal, hex inspector, and assessment card become the Investigation stage untouched.

1.  **🔮 PREDICTION card** — inserted in the left column between the experiment selector and the Run button: question label, 4 radio options, `Record Prediction` button.
2.  **Run button gating** — `setEnabled(False)` at `STATE_PREDICTION`; enabled only at `STATE_ARMED`.
3.  **🔗 MATCHING card** — added below the Security Property Assessment card: 3 rows of (prompt label + combo selector), `Submit Matching` button; active only at `STATE_MATCHING`.
4.  **📖 REVEAL block** — populated exclusively from `STATE_REVEALED` data: prediction verdict (+ per-option feedback), per-match results, full explanation, and an `XP earned` line appended to the terminal trace.
5.  **Experiment switching** — selecting a different radio resets the session to `STATE_PREDICTION`, clears pedagogy widgets, and re-locks Run. Sandbox evidence panels (terminal/hex) reset as they do today.
6.  Completed challenges may be re-run freely — evidence always regenerates from the real sandbox; XP is only awarded once.

---

## 7. Test Plan (`tests/test_tamper_pedagogy.py`)

Additive only — the existing 42 tests must remain green and unmodified.

1.  **`validate_pedagogy()`** — 7 challenges, 1:1 with experiment names; exactly 4 prediction options; correct index in range; feedback present for every incorrect option; exactly 3 matching items, each with ≥ 2 options and an in-range correct index.
2.  **State gating** — run locked before prediction; verdicts hidden before `STATE_REVEALED`; prediction cannot be re-recorded without reset.
3.  **XP rules** — full score for all-correct; partial (2/3) award; zero award on re-completion; zero for clicks.
4.  **Reality cross-validation** — for every attack challenge, execute the *real* sandbox experiment and assert the pedagogy's canonical defense layer equals the actual `trace.rejection_layer` (Version → `STRUCTURAL`; Ciphertext/Metadata/Algorithm/Truncation/Tag → `CRYPTOGRAPHIC`; Control Group → success + `NONE`). The educational content can never silently drift from engine behavior.
5.  **Progress integration** — completed challenge keys land in `completed_challenges`; pre-existing progress keys are preserved after a save cycle.

---

## 8. Explicit Non-Goals

*   No hints inside the Tamper Lab cycle in this stage (scope discipline; can be added post-v1.5).
*   No XP for running experiments without completing the cycle.
*   No modification to `sandbox.py` security logic, `cryptix_engine/`, container format, or existing tests.
*   No new curriculum lessons — Level 7 already teaches the two-layer defense this layer exercises.

---

## 9. Deliverables & Order of Work

| Step | File | Content |
|---|---|---|
| 1 | `cryptix_academy/tamper_pedagogy.py` | Data model, 7 challenges, session state machine, XP rules |
| 2 | `tests/test_tamper_pedagogy.py` | The 5 test groups above |
| 3 | `ui/tamper_lab_dialog.py` | Prediction card, run gating, matching card, reveal block |
| 4 | `ui/academy_dialog.py` | Pass progress into `TamperLabDialog` |

Each step ends with `pytest -v` green before the next begins.
