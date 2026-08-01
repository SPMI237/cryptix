import os
import tempfile

from core.file_handler import encrypt_path
from cryptix_engine.container import generate_fingerprint


def test_fingerprint_changes_on_modification():
    password = "StrongPassword123!"
    data = b"Fingerprint test"

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, "file.txt")

        with open(input_path, "wb") as f:
            f.write(data)

        encrypted_path = encrypt_path(input_path, password)

        with open(encrypted_path, "rb") as f:
            original_bytes = f.read()

        fp1 = generate_fingerprint(original_bytes)

        # Modify one byte
        modified = bytearray(original_bytes)
        modified[10] ^= 0xFF

        fp2 = generate_fingerprint(modified)

        assert fp1 != fp2