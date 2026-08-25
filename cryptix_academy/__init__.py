# cryptix_academy/__init__.py

from .models import Lesson, Question, ChallengeResult, LearningProgress
from .progress import ProgressStore
from .curriculum import get_lessons, get_questions_for_lesson
from .engine import ChallengeSession, STATE_ACTIVE, STATE_FAILED_ATTEMPT, STATE_COMPLETED
from .sandbox import (
    TamperLabSandbox, TraceStep, VerificationTrace, TamperExperiment, NoOpExperiment,
    CiphertextTamperExperiment, MetadataTamperExperiment, VersionTamperExperiment,
    AlgorithmTamperExperiment, TruncationExperiment, TagTamperExperiment
)
from .tamper_pedagogy import (
    MatchingItem, TamperChallenge, TamperChallengeSession, TAMPER_CHALLENGES,
    get_challenge_for_experiment, validate_pedagogy, apply_challenge_outcome
)

__all__ = [
    "Lesson",
    "Question",
    "ChallengeResult",
    "LearningProgress",
    "ProgressStore",
    "get_lessons",
    "get_questions_for_lesson",
    "ChallengeSession",
    "STATE_ACTIVE",
    "STATE_FAILED_ATTEMPT",
    "STATE_COMPLETED",
    "TamperLabSandbox",
    "TraceStep",
    "VerificationTrace",
    "TamperExperiment",
    "NoOpExperiment",
    "CiphertextTamperExperiment",
    "MetadataTamperExperiment",
    "VersionTamperExperiment",
    "AlgorithmTamperExperiment",
    "TruncationExperiment",
    "TagTamperExperiment",
    "MatchingItem",
    "TamperChallenge",
    "TamperChallengeSession",
    "TAMPER_CHALLENGES",
    "get_challenge_for_experiment",
    "validate_pedagogy",
    "apply_challenge_outcome",
]
