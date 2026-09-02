# cryptix_academy/engine.py

from cryptix_academy.models import Question, Lesson, ChallengeResult
from cryptix_academy.evaluators import get_evaluator

# Challenge session states (Simplified as recommended to prevent unused lifecycle states)
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

    def current_xp_potential(self) -> int:
        """
        XP a correct answer submitted RIGHT NOW would earn, factoring in the
        current attempt number and hint usage. Single source of truth for
        both evaluate() and the UI's live 'Worth: X XP' badge.
        """
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

        return earned_xp

    def evaluate(self, student_answer: str) -> ChallengeResult:
        """
        Evaluates the student's answer using decoupled, type-specific evaluators.
        Prevents resubmission if already completed.
        Returns a strongly typed ChallengeResult dataclass.
        """
        if self.state == STATE_COMPLETED:
            return ChallengeResult(
                challenge_id=self.question.id,
                correct=True,
                score=0,
                attempts=self.attempts - 1,
                hint_level=self.hint_level,
                feedback="Challenge already completed. Re-evaluation blocked."
            )

        # Retrieve normalized evaluator dynamically from type registry
        evaluator = get_evaluator(self.question.question_type)
        correct = evaluator.evaluate(student_answer, self.question.correct_answer)

        if correct:
            self.state = STATE_COMPLETED

            # XP reward comes from the live potential (attempts + hints factored)
            earned_xp = self.current_xp_potential()

            return ChallengeResult(
                challenge_id=self.question.id,
                correct=True,
                score=earned_xp,
                attempts=self.attempts,
                hint_level=self.hint_level,
                explanation=self.question.explanation
            )
        else:
            feedback = self.get_mistake_feedback(student_answer)
            current_attempts = self.attempts
            self.attempts += 1
            return ChallengeResult(
                challenge_id=self.question.id,
                correct=False,
                score=0,
                attempts=current_attempts,
                hint_level=self.hint_level,
                feedback=feedback
            )

    def get_mistake_feedback(self, student_answer: str) -> str:
        """
        Generates structured, helpful educational mistake feedback from curriculum.
        Completely decoupled from hardcoded question IDs.
        """
        ans = student_answer.strip().upper()
        
        # Map indices back to letters if needed
        index_to_letter = {"0": "A", "1": "B", "2": "C", "3": "D"}
        letter_ans = index_to_letter.get(ans, ans)

        # Read from dynamic question feedback mapping
        feedback = self.question.feedback_by_answer.get(ans) or self.question.feedback_by_answer.get(letter_ans)
        if feedback:
            return feedback

        # Fallbacks depending on type
        if self.question.question_type == "boolean":
            return "Not quite. Think about the fundamental security property. Try again or request a Hint!"
        elif self.question.question_type == "ordering":
            return "The sequential ordering of the cryptographic pipeline is incorrect. Review level guidelines and try again!"
        else:
            return "That answer is not correct. Review the lesson explanations and try again!"
