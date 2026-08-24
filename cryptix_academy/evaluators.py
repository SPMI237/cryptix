# cryptix_academy/evaluators.py

class BaseEvaluator:
    def evaluate(self, student_answer: str, correct_answer: str) -> bool:
        raise NotImplementedError


class ChoiceEvaluator(BaseEvaluator):
    def evaluate(self, student_answer: str, correct_answer: str) -> bool:
        """
        Normalizes and evaluates choice question single-character answers.
        """
        return student_answer.strip().upper() == correct_answer.strip().upper()


class BooleanEvaluator(BaseEvaluator):
    def evaluate(self, student_answer: str, correct_answer: str) -> bool:
        """
        Normalizes case-insensitive True/False string matches.
        """
        return student_answer.strip().lower() == correct_answer.strip().lower()


class OrderingEvaluator(BaseEvaluator):
    def evaluate(self, student_answer: str, correct_answer: str) -> bool:
        """
        Normalizes sequence elements by clearing spaces and commas,
        protecting against variations in whitespace mapping.
        """
        norm_student = "".join(student_answer.split()).replace(",", "")
        norm_correct = "".join(correct_answer.split()).replace(",", "")
        return norm_student == norm_correct


def get_evaluator(question_type: str) -> BaseEvaluator:
    """
    Returns the appropriate normalized evaluator.
    """
    if question_type == "choice":
        return ChoiceEvaluator()
    elif question_type == "boolean":
        return BooleanEvaluator()
    elif question_type == "ordering":
        return OrderingEvaluator()
    else:
        raise ValueError(f"Unsupported question type: {question_type}")
