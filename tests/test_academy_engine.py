# tests/test_academy_engine.py

import pytest
from cryptix_academy.models import Question, Lesson, LearningProgress, ChallengeResult
from cryptix_academy.engine import ChallengeSession, STATE_ACTIVE, STATE_COMPLETED
from cryptix_academy.progress import ProgressStore
from cryptix_academy.curriculum import get_lessons, get_questions_for_lesson

@pytest.fixture
def sample_data():
    lesson = Lesson(
        id="test_lesson",
        title="Test Lesson",
        category="Test",
        difficulty="Beginner",
        content="Test content",
        simple_explanation="Concept hint",
        technical_explanation="Tech hint",
        security_explanation="Sec hint"
    )
    question = Question(
        id="test_q1",
        lesson_id="test_lesson",
        question_type="choice",
        question="What is the answer?",
        options=["A", "B", "C", "D"],
        correct_answer="B",
        explanation="Detail hint",
        difficulty="Beginner"
    )
    return lesson, question

def test_first_attempt_scoring(sample_data):
    lesson, question = sample_data
    session = ChallengeSession(question, lesson)
    assert session.state == STATE_ACTIVE
    assert session.attempts == 1

    # First attempt success (using decoupled index string "1" representing B)
    res = session.evaluate("1")
    assert isinstance(res, ChallengeResult)
    assert res.correct is True
    assert res.score == 10
    assert session.state == STATE_COMPLETED

def test_first_attempt_scoring_with_letter(sample_data):
    lesson, question = sample_data
    session = ChallengeSession(question, lesson)
    
    # First attempt success (using letter string "B")
    res = session.evaluate("B")
    assert isinstance(res, ChallengeResult)
    assert res.correct is True
    assert res.score == 10

def test_multi_attempt_scoring(sample_data):
    lesson, question = sample_data
    session = ChallengeSession(question, lesson)

    # First attempt wrong
    res1 = session.evaluate("A")
    assert isinstance(res1, ChallengeResult)
    assert res1.correct is False
    assert res1.attempts == 1
    assert session.attempts == 2
    
    # Second attempt wrong
    res2 = session.evaluate("C")
    assert isinstance(res2, ChallengeResult)
    assert res2.correct is False
    assert res2.attempts == 2
    assert session.attempts == 3

    # Third attempt correct (earns minimum fallback score of 5 XP)
    res3 = session.evaluate("B")
    assert isinstance(res3, ChallengeResult)
    assert res3.correct is True
    assert res3.score == 5
    assert session.state == STATE_COMPLETED

def test_hint_penalty_calculations(sample_data):
    lesson, question = sample_data
    session = ChallengeSession(question, lesson)

    # Request Hint 1 (Conceptual)
    hint1 = session.request_next_hint()
    assert "Concept hint" in hint1
    assert session.hint_level == 1

    # Request Hint 2 (Technical)
    hint2 = session.request_next_hint()
    assert "Tech hint" in hint2
    assert session.hint_level == 2

    # Request Hint 3 (Expository Solution)
    hint3 = session.request_next_hint()
    assert "Detail hint" in hint3
    assert session.hint_level == 3

    # Correct submission with Hint Level 3
    # Base 10 XP - (3 Hint levels * 2 XP penalty) = 4 XP, but capped at minimum baseline of 5 XP!
    res = session.evaluate("B")
    assert isinstance(res, ChallengeResult)
    assert res.correct is True
    assert res.score == 5

def test_completed_challenge_cannot_be_resubmitted(sample_data):
    lesson, question = sample_data
    session = ChallengeSession(question, lesson)

    # 1. Correct Submission
    res1 = session.evaluate("B")
    assert isinstance(res1, ChallengeResult)
    assert res1.correct is True
    assert res1.score == 10
    assert session.state == STATE_COMPLETED

    # 2. Resubmission Attempt (rejected)
    res2 = session.evaluate("B")
    assert isinstance(res2, ChallengeResult)
    assert res2.correct is True
    assert res2.score == 0
    assert "already completed" in res2.feedback

def test_progress_does_not_duplicate_challenges():
    progress = ProgressStore.reset_progress()
    
    # Simulate solving the same question ID multiple times
    for _ in range(3):
        if "fundamentals_q1" not in progress.completed_challenges:
            progress.completed_challenges["fundamentals_q1"] = {
                "attempts": 1,
                "hints_used": 0,
                "xp": 10,
                "first_attempt": True
            }
            
    assert len(progress.completed_challenges) == 1
    assert "fundamentals_q1" in progress.completed_challenges

def test_sequential_level_unlocking():
    progress = ProgressStore.reset_progress()
    lessons = get_lessons()
    
    # Assert start level is 1
    current_level = 1
    for l in lessons:
        if l.id in progress.completed_lessons:
            current_level += 1
        else:
            break
    assert current_level == 1

    # Mark Level 1 completed
    progress.completed_lessons.append("crypto_fundamentals")
    
    current_level = 1
    for l in lessons:
        if l.id in progress.completed_lessons:
            current_level += 1
        else:
            break
    assert current_level == 2  # Level 2 unlocked!

    # Simulate skipping: complete Level 4 without Level 2 and 3 completed
    progress.completed_lessons.append("aead_authentication")
    
    current_level = 1
    for l in lessons:
        if l.id in progress.completed_lessons:
            current_level += 1
        else:
            break
    # Level remains 2 because of the sequential missing gap in Level 2!
    assert current_level == 2
