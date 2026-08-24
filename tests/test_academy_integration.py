# tests/test_academy_integration.py

import pytest
from utils.settings import load_settings, save_settings
from cryptix_academy.models import LearningProgress
from cryptix_academy.progress import ProgressStore

def test_unrelated_settings_preservation_on_save():
    # 1. Preset standard settings (dark mode, algorithm, and hardware_profile)
    settings = load_settings()
    settings["dark_mode"] = True
    settings["algorithm"] = 2
    settings["hardware_profile"] = {
        "aes_mb_s": 224.52,
        "chacha_mb_s": 248.11,
        "kdf_latency_s": 0.115,
        "timestamp": 1234567.89
    }
    save_settings(settings)

    # 2. Modify and Save Academy Progress
    progress = ProgressStore.reset_progress()
    progress.xp = 180
    progress.level = 3
    progress.completed_challenges["fundamentals_q1"] = {
        "attempts": 1,
        "hints_used": 0,
        "xp": 10,
        "first_attempt": True
    }
    ProgressStore.save_progress(progress)

    # 3. Load settings back and assert unrelated settings remain intact!
    reloaded_settings = load_settings()
    assert reloaded_settings["dark_mode"] is True
    assert reloaded_settings["algorithm"] == 2
    assert reloaded_settings["hardware_profile"]["aes_mb_s"] == 224.52
    assert reloaded_settings["hardware_profile"]["timestamp"] == 1234567.89

    # 4. Verify learning progress retrieved correctly
    loaded_progress = ProgressStore.load_progress()
    assert loaded_progress.xp == 180
    assert loaded_progress.level == 3
    assert "fundamentals_q1" in loaded_progress.completed_challenges

    # 5. Reset progress and verify unrelated settings STILL intact!
    ProgressStore.reset_progress()
    clean_settings = load_settings()
    assert clean_settings["dark_mode"] is True
    assert clean_settings["algorithm"] == 2
    assert "learning_profile" not in clean_settings
