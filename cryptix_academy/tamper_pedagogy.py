# cryptix_academy/tamper_pedagogy.py
#
# Stage 6B - The Scientific Method Layer.
# Sits ABOVE cryptix_academy/sandbox.py and contains pure educational truth:
# predictions, matching pairs, delayed reveal state machine, and XP rules.
# It never performs and never simulates cryptography; the sandbox remains
# the only source of verification evidence, and the UI stays a renderer.

from dataclasses import dataclass, field
from typing import List, Optional

from cryptix_academy.models import LearningProgress
from cryptix_academy.sandbox import (
    NoOpExperiment,
    CiphertextTamperExperiment,
    MetadataTamperExperiment,
    VersionTamperExperiment,
    AlgorithmTamperExperiment,
    TruncationExperiment,
    TagTamperExperiment,
)

# =========================================================
# CONSTANTS
# =========================================================

# Canonical rejection-layer values (must match VerificationTrace.rejection_layer)
LAYER_NONE = "NONE"
LAYER_STRUCTURAL = "STRUCTURAL"
LAYER_CRYPTOGRAPHIC = "CRYPTOGRAPHIC"
VALID_REJECTION_LAYERS = {LAYER_NONE, LAYER_STRUCTURAL, LAYER_CRYPTOGRAPHIC}

# XP rules (Stage 6B contract)
XP_CORRECT_PREDICTION = 10
XP_FULL_MATCH = 15      # 3/3 matches
XP_PARTIAL_MATCH = 5    # 2/3 matches
# 0-1/3 matches, re-completion, and experiment clicks always award 0 XP.


# =========================================================
# PEDAGOGY DATA MODEL
# =========================================================

@dataclass
class MatchingItem:
    prompt: str          # e.g. "Defense Layer Engaged"
    options: List[str]   # e.g. ["None", "Layer 1 - Structural", "Layer 2 - Cryptographic"]
    correct: int         # index into options


@dataclass
class TamperChallenge:
    challenge_id: str                # stable progress key, e.g. "tamper_ciphertext"
    experiment_name: str             # links 1:1 to a TamperExperiment.name
    prediction_question: str
    prediction_options: List[str]    # exactly 4
    prediction_correct: int
    prediction_feedback: dict        # per-option feedback keyed by incorrect index strings
    matching_items: List[MatchingItem]  # exactly 3
    canonical_rejection_layer: str   # reality-anchored answer for cross-validation
    explanation: str                 # full delayed explanation, revealed only at the end


# =========================================================
# THE SEVEN CANONICAL CHALLENGES
# =========================================================

LAYER_MATCH_OPTIONS = [
    "None - the container fully authenticated",
    "Layer 1 - Structural Format Validation",
    "Layer 2 - Cryptographic AEAD Verification",
]

