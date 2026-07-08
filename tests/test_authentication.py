import os
import tempfile
import pytest

from core.file_handler import encrypt_path, decrypt_path, AuthenticationError


def test_wrong_password_fails():
    correct_password = "CorrectPassword123!"
    wrong_password = "WrongPassword456!"
    original_data = b"Sensitive content"

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, "secret.txt")

        with open(input_path, "wb") as f:
            f.write(original_data)

        encrypted_path = encrypt_path(input_path, correct_password)

        with pytest.raises(AuthenticationError):
            decrypt_path(encrypted_path, wrong_password)

def test_corrupted_ciphertext_fails():
    password = "StrongPassword123!"
    original_data = b"Important data"

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, "file.txt")

        with open(input_path, "wb") as f:
            f.write(original_data)

        encrypted_path = encrypt_path(input_path, password)

        # Corrupt one byte in ciphertext
        with open(encrypted_path, "r+b") as f:
            f.seek(-10, os.SEEK_END)
            byte = f.read(1)
            f.seek(-1, os.SEEK_CUR)
            f.write(bytes([byte[0] ^ 0xFF]))

        with pytest.raises(AuthenticationError):
            decrypt_path(encrypted_path, password)            

def test_modified_header_fails():
    password = "StrongPassword123!"
    original_data = b"Header test"

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, "meta.txt")

        with open(input_path, "wb") as f:
            f.write(original_data)

        encrypted_path = encrypt_path(input_path, password)

        # Modify version byte
        with open(encrypted_path, "r+b") as f:
            f.seek(4)  # VERSION byte position
            version_byte = f.read(1)
            f.seek(4)
            f.write(bytes([version_byte[0] ^ 0x01]))

        with pytest.raises(Exception):
            decrypt_path(encrypted_path, password)

def test_truncated_file_fails():
    password = "StrongPassword123!"
    original_data = b"Truncate me"

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, "truncate.txt")

        with open(input_path, "wb") as f:
            f.write(original_data)

        encrypted_path = encrypt_path(input_path, password)

        # Truncate last 20 bytes
        with open(encrypted_path, "rb") as f:
            data = f.read()

        truncated = data[:-20]

        with open(encrypted_path, "wb") as f:
            f.write(truncated)

        with pytest.raises(Exception):
            decrypt_path(encrypted_path, password)                        