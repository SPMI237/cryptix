# cryptix_academy/engine.py

import time
from cryptix_academy.models import Question, Lesson
from cryptix_engine.constants import ALGO_AES, ALGO_CHACHA, ALGO_XCHACHA

# Challenge session states
STATE_NOT_STARTED = 0
STATE_ACTIVE = 1
STATE_FAILED_ATTEMPT = 2
STATE_COMPLETED = 3

class ChallengeSession:
    def __init__(self, question: Question, lesson: Lesson):
        self.question = question
        self.lesson = lesson
        self.attempts = 1
        self.hint_level = 0  # ranges from 0 to 3
        self.state = STATE_ACTIVE

    def request_next_hint(self) -> str:
        """
        Increments and returns the next progressive Socratic hint layer.
        """
        if self.hint_level < 3:
            self.hint_level += 1

        if self.hint_level == 1:
            return f"💡 Hint 1 (Conceptual Clue): {self.lesson.simple_explanation}"
        elif self.hint_level == 2:
            return f"💡 Hint 2 (Technical Clue): {self.lesson.technical_explanation}"
        else:
            return f"💡 Hint 3 (Expository Solution Clue): {self.question.explanation}"

    def evaluate(self, student_answer: str) -> dict:
        """
        Evaluates the student's answer using type-specific validation rules.
        Prevents resubmission if already completed.
        Returns a rich status payload.
        """
        if self.state == STATE_COMPLETED:
            return {
                "correct": True,
                "xp_earned": 0,
                "msg": "Challenge already completed. Re-evaluation blocked."
            }

        # Validate answer correctness
        correct = (student_answer.strip() == self.question.correct_answer.strip())

        if correct:
            self.state = STATE_COMPLETED

            # Calculate XP reward based on attempts and hints
            base_xp = 15 if self.question.question_type == "ordering" else 10

            if self.attempts == 1:
                earned_xp = base_xp
            elif self.attempts == 2:
                earned_xp = 10 if self.question.question_type == "ordering" else 7
            else:
                earned_xp = 5

            # Apply progressive hint penalty (deducts 2 XP per hint level, capped at minimum 5 XP)
            if self.hint_level > 0:
                earned_xp = max(5, earned_xp - (self.hint_level * 2))

            return {
                "correct": True,
                "xp_earned": earned_xp,
                "explanation": self.question.explanation
            }
        else:
            self.state = STATE_FAILED_ATTEMPT
            feedback = self.get_mistake_feedback(student_answer)
            self.attempts += 1
            return {
                "correct": False,
                "attempts": self.attempts,
                "feedback": feedback
            }

    def get_mistake_feedback(self, student_answer: str) -> str:
        """
        Generates structured, helpful educational mistake feedback.
        """
        if self.question.question_type == "boolean":
            return "Not quite. Think about the fundamental security property. Try again or request a Hint!"
        
        if self.question.question_type == "ordering":
            return "The sequential ordering of the cryptographic pipeline is incorrect. Review Level 1 fundamentals and try again!"

        # Choice-specific wrong-option diagnostics
        if self.question.id == "fundamentals_q1":
            if student_answer == "A":
                return "Incorrect. While zip compressing saves space, symmetric cryptography's primary goal is secrecy."
            elif student_answer == "C":
                return "Incorrect. Digital signatures and public-key cryptosystems verify sender identity, not simple symmetric blocks."
            else:
                return "Incorrect. Anti-malware software blocks malicious payloads. Cryptography only protects data secrecy."

        if self.question.id == "kdf_q1":
            return "Incorrect. AES demands high-entropy binary bits of exactly 256 bits length. Low-entropy passwords are easily guessed. Try again!"

        if self.question.id == "salt_nonce_q1":
            return "Incorrect. Nonces do not hide sizes or store password backups. They make identical inputs uniquely scrambled."

        return "That answer is not correct. Review the lesson explanations and try again!"
