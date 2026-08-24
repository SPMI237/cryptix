Cryptix Core v1.5.0 — Stage 5: Interactive Challenge Engine Architectural Specification
1. Introduction & Core Objective
This document outlines the detailed architectural blueprint, data flows, and design rules for Stage 5 — Interactive Challenge Engine of the Cryptix Academy educational platform.

The core objective is to construct a reusable, decoupled, and mathematically disciplined engine inside cryptix_academy/ capable of evaluating multi-format challenges, tracking diagnostic sessions, and generating objective mastery scoring.

2. Decoupled Challenge Architecture (Separation of Concerns)
To keep the security engine pristine and prevent any UI logic pollution:

UI Layer (ui/academy_dialog.py): Responsible only for layout rendering, capturing input indices, and displaying visual updates.
Academy Engine (cryptix_academy/engine.py): Orchestrates challenge lifecycles, houses type-specific evaluators, tracks in-memory attempt states, and computes score weights.
Facts Storage (cryptix_academy/progress.py): Serializes long-term milestones directly to settings.
text

                  ACADEMY ARCHITECTURE PIPELINE
                  
                 QDialog / Stacked Challenge Widget
                                │
                                ▼ (Pass Raw Input: Options / Order Lists)
                       ChallengeSession Engine
                                │
          ┌─────────────────────┼─────────────────────┐
          ▼                     ▼                     ▼
   ChoiceEvaluator      BooleanEvaluator     OrderingEvaluator
          │                     │                     │
          └─────────────────────┼─────────────────────┘
                                ▼
                         ChallengeResult
                                │
                                ▼
                       ProgressStore (Save)
3. The 12 Core Architectural Specifications
3.1 What exactly is a challenge?
A challenge is an active diagnostic session (ChallengeSession) wrapped around a curriculum Question payload. It is instantiated when a student begins a lesson quiz. It keeps track of temporary runtime parameters (like active question references, attempts counter, and hint state indices) without contaminating global profile files.

3.2 What happens when an answer is submitted?
The GUI extracts the raw student input (e.g. index letter "A", boolean string "False", or sequence array "0,1,2,3,4").
The input is passed directly to the engine's ChallengeSession.evaluate(student_answer).
The session invokes the appropriate ChallengeEvaluator to verify correctness.
On Success: Generates a finalized ChallengeResult detailing attempts, hint usage, and earned XP. Triggers progress persistence and transitions.
On Failure: Increments the internal attempts counter, renders custom, context-aware mistake explanations, and prompts for a retry or progressive hint.
3.3 How are attempts counted?
Attempts are tracked only at the session level (ChallengeSession.attempts) starting at 1.
Each incorrect submission increments the attempt counter by 1.
Attempts are not persisted globally to prevent database bloating; they are only saved in the progress log as a lightweight trace index inside completed_challenges upon successful completion.
3.4 How is XP calculated?
To maintain an encouraging, pedagogically sound reward model:

First Attempt Success: +10 XP (choice/boolean) or +15 XP (ordering).
Second Attempt Success: +7 XP (choice/boolean) or +10 XP (ordering).
Third+ Attempt Success: Capped at a minimum baseline reward of +5 XP.
Hint Penalty: Requesting a progressive hint deducts -2 XP from the potential reward, but never drops below the minimum baseline reward of +5 XP. This rewards struggle and exploration!
3.5 How do hints work?
Instead of immediately revealing the answer, we implement a Socratic progressive hint engine:

Hint Request 1 (Conceptual Clue): Displays the lesson's simple_explanation.
Hint Request 2 (Technical Clue): Displays the lesson's technical_explanation.
Hint Request 3 (Final Solution Guidance): Displays the question's technical explanation block.
3.6 What constitutes lesson completion?
A lesson is marked as completed only when all questions mapped to its lesson ID inside the curriculum database are successfully solved. Completed lesson IDs are appended to LearningProgress.completed_lessons and saved.

3.7 What constitutes level completion?
A level milestone (Level 1, Level 2, etc.) is completed as soon as the corresponding lesson index is fully solved, dynamically unlocking the next sequential level button on the Dashboard.

3.8 How is concept mastery calculated?
To provide genuine academic value separate from effort-based XP accumulation:
Concept Mastery (%)
=
∑
First-Attempt Successes
Total Solved Challenges
×
100
Concept Mastery (%)= 
Total Solved Challenges
∑First-Attempt Successes
​
 ×100
This index allows students to see their true diagnostic performance across core cryptographic topics.

3.9 What happens after a wrong answer?
Instead of a blunt "Incorrect" alert, the engine generates an Intelligent Explainer Trace:

Validates which incorrect choice was submitted.
Generates a structured warning panel:
What you answered: "Nonce stores the password"
Why this is incorrect: A nonce is a public, unique helper header. It never holds secret keys or passwords.
Socratic Clue: Think about semantic security and how ciphers remain unique.
Prompts for a retry.
3.10 What gets persisted?
Dynamic stats are written directly to %APPDATA%/Cryptix/settings.json under "learning_profile":

xp: Cumulative experience points.
level: Current academic badge (Length of completed_lessons + 1).
completed_lessons: List of lesson IDs solved.
completed_challenges: List of unique question IDs solved.
3.11 What does Reset Progress erase?
Completely deletes the "learning_profile" key inside settings.json and resets all levels to 1 and XP to 0.

3.12 Component Separation
Academy Engine (cryptix_academy/): Runs ProgressStore, ChallengeSession, ChallengeEvaluator, and curriculum loaders. Highly isolated and fully testable under CLI.
GUI (ui/): Renders layout structures, dialog sheets, and progress colors.
4. Test Strategy
All Stage 5 engine mechanics must pass regression verification under pytest -v:

test_first_attempt_scoring: Assert +10 XP awarded on immediate correct choice.
test_multi_attempt_scoring: Assert score reduces to minimum baseline +5 XP on third attempt.
test_hint_penalty_calculations: Assert hint requests deduct 2 XP but respect the +5 XP minimum.
test_mastery_evaluation: Verify mastery percentages accurately map first-attempt counts over totals.
test_lesson_unlock_logic: Ensure completion unlocks subsequent levels correctly.