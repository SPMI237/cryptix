# cryptix_engine/aes_gcm.py

import os
import config
from Crypto.Cipher import AES, ChaCha20_Poly1305
from cryptix_engine.exceptions import FormatError

from cryptix_engine.constants import ALGO_AES, ALGO_CHACHA, ALGO_XCHACHA
from cryptix_engine.reports import IntegrityReport


def create_cipher(algorithm: int, key: bytes, iv: bytes):
    if algorithm == ALGO_AES:
        return AES.new(key, AES.MODE_GCM, nonce=iv)
    elif algorithm in [ALGO_CHACHA, ALGO_XCHACHA]:
        return ChaCha20_Poly1305.new(key=key, nonce=iv)
    else:
        raise FormatError("Unsupported algorithm")
    
def encrypt_stream(
    input_stream,
    output_stream,
    key: bytes,
    algorithm: int,
    salt: bytes,
    iv: bytes,
    filename_bytes: bytes,
    progress_callback=None,
):
    """
    Encrypts data from input_stream and writes to output_stream.
    Assumes salt and iv already generated.
    """

    from cryptix_engine.container import build_header, build_aad

    header = build_header(algorithm, salt, iv)

    # Write header
    output_stream.write(header)

    # Reserve space for tag (16 bytes)
    output_stream.write(b"\x00" * 16)

    # Write filename length + filename
    filename_length = len(filename_bytes).to_bytes(4, "big")
    output_stream.write(filename_length)
    output_stream.write(filename_bytes)

    cipher = create_cipher(algorithm, key, iv)

    aad = build_aad(header, filename_bytes)
    cipher.update(aad)

    CHUNK_SIZE = 32 * 1024
    processed = 0

    while True:
        chunk = input_stream.read(CHUNK_SIZE)
        if not chunk:
            break

        encrypted_chunk = cipher.encrypt(chunk)
        output_stream.write(encrypted_chunk)

        processed += len(chunk)

        if progress_callback:
            progress_callback(processed)

    tag = cipher.digest()

    # Go back and write tag
    output_stream.seek(len(header))
    output_stream.write(tag)    

def decrypt_stream(
    input_stream,
    output_stream,
    key: bytes,
    algorithm: int,
    salt: bytes,
    iv: bytes,
    tag: bytes,
    filename_bytes: bytes,
    progress_callback=None,
):
    """
    Decrypts data from input_stream and writes to output_stream.
    Assumes header already parsed.
    """

    from cryptix_engine.container import build_header, build_aad
    from cryptix_engine.exceptions import AuthenticationError

    cipher = create_cipher(algorithm, key, iv)

    header = build_header(algorithm, salt, iv)
    aad = build_aad(header, filename_bytes)
    cipher.update(aad)

    CHUNK_SIZE = 32 * 1024
    processed = 0

    while True:
        chunk = input_stream.read(CHUNK_SIZE)
        if not chunk:
            break

        decrypted_chunk = cipher.decrypt(chunk)
        output_stream.write(decrypted_chunk)

        processed += len(chunk)

        if progress_callback:
            progress_callback(processed)

    try:
        cipher.verify(tag)
    except ValueError:
        raise AuthenticationError("Authentication failed — wrong password or tampered file")   

def verify_stream(
    input_stream,
    key: bytes,
    algorithm: int,
    salt: bytes,
    iv: bytes,
    tag: bytes,
    filename_bytes: bytes,
    progress_callback=None,
    return_report=False,
):
    """
    Verifies integrity and authenticity of encrypted stream.
    """

    from cryptix_engine.container import build_header, build_aad
    from cryptix_engine.exceptions import AuthenticationError

    report = IntegrityReport(
        container_valid=True,
        version_supported=True,
        algorithm_supported=True,
        metadata_authenticated=False,
        ciphertext_authenticated=False,
        failure_stage=None,
        notes=[],
    )

    try:
        cipher = create_cipher(algorithm, key, iv)
    except Exception:
        report.algorithm_supported = False
        report.failure_stage = "algorithm"
        raise AuthenticationError("Unsupported algorithm", report=report)

    header = build_header(algorithm, salt, iv)
    aad = build_aad(header, filename_bytes)

    cipher.update(aad)
    report.metadata_authenticated = True

    CHUNK_SIZE = 32 * 1024

    while True:
        chunk = input_stream.read(CHUNK_SIZE)
        if not chunk:
            break

        cipher.decrypt(chunk)

    try:
        cipher.verify(tag)
        report.ciphertext_authenticated = True
    except ValueError:
        report.failure_stage = "ciphertext"
        report.notes.append(
            "Authenticated encryption cannot distinguish wrong password from tampering."
        )
        raise AuthenticationError("Integrity check failed", report=report)

    if return_report:
        return report