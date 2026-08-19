# tests/test_simulation.py

import time
import pytest
from cryptix_engine.simulation import calculate_simulation
from cryptix_engine.reports import HardwareProfile, SimulationReport
from cryptix_engine.constants import ALGO_AES, ALGO_CHACHA

def test_simulation_with_fallback_profile():
    # Fallback/Empty profile
    profile = HardwareProfile(
        aes_mb_s=150.0,
        chacha_mb_s=130.0,
        kdf_latency_s=0.15,
        timestamp=0.0
    )

    # Simulate for a 150 MB file
    report = calculate_simulation(
        file_size_bytes=150 * 1024 * 1024,
        algorithm=ALGO_AES,
        filename="video.mp4",
        profile=profile
    )

    assert isinstance(report, SimulationReport)
    assert report.input_size_bytes == 150 * 1024 * 1024
    
    # KDF latency (0.15s) + Encryption time (150 MB / 150 MB/s = 1.0s) = 1.15 seconds
    assert report.estimated_time_s == 1.15
    assert report.estimated_memory_mb == 110  # 100MB Argon2id + 10MB streaming buffer overhead
    assert report.confidence_level == "Low"
    assert "No local machine calibration is available." in report.confidence_reasons
    assert any("Streaming chunk-based pipeline" in note for note in report.notes)

def test_simulation_with_recent_calibration():
    # Freshly calibrated profile (timestamp = current epoch)
    profile = HardwareProfile(
        aes_mb_s=200.0,
        chacha_mb_s=250.0,
        kdf_latency_s=0.10,
        timestamp=time.time()
    )

    # Simulate for 500 MB using ChaCha20-Poly1305
    report = calculate_simulation(
        file_size_bytes=500 * 1024 * 1024,
        algorithm=ALGO_CHACHA,
        filename="backup.zip",
        profile=profile
    )

    assert isinstance(report, SimulationReport)
    assert report.input_size_bytes == 500 * 1024 * 1024
    
    # KDF latency (0.10s) + Encryption time (500 MB / 250 MB/s = 2.0s) = 2.10 seconds
    assert report.estimated_time_s == 2.10
    assert report.confidence_level == "High"
    assert "Recent machine-specific calibration profile is available." in report.confidence_reasons

def test_simulation_output_size_calculation():
    profile = HardwareProfile(
        aes_mb_s=150.0,
        chacha_mb_s=130.0,
        kdf_latency_s=0.15,
        timestamp=time.time()
    )

    filename = "doc.txt"  # 7 UTF-8 bytes
    file_size_bytes = 1000

    report = calculate_simulation(
        file_size_bytes=file_size_bytes,
        algorithm=ALGO_AES,
        filename=filename,
        profile=profile
    )

    # Overhead = 50 (headers) + 4 (length prefix) + 7 (filename bytes) = 61 bytes
    # Expected output size = 1000 + 61 = 1061 bytes
    assert report.estimated_output_size_bytes == 1061
    assert any("dominated almost entirely" in note for note in report.notes)