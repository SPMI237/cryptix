import os
import tempfile
import random
import pytest

from core.file_handler import encrypt_path, decrypt_path, AuthenticationError


def test_random_byte_flip_fails():
    password = "StrongPassword123!"
    original_data = os.urandom(1024)

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, "fuzz.txt")

        with open(input_path, "wb") as f:
            f.write(original_data)

        encrypted_path = encrypt_path(input_path, password)

        # Flip 5 random bytes
        with open(encrypted_path, "r+b") as f:
            data = bytearray(f.read())

        for _ in range(5):
            index = random.randint(0, len(data) - 1)
            data[index] ^= 0xFF

        with open(encrypted_path, "wb") as f:
            f.write(data)

        with pytest.raises(AuthenticationError):
            decrypt_path(encrypted_path, password)