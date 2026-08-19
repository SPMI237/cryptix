# tests/test_performance.py

import os
from utils.performance import run_calibration, get_hardware_profile
from cryptix_engine.reports import HardwareProfile

def test_calibration_and_profile():
    # Clear any previous settings-cached profile to test fallback path
    from utils.settings import load_settings, save_settings
    settings = load_settings()
    if "hardware_profile" in settings:
        del settings["hardware_profile"]
        save_settings(settings)

    # 1. Test Fallback Profile
    fallback_profile = get_hardware_profile()
    assert isinstance(fallback_profile, HardwareProfile)
    assert fallback_profile.aes_mb_s == 150.0
    assert fallback_profile.chacha_mb_s == 130.0
    assert fallback_profile.kdf_latency_s == 0.15
    assert fallback_profile.timestamp == 0.0

    # 2. Run Calibration
    calibrated_profile = run_calibration()
    assert isinstance(calibrated_profile, HardwareProfile)
    assert calibrated_profile.aes_mb_s > 0
    assert calibrated_profile.chacha_mb_s > 0
    assert calibrated_profile.kdf_latency_s > 0
    assert calibrated_profile.timestamp > 0

    # 3. Test Loading Calibrated Profile
    loaded_profile = get_hardware_profile()
    assert isinstance(loaded_profile, HardwareProfile)
    assert loaded_profile.aes_mb_s == calibrated_profile.aes_mb_s
    assert loaded_profile.chacha_mb_s == calibrated_profile.chacha_mb_s
    assert loaded_profile.kdf_latency_s == calibrated_profile.kdf_latency_s
    assert loaded_profile.timestamp == calibrated_profile.timestamp