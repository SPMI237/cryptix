import os
import tempfile

from core.file_handler import encrypt_path, decrypt_path


def test_empty_file():
    password = "StrongPassword123!"

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, "empty.txt")

        # Create empty file
        open(input_path, "wb").close()

        encrypted_path = encrypt_path(input_path, password)
        decrypted_path = decrypt_path(encrypted_path, password)

        with open(decrypted_path, "rb") as f:
            data = f.read()

        assert data == b""


def test_one_byte_file():
    password = "StrongPassword123!"
    original_data = b"A"

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, "onebyte.txt")

        with open(input_path, "wb") as f:
            f.write(original_data)

        encrypted_path = encrypt_path(input_path, password)
        decrypted_path = decrypt_path(encrypted_path, password)

        with open(decrypted_path, "rb") as f:
            data = f.read()

        assert data == original_data


def test_unicode_filename():
    password = "StrongPassword123!"
    original_data = b"Unicode test"

    with tempfile.TemporaryDirectory() as tmpdir:
        filename = "秘密_document_✓.txt"
        input_path = os.path.join(tmpdir, filename)

        with open(input_path, "wb") as f:
            f.write(original_data)

        encrypted_path = encrypt_path(input_path, password)
        decrypted_path = decrypt_path(encrypted_path, password)

        with open(decrypted_path, "rb") as f:
            data = f.read()

        assert data == original_data