import time
import os
from Crypto.Cipher import AES, ChaCha20_Poly1305
from core.kdf import derive_key, generate_salt


def run_benchmark():
    # Fixed test password (not used in production)
    password = "benchmark_test_password"
    salt = b'\x00' * 16  # deterministic salt for repeatable times

    # Derive key and measure time
    start = time.perf_counter()
    key = derive_key(password, salt)
    kdf_time = time.perf_counter() - start

    # Generate 50 MB of random data in memory
    data_size = 50 * 1024 * 1024  # 50 MB
    data = os.urandom(data_size)

    # AES‑256‑GCM encryption
    iv = os.urandom(12)
    start = time.perf_counter()
    cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
    _, _ = cipher.encrypt_and_digest(data)
    aes_time = time.perf_counter() - start

    # ChaCha20‑Poly1305 encryption
    iv = os.urandom(12)
    start = time.perf_counter()
    cipher = ChaCha20_Poly1305.new(key=key, nonce=iv)
    _, _ = cipher.encrypt_and_digest(data)
    chacha_time = time.perf_counter() - start

    result = (
        f"Benchmark Results (50 MB in‑memory data)\n\n"
        f"Argon2id Key Derivation (100MB, 3 passes): {kdf_time:.3f} s\n"
        f"AES‑256‑GCM Encryption: {aes_time:.3f} s\n"
        f"ChaCha20‑Poly1305 Encryption: {chacha_time:.3f} s\n"
    )
    return result