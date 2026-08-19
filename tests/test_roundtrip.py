# tests/test_roundtrip.py

import os
import tempfile

from core.file_handler import encrypt_path, decrypt_path
from cryptix_engine.constants import ALGO_XCHACHA


def test_encrypt_decrypt_roundtrip_file():
    password = "StrongPassword123!"
    original_data = b"Confidential test data."

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, "test.txt")

        # Write original file
        with open(input_path, "wb") as f:
            f.write(original_data)

        # Encrypt
        encrypted_path = encrypt_path(input_path, password)

        # Decrypt
        decrypted_path = decrypt_path(encrypted_path, password)

        # Read decrypted content
        with open(decrypted_path, "rb") as f:
            decrypted_data = f.read()

        assert decrypted_data == original_data


def test_encrypt_decrypt_roundtrip_xchacha():
    password = "XChaChaPassword!2026"
    original_data = b"Modern XChaCha20-Poly1305 encryption validation data."

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, "xchacha_test.txt")

        # Write original file
        with open(input_path, "wb") as f:
            f.write(original_data)

        # Encrypt using XChaCha20-Poly1305
        encrypted_path = encrypt_path(input_path, password, algorithm=ALGO_XCHACHA)

        # Decrypt (automatic algorithm detection reads ALGO_XCHACHA = 3 from header)
        decrypted_path = decrypt_path(encrypted_path, password)

        # Read decrypted content
        with open(decrypted_path, "rb") as f:
            decrypted_data = f.read()

        assert decrypted_data == original_data