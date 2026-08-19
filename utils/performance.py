# utils/performance.py

import os
import time
from Crypto.Cipher import AES, ChaCha20_Poly1305
from cryptix_engine.kdf import derive_key
from cryptix_engine.reports import HardwareProfile
from utils.settings import load_settings, save_settings

DEFAULT_AES_SPEED = 150.0       # Fallback 150 MB/s
DEFAULT_CHACHA_SPEED = 130.0    # Fallback 130 MB/s
DEFAULT_KDF_LATENCY = 0.15      # Fallback 0.15 seconds

def run_calibration() -> HardwareProfile:
    """
    Measures the hardware performance:
    - Argon2id key derivation time
    - AES-256-GCM encryption speed in MB/s
    - ChaCha20-Poly1305 encryption speed in MB/s
    Saves results to persistent settings.
    """
    password = "calibration_benchmark_pass"
    salt = b'\x00' * 16

    # Measure KDF Latency
    start = time.perf_counter()
    key = derive_key(password, salt)
    kdf_time = time.perf_counter() - start

    # Use 10 MB of random data to measure throughput accurately and fast
    test_size_mb = 10
    data_size = test_size_mb * 1024 * 1024
    data = os.urandom(data_size)

    # AES encryption speed
    iv_aes = os.urandom(12)
    start_aes = time.perf_counter()
    cipher_aes = AES.new(key, AES.MODE_GCM, nonce=iv_aes)
    _, _ = cipher_aes.encrypt_and_digest(data)
    aes_time = time.perf_counter() - start_aes
    aes_speed = test_size_mb / aes_time if aes_time > 0 else DEFAULT_AES_SPEED

    # ChaCha encryption speed
    iv_chacha = os.urandom(12)
    start_chacha = time.perf_counter()
    cipher_chacha = ChaCha20_Poly1305.new(key=key, nonce=iv_chacha)
    _, _ = cipher_chacha.encrypt_and_digest(data)
    chacha_time = time.perf_counter() - start_chacha
    chacha_speed = test_size_mb / chacha_time if chacha_time > 0 else DEFAULT_CHACHA_SPEED

    profile = HardwareProfile(
        aes_mb_s=round(aes_speed, 2),
        chacha_mb_s=round(chacha_speed, 2),
        kdf_latency_s=round(kdf_time, 3),
        timestamp=time.time()
    )

    # Persistent cache
    settings = load_settings()
    settings["hardware_profile"] = {
        "aes_mb_s": profile.aes_mb_s,
        "chacha_mb_s": profile.chacha_mb_s,
        "kdf_latency_s": profile.kdf_latency_s,
        "timestamp": profile.timestamp
    }
    save_settings(settings)

    return profile


def get_hardware_profile() -> HardwareProfile:
    """
    Returns the cached HardwareProfile. If no calibration exists,
    returns a fallback default profile.
    """
    settings = load_settings()
    profile_data = settings.get("hardware_profile")

    if not profile_data:
        return HardwareProfile(
            aes_mb_s=DEFAULT_AES_SPEED,
            chacha_mb_s=DEFAULT_CHACHA_SPEED,
            kdf_latency_s=DEFAULT_KDF_LATENCY,
            timestamp=0.0
        )

    return HardwareProfile(
        aes_mb_s=profile_data.get("aes_mb_s", DEFAULT_AES_SPEED),
        chacha_mb_s=profile_data.get("chacha_mb_s", DEFAULT_CHACHA_SPEED),
        kdf_latency_s=profile_data.get("kdf_latency_s", DEFAULT_KDF_LATENCY),
        timestamp=profile_data.get("timestamp", 0.0)
    )