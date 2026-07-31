import os
import tempfile
from io import BytesIO

from core.file_handler import encrypt_path
from cryptix_engine.container import analyze_container_structure


def test_structure_analysis_valid_container():
    password = "StrongPassword123!"
    data = b"Structure test"

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, "file.txt")

        with open(input_path, "wb") as f:
            f.write(data)

        encrypted_path = encrypt_path(input_path, password)

        with open(encrypted_path, "rb") as f:
            report = analyze_container_structure(f)

        assert report.container_detected is True
        assert report.header_valid is True
        assert report.compatible is True


def test_structure_analysis_invalid_magic():
    fake_data = b"XXXX" + b"\x00" * 20

    report = analyze_container_structure(BytesIO(fake_data))

    assert report.container_detected is False
    assert report.header_valid is False