# tests/test_academy_models.py

import pytest
from cryptix_academy.models import Lesson, Question, LearningProgress
from cryptix_academy.progress import ProgressStore
from cryptix_academy.curriculum import get_lessons, get_questions_for_lesson

def test_curriculum_and_all_lessons():
    lessons = get_lessons()
    assert len(lessons) == 7
    
    lesson_ids = [l.id for l in lessons]
    expected_ids = [
        "crypto_fundamentals",
        "kdf_argon2id",
        "salt_nonce_lab",
        "aead_authentication",
        "aad_metadata",
        "container_architecture",
        "integrity_tampering"
    ]
    assert lesson_ids == expected_ids

    # Verify that every lesson has exactly 1 high-quality question mapped to it
    for l_id in expected_ids:
        questions = get_questions_for_lesson(l_id)
        assert len(questions) == 1
        assert isinstance(questions[0], Question)
        assert questions[0].lesson_id == l_id
        assert len(questions[0].correct_answer) == 1
        assert len(questions[0].options) == 4

def test_progress_persistence_and_reset():
    # 1. Reset progress first to start clean
    progress = ProgressStore.reset_progress()
    assert isinstance(progress, LearningProgress)
    assert progress.xp == 0
    assert progress.level == 1
    assert len(progress.completed_lessons) == 0

    # 2. Modify and Save Progress
    progress.xp = 150
    progress.level = 2
    progress.completed_lessons.append("crypto_fundamentals")
    progress.completed_lessons.append("kdf_argon2id")
    ProgressStore.save_progress(progress)

    # 3. Reload Progress
    loaded = ProgressStore.load_progress()
    assert loaded.xp == 150
    assert loaded.level == 2
    assert "crypto_fundamentals" in loaded.completed_lessons
    assert "kdf_argon2id" in loaded.completed_lessons

    # 4. Reset and Verify Wiped
    reset_state = ProgressStore.reset_progress()
    assert reset_state.xp == 0
    assert len(reset_state.completed_lessons) == 0
    
    # Reload should be clean
    reloaded = ProgressStore.load_progress()
    assert reloaded.xp == 0