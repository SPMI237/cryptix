# core/aes_gcm.py

import os
import config
from Crypto.Cipher import AES, ChaCha20_Poly1305
from cryptix_engine.exceptions import FormatError

ALGO_AES = 1
ALGO_CHACHA = 2


def create_cipher(algorithm: int, key: bytes, iv: bytes):
    if algorithm == ALGO_AES:
        return AES.new(key, AES.MODE_GCM, nonce=iv)
    elif algorithm == ALGO_CHACHA:
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
):
    """
    Verifies integrity and authenticity of encrypted stream.
    Does not return plaintext.
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

        cipher.decrypt(chunk)
        processed += len(chunk)

        if progress_callback:
            progress_callback(processed)

    try:
        cipher.verify(tag)
    except ValueError:
        raise AuthenticationError("Integrity check failed — wrong password or tampered file")     