TAMPER_CHALLENGES: List[TamperChallenge] = [
    TamperChallenge(
        challenge_id="tamper_control_group",
        experiment_name="Control Group (No-Op)",
        prediction_question="The container is left completely untouched. What will the Cryptix verification pipeline do with it?",
        prediction_options=[
            "Reject it - the MAGIC header will fail validation.",
            "Decrypt and authenticate it successfully, proving the system baseline works.",
            "Attempt to repair minor byte inconsistencies automatically.",
            "Refuse it because no password was provided for this session.",
        ],
        prediction_correct=1,
        prediction_feedback={
            "0": "The MAGIC header is intact - only tampering breaks it. Compare with the trace: MAGIC passed.",
            "2": "Cryptix has no repair mechanism. AEAD verifies; it never reconstructs damaged data.",
            "3": "The sandbox holds a valid ephemeral session password. Nothing about the control group changes credentials.",
        },
        matching_items=[
            MatchingItem(
                prompt="Defense Layer Engaged",
                options=LAYER_MATCH_OPTIONS,
                correct=0,
            ),
            MatchingItem(
                prompt="Defense Mechanism",
                options=[
                    "The AEAD tag was verified over ciphertext and AAD with the session key",
                    "The format parser rejected the header structure",
                    "Argon2id key derivation refused the salt",
                ],
                correct=0,
            ),
            MatchingItem(
                prompt="Security Property Demonstrated",
                options=[
                    "System integrity compliance - the baseline holds",
                    "Format validity of the header",
                    "Keystream confidentiality",
                ],
                correct=0,
            ),
        ],
        canonical_rejection_layer=LAYER_NONE,
        explanation=(
            "The control group proves the baseline: an untampered container passes Layer 1 parsing (MAGIC, VERSION, ALGO, "
            "lengths) and Layer 2 AEAD verification with the session key. Every attack experiment is compared against "
            "this reference behavior. Without a working control group, a rejection in the attack experiments would prove nothing."
        ),
    ),
    TamperChallenge(
        challenge_id="tamper_ciphertext",
        experiment_name="Ciphertext Mutation",
        prediction_question="One bit of the encrypted payload is flipped. What will Cryptix do?",
        prediction_options=[
            "Decrypt normally - single-bit changes are tolerable to streaming ciphers.",
            "Repair the modified byte using error-correction data inside the tag.",
            "Detect the authentication failure at the AEAD stage and block all plaintext release.",
            "Reject the file immediately because the MAGIC header is invalid.",
        ],
        prediction_correct=2,
        prediction_feedback={
            "0": "AEAD is not error-tolerant. Any ciphertext change alters the computed tag, so verification fails closed.",
            "1": "The tag is a verifier, not error-correction data. Cryptix detects damage; it never repairs it.",
            "3": "The header is untouched - the trace shows MAGIC, VERSION and all header stages passing before AUTHENTICATION fails.",
        },
        matching_items=[
            MatchingItem(
                prompt="Defense Layer Engaged",
                options=LAYER_MATCH_OPTIONS,
                correct=2,
            ),
            MatchingItem(
                prompt="Defense Mechanism",
                options=[
                    "AEAD tag computed over the ciphertext no longer matches the stored tag",
                    "The parser detected an invalid ciphertext length field",
                    "Argon2id derived a different key for the mutated container",
                ],
                correct=0,
            ),
            MatchingItem(
                prompt="Security Property Demonstrated",
                options=[
                    "Integrity - tampered ciphertext cannot authenticate",
                    "Format validity of the header",
                    "Key confidentiality",
                ],
                correct=0,
            ),
        ],
        canonical_rejection_layer=LAYER_CRYPTOGRAPHIC,
        explanation=(
            "The header parses cleanly (Layer 1 passes), but the flipped ciphertext byte changes the tag computed by the "
            "AEAD algorithm, so the stored tag no longer matches (Layer 2). This is exactly why plaintext is only released "
            "after verification: an attacker cannot modify encrypted content without the key, because integrity and "
            "confidentiality are enforced by the same authentication mechanism."
        ),
    ),
    TamperChallenge(
        challenge_id="tamper_metadata",
        experiment_name="Metadata (Filename) Mutation",
        prediction_question="The filename is public, unencrypted metadata. Can an attacker edit it without consequences?",
        prediction_options=[
            "Yes - public metadata is never checked by Cryptix.",
            "No - the filename is bound into the AAD, so verification fails on mismatch.",
            "The parser silently truncates the modified filename.",
            "Cryptix re-encrypts the filename with the original key.",
        ],
        prediction_correct=1,
        prediction_feedback={
            "0": "Public does not mean unauthenticated. The filename is covered by AAD, so editing it breaks verification.",
            "2": "There is no silent truncation. The filename length still parses, but the AAD mismatch aborts everything.",
            "3": "Nothing is re-encrypted at verification time. The tag simply fails because the authenticated data changed.",
        },
        matching_items=[
            MatchingItem(
                prompt="Defense Layer Engaged",
                options=LAYER_MATCH_OPTIONS,
                correct=2,
            ),
            MatchingItem(
                prompt="Defense Mechanism",
                options=[
                    "The filename is bound into the AAD, so the tag check fails on mismatch",
                    "The parser rejects non-ASCII filename bytes",
                    "The filename is re-encrypted before verification",
                ],
                correct=0,
            ),
            MatchingItem(
                prompt="Security Property Demonstrated",
                options=[
                    "Authenticity - public metadata is still authenticated",
                    "Confidentiality of the filename",
                    "Structural format validity",
                ],
                correct=0,
            ),
        ],
        canonical_rejection_layer=LAYER_CRYPTOGRAPHIC,
        explanation=(
            "The filename is readable by anyone (it is not secret), but it is authenticated as Associated Data (AAD). "
            "Changing a single filename byte changes the AAD input, which changes the expected tag, so Layer 2 verification "
            "fails even though the ciphertext itself was never touched. This teaches the difference between confidentiality "
            "(hiding data) and authenticity (detecting modification)."
        ),
    ),
    TamperChallenge(
        challenge_id="tamper_version",
        experiment_name="Format Version Mutation",
        prediction_question="The version byte is altered. Will Cryptix even reach cryptographic verification?",
        prediction_options=[
            "Yes - the tag is checked first, and only then the version.",
            "No - the parser rejects the unsupported version before any key processing.",
            "Yes, but only for AES containers.",
            "No - the file is quarantined for manual review.",
        ],
        prediction_correct=1,
        prediction_feedback={
            "0": "Order matters: Layer 1 parsing happens before any key derivation or tag check. The trace stops at VERSION.",
            "2": "Algorithm choice is irrelevant here. Version validation is structural and happens first for every algorithm.",
            "3": "There is no quarantine mechanism. Cryptix fails closed with a clean VersionMismatchError at parse time.",
        },
        matching_items=[
            MatchingItem(
                prompt="Defense Layer Engaged",
                options=LAYER_MATCH_OPTIONS,
                correct=1,
            ),
            MatchingItem(
                prompt="Defense Mechanism",
                options=[
                    "The format parser rejected the unsupported version before key processing",
                    "The AEAD tag mismatched because of the version bytes",
                    "Argon2id rejected the modified header salt",
                ],
                correct=0,
            ),
            MatchingItem(
                prompt="Security Property Demonstrated",
                options=[
                    "Format validity - structural rejection guards the pipeline",
                    "Payload integrity",
                    "Password confidentiality",
                ],
                correct=0,
            ),
        ],
        canonical_rejection_layer=LAYER_STRUCTURAL,
        explanation=(
            "This attack never reaches cryptography. Layer 1 (structural format validation) reads the version byte during "
            "parse_header() and raises VersionMismatchError immediately - no key is derived, no cipher is created, no tag "
            "is checked. This is the cheapest possible rejection: dangerous or malformed input is discarded before any "
            "expensive or sensitive operation runs."
        ),
    ),
    TamperChallenge(
        challenge_id="tamper_algorithm",
        experiment_name="Algorithm Selector Mutation",
        prediction_question="AES ciphertext is relabeled as ChaCha20 by changing the algorithm ID byte. What happens?",
        prediction_options=[
            "It decrypts as valid ChaCha20 - algorithm labels do not matter.",
            "The parser rejects the unknown algorithm ID immediately.",
            "The wrong cipher keystream guarantees the tag check fails - zero plaintext.",
            "Cryptix falls back to AES after detecting the mismatch.",
        ],
        prediction_correct=2,
        prediction_feedback={
            "0": "The label selects which cipher interprets the bytes. AES ciphertext under a ChaCha keystream is garbage, and the tag fails.",
            "1": "ID 2 is a valid, supported algorithm - Layer 1 accepts it. The failure happens later, at Layer 2.",
            "3": "There is no fallback logic. Cryptix trusts the declared algorithm, and the authentication tag exposes the deception.",
        },
        matching_items=[
            MatchingItem(
                prompt="Defense Layer Engaged",
                options=LAYER_MATCH_OPTIONS,
                correct=2,
            ),
            MatchingItem(
                prompt="Defense Mechanism",
                options=[
                    "Parsing succeeds (the ID is valid), but the wrong cipher keystream fails the tag check",
                    "The parser rejects the unknown algorithm ID immediately",
                    "The container is transparently re-labeled back to AES",
                ],
                correct=0,
            ),
            MatchingItem(
                prompt="Security Property Demonstrated",
                options=[
                    "Integrity - ciphertext is bound to its algorithm context",
                    "Format validity of the header",
                    "Nonce uniqueness",
                ],
                correct=0,
            ),
        ],
        canonical_rejection_layer=LAYER_CRYPTOGRAPHIC,
        explanation=(
            "A subtle two-layer lesson: the algorithm ID 2 is structurally valid, so Layer 1 parsing succeeds. But the "
            "ciphertext was produced with AES; interpreting it with a ChaCha20 keystream produces garbage whose tag can "
            "never match. The attacker controls the label, but not the key - and without the key, no relabeling can "
            "produce a valid authentication."
        ),
    ),
    TamperChallenge(
        challenge_id="tamper_truncation",
        experiment_name="Container Truncation",
        prediction_question="The last 20 bytes of the container are removed. What happens?",
        prediction_options=[
            "The available portion decrypts; only the missing tail is lost.",
            "The parser pads the missing bytes automatically.",
            "Verification fails - missing ciphertext bytes break the tag computation, blocking plaintext.",
            "The MAGIC header becomes unreadable, so parsing fails.",
        ],
        prediction_correct=2,
        prediction_feedback={
            "0": "AEAD has no partial success mode. An incomplete stream can never produce a matching tag, so nothing is released.",
            "1": "Cryptix never invents missing bytes. Padding would be forgery - the exact thing authentication prevents.",
            "3": "The header sits at the front and is fully intact. The trace shows parsing succeeds and failure comes later.",
        },
        matching_items=[
            MatchingItem(
                prompt="Defense Layer Engaged",
                options=LAYER_MATCH_OPTIONS,
                correct=2,
            ),
            MatchingItem(
                prompt="Defense Mechanism",
                options=[
                    "Streaming verification fails - missing ciphertext bytes break the tag computation",
                    "The parser pads the missing bytes before verifying",
                    "The MAGIC header becomes unreadable, failing the parse",
                ],
                correct=0,
            ),
            MatchingItem(
                prompt="Security Property Demonstrated",
                options=[
                    "Integrity - incomplete streams cannot authenticate",
                    "Format validity of the magic header",
                    "Compressed payload correctness",
                ],
                correct=0,
            ),
        ],
        canonical_rejection_layer=LAYER_CRYPTOGRAPHIC,
        explanation=(
            "The header is intact, so Layer 1 parses successfully. But the AEAD tag authenticates the exact byte length of "
            "the ciphertext: with 20 bytes missing, the computed tag cannot match, and verification fails closed. Truncation "
            "is a real-world corruption and attack vector, and Cryptix treats it identically to any other integrity violation: "
            "zero plaintext released."
        ),
    ),
    TamperChallenge(
        challenge_id="tamper_tag",
        experiment_name="Authentication Tag Mutation",
        prediction_question="The attacker flips a bit in the 16-byte authentication tag itself. Can the container still pass verification?",
        prediction_options=[
            "Yes - a new valid tag can be forged without the key.",
            "No - the computed tag no longer matches the stored tag, so verification fails.",
            "Only for ChaCha20 containers.",
            "Yes - the tag is advisory metadata, not a security control.",
        ],
        prediction_correct=1,
        prediction_feedback={
            "0": "Forging a tag requires the session key. The attacker changed the stored tag, not the computed one - the mismatch is detected.",
            "2": "Algorithm choice is irrelevant. Every AEAD mode Cryptix offers enforces the same tag comparison.",
            "3": "The tag is the core security control. Without it, every other experiment in this lab would succeed.",
        },
        matching_items=[
            MatchingItem(
                prompt="Defense Layer Engaged",
                options=LAYER_MATCH_OPTIONS,
                correct=2,
            ),
            MatchingItem(
                prompt="Defense Mechanism",
                options=[
                    "The stored tag no longer matches the tag computed over ciphertext and AAD",
                    "The parser detects tag bytes outside the allowed range",
                    "The tag is regenerated from the mutated ciphertext",
                ],
                correct=0,
            ),
            MatchingItem(
                prompt="Security Property Demonstrated",
                options=[
                    "Authenticity - the seal cannot be forged without the key",
                    "Format validity of the header",
                    "Salt randomness",
                ],
                correct=0,
            ),
        ],
        canonical_rejection_layer=LAYER_CRYPTOGRAPHIC,
        explanation=(
            "The attacker can freely modify the stored tag - it is just bytes in the file. But verification recomputes the "
            "tag from the ciphertext, the AAD, and the key. Without the key, no modification of the stored tag can ever "
            "match the computed one. This is the heart of AEAD authenticity: the seal proves who encrypted the data, "
            "not just that the data is intact."
        ),
    ),
]


# =========================================================
# LOOKUP & VALIDATION
# =========================================================

def get_challenge_for_experiment(experiment_name: str) -> Optional[TamperChallenge]:
    """Returns the canonical challenge linked to a sandbox experiment name, or None."""
    for challenge in TAMPER_CHALLENGES:
        if challenge.experiment_name == experiment_name:
            return challenge
    return None


def sandbox_experiment_names() -> List[str]:
    """The authoritative list of experiment names straight from the sandbox."""
    return [
        NoOpExperiment().name,
        CiphertextTamperExperiment().name,
        MetadataTamperExperiment().name,
        VersionTamperExperiment().name,
        AlgorithmTamperExperiment().name,
        TruncationExperiment().name,
        TagTamperExperiment().name,
    ]


def validate_pedagogy() -> List[str]:
    """
    Structural validation of the pedagogy content (same discipline as validate_curriculum).
    Returns a list of problems; an empty list means the pedagogy is sound.
    """
    problems = []

    if len(TAMPER_CHALLENGES) != 7:
        problems.append(f"Expected exactly 7 challenges, found {len(TAMPER_CHALLENGES)}")

    ids = [c.challenge_id for c in TAMPER_CHALLENGES]
    if len(set(ids)) != len(ids):
        problems.append("challenge_id values must be unique")

    names = [c.experiment_name for c in TAMPER_CHALLENGES]
    if len(set(names)) != len(names):
        problems.append("experiment_name values must be unique")

    sandbox_names = sandbox_experiment_names()
    for name in sandbox_names:
        if name not in names:
            problems.append(f"sandbox experiment '{name}' has no pedagogy challenge")
    for c in TAMPER_CHALLENGES:
        if c.experiment_name not in sandbox_names:
            problems.append(f"challenge '{c.challenge_id}' references unknown experiment '{c.experiment_name}'")

    for c in TAMPER_CHALLENGES:
        if len(c.prediction_options) != 4:
            problems.append(f"{c.challenge_id}: prediction must have exactly 4 options")
        if len(set(c.prediction_options)) != len(c.prediction_options):
            problems.append(f"{c.challenge_id}: prediction options must be distinct")
        if not (0 <= c.prediction_correct < len(c.prediction_options)):
            problems.append(f"{c.challenge_id}: prediction_correct out of range")
        else:
            for idx in range(len(c.prediction_options)):
                if idx == c.prediction_correct:
                    continue
                if str(idx) not in c.prediction_feedback:
                    problems.append(f"{c.challenge_id}: missing prediction feedback for option {idx}")

        if len(c.matching_items) != 3:
            problems.append(f"{c.challenge_id}: must have exactly 3 matching items")
        for m in c.matching_items:
            if len(m.options) < 2:
                problems.append(f"{c.challenge_id}: matching item '{m.prompt}' needs at least 2 options")
            if len(set(m.options)) != len(m.options):
                problems.append(f"{c.challenge_id}: matching item '{m.prompt}' options must be distinct")
            if not (0 <= m.correct < len(m.options)):
                problems.append(f"{c.challenge_id}: matching item '{m.prompt}' correct index out of range")

        if c.canonical_rejection_layer not in VALID_REJECTION_LAYERS:
            problems.append(f"{c.challenge_id}: invalid canonical_rejection_layer '{c.canonical_rejection_layer}'")

        if not c.explanation.strip():
            problems.append(f"{c.challenge_id}: explanation must not be empty")

    return problems


# =========================================================
# SESSION STATE MACHINE
# =========================================================

class TamperChallengeSession:
    """
    Enforces the scientific method cycle:
        STATE_PREDICTION -> STATE_ARMED -> STATE_MATCHING -> STATE_REVEALED

    The delayed reveal is structural: verdict values are not exposed by the
    engine until STATE_REVEALED is reached, so no UI can show answers early.
    """

    STATE_PREDICTION = 1   # Run locked; student must record a hypothesis
    STATE_ARMED = 2        # Prediction recorded; experiment unlocked
    STATE_MATCHING = 3     # Evidence visible; investigation + matching active
    STATE_REVEALED = 4     # Verdicts, answers, explanation and XP exposed

    def __init__(self, challenge: TamperChallenge):
        self.challenge = challenge
        self.state = self.STATE_PREDICTION
        self.predicted_index: Optional[int] = None
        self.matching_selection: Optional[List[int]] = None
        self._prediction_verdict: Optional[bool] = None
        self._matching_results: Optional[List[bool]] = None
        self._xp_earned: Optional[int] = None

    # ---------- transitions ----------

    def record_prediction(self, index: int) -> bool:
        """Records the student's hypothesis. Single-shot; unlocks the experiment."""
        if self.state != self.STATE_PREDICTION:
            return False
        if not isinstance(index, int) or isinstance(index, bool):
            return False
        if not (0 <= index < len(self.challenge.prediction_options)):
            return False
        self.predicted_index = index
        self.state = self.STATE_ARMED
        return True

    def record_experiment_run(self) -> bool:
        """Notifies the session that the real sandbox experiment has executed."""
        if self.state != self.STATE_ARMED:
            return False
        self.state = self.STATE_MATCHING
        return True

    def submit_matching(self, selections: List[int]) -> bool:
        """
        Accepts one selection per matching item, evaluates everything,
        computes XP, and transitions to the reveal state.
        """
        if self.state != self.STATE_MATCHING:
            return False
        if not isinstance(selections, list) or len(selections) != len(self.challenge.matching_items):
            return False
        for sel, item in zip(selections, self.challenge.matching_items):
            if not isinstance(sel, int) or isinstance(sel, bool):
                return False
            if not (0 <= sel < len(item.options)):
                return False

        self.matching_selection = list(selections)

        # Evaluate (verdicts stored privately until reveal)
        self._prediction_verdict = (self.predicted_index == self.challenge.prediction_correct)
        self._matching_results = [
            sel == item.correct
            for sel, item in zip(selections, self.challenge.matching_items)
        ]

        correct_matches = sum(self._matching_results)
        xp = XP_CORRECT_PREDICTION if self._prediction_verdict else 0
        if correct_matches == len(self.challenge.matching_items):
            xp += XP_FULL_MATCH
        elif correct_matches == len(self.challenge.matching_items) - 1:
            xp += XP_PARTIAL_MATCH
        self._xp_earned = xp

        self.state = self.STATE_REVEALED
        return True

    def reset(self, challenge: Optional[TamperChallenge] = None) -> None:
        """Returns to STATE_PREDICTION, optionally bound to a new challenge."""
        if challenge is not None:
            self.challenge = challenge
        self.state = self.STATE_PREDICTION
        self.predicted_index = None
        self.matching_selection = None
        self._prediction_verdict = None
        self._matching_results = None
        self._xp_earned = None

    # ---------- delayed-reveal properties ----------

    @property
    def prediction_verdict(self) -> Optional[bool]:
        """True if the prediction was correct. None until revealed."""
        return self._prediction_verdict if self.state == self.STATE_REVEALED else None

    @property
    def matching_results(self) -> Optional[List[bool]]:
        """Per-item correctness list. None until revealed."""
        return self._matching_results if self.state == self.STATE_REVEALED else None

    @property
    def xp_earned(self) -> Optional[int]:
        """XP earned in this cycle. None until revealed."""
        return self._xp_earned if self.state == self.STATE_REVEALED else None

    @property
    def explanation(self) -> Optional[str]:
        """Full delayed explanation. None until revealed."""
        return self.challenge.explanation if self.state == self.STATE_REVEALED else None


# =========================================================
# PROGRESS INTEGRATION
# =========================================================

def apply_challenge_outcome(progress: LearningProgress, session: TamperChallengeSession) -> int:
    """
    Persists a revealed challenge outcome into the learning profile.
    Awards XP exactly once per challenge (re-completion awards 0, mirroring
    the engine.py resubmission rule). Returns the XP actually awarded.
    """
    if session.state != TamperChallengeSession.STATE_REVEALED:
        return 0

    challenge = session.challenge
    if challenge.challenge_id in progress.completed_challenges:
        return 0

    awarded = session.xp_earned or 0
    progress.completed_challenges[challenge.challenge_id] = {
        "attempts": 1,
        "hints_used": 0,
        "xp": awarded,
        "first_attempt": bool(session.prediction_verdict),
    }
    progress.xp += awarded
    progress.total_attempts += 1
    if session.prediction_verdict:
        progress.first_attempt_successes += 1
    return awarded
