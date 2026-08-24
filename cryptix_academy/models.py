# cryptix_academy/models.py

from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class Lesson:
    id: str
    title: str
    category: str
    difficulty: str
    content: str
    simple_explanation: str
    technical_explanation: str
    security_explanation: str

@dataclass
class Question:
    id: str
    lesson_id: str
    question_type: str  # "choice", "boolean", "ordering"
    question: str
    options: List[str] = field(default_factory=list)
    correct_answer: str = ""
    explanation: str = ""
    difficulty: str = "Beginner"
    feedback_by_answer: dict = field(default_factory=dict)

@dataclass
class ChallengeResult:
    challenge_id: str
    correct: bool
    score: int
    attempts: int
    hint_level: int
    feedback: str = ""
    explanation: str = ""

@dataclass
class LearningProgress:
    schema_version: int = 1
    xp: int = 0
    level: int = 1
    completed_lessons: List[str] = field(default_factory=list)
    completed_challenges: dict = field(default_factory=dict)
    first_attempt_successes: int = 0
    total_attempts: int = 0
