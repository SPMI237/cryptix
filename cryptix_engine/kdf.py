# core/kdf.py

import os
import hashlib
from argon2.low_level import hash_secret_raw, Type

import config


def generate_salt() -> bytes:
    """
    Generate a cryptographically secure 16-byte salt.
    """
    return os.urandom(16)


def derive_key(password: str, salt: bytes, keyfile_data: bytes = None) -> bytes:
    """
    Derive a 256-bit key using password and optional keyfile data.
    """

    password_bytes = password.encode("utf-8")

    # Combine password + keyfile if provided
    if keyfile_data is not None:
        keyfile_hash = hashlib.sha256(keyfile_data).digest()
        secret = password_bytes + keyfile_hash
    else:
        secret = password_bytes

    key = hash_secret_raw(
        secret=secret,
        salt=salt,
        time_cost=config.ARGON2_TIME_COST,
        memory_cost=config.ARGON2_MEMORY_COST,
        parallelism=config.ARGON2_PARALLELISM,
        hash_len=config.ARGON2_HASH_LEN,
        type=Type.ID,
    )

    return key