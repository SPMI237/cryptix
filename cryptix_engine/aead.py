# core/aes_gcm.py

import os
from Crypto.Cipher import AES
import config


def generate_iv() -> bytes:
    """
    Generate a secure random 12-byte IV for AES-GCM.
    """
    return os.urandom(config.AES_IV_SIZE)


def encrypt_data(key: bytes, data: bytes):
    """
    Encrypt data using AES-256-GCM.

    :param key: 32-byte AES key
    :param data: Plaintext bytes
    :return: (iv, ciphertext, tag)
    """

    iv = generate_iv()

    cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
    ciphertext, tag = cipher.encrypt_and_digest(data)

    return iv, ciphertext, tag


def decrypt_data(key: bytes, iv: bytes, ciphertext: bytes, tag: bytes):
    """
    Decrypt data using AES-256-GCM.

    :param key: 32-byte AES key
    :param iv: 12-byte IV
    :param ciphertext: Encrypted data
    :param tag: Authentication tag
    :return: Plaintext bytes
    """

    cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
    plaintext = cipher.decrypt_and_verify(ciphertext, tag)

    return plaintext