import os
import tempfile

from core.file_handler import encrypt_path, decrypt_path


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