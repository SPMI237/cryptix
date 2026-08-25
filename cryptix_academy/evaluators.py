# cryptix_academy/evaluators.py

class BaseEvaluator:
    def evaluate(self, student_answer: str, correct_answer: str) -> bool:
        raise NotImplementedError


class ChoiceEvaluator(BaseEvaluator):
    def evaluate(self, student_answer: str, correct_answer: str) -> bool:
        """
        Normalizes and evaluates choice question single-character answers.
        Supports both raw index strings (e.g. "1") and letters (e.g. "B" / "b"),
        completely decoupling the GUI from the semantic choice letters.
        """
        ans = student_answer.strip().upper()
        corr = correct_answer.strip().upper()
        
        # Map uppercase options to standard numeric indices
        letter_to_index = {"A": "0", "B": "1", "C": "2", "D": "3"}
        corr_index = letter_to_index.get(corr, "")
        
        return ans == corr or (corr_index != "" and ans == corr_index)


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
