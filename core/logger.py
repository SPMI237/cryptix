# core/logger.py

import os
import datetime
import hashlib
from Crypto.Cipher import AES

# We derive a fixed 32-byte internal key specifically for the local audit log.
# This keeps logging secure and transparent without requiring user input.
LOG_SECRET = b"CRYPTIX_NOVA_INTERNAL_AUDIT_SECRET_KEY_2026"
LOG_KEY = hashlib.sha256(LOG_SECRET).digest()
LOG_FILE = "CRYPTIX_audit.log.enc"

def clear_secure_log():
    """
    Deletes the encrypted audit log file.
    """
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)

def log_event(event_type: str, details: str):
    """
    Securely appends an event to the encrypted audit log.
    """
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_entry = f"[{timestamp}] [{event_type}] {details}\n"

    plaintext = ""

    # 1. Read and decrypt existing log (if it exists)
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "rb") as f:
                iv = f.read(12)
                tag = f.read(16)
                ciphertext = f.read()

            cipher = AES.new(LOG_KEY, AES.MODE_GCM, nonce=iv)
            plaintext = cipher.decrypt_and_verify(ciphertext, tag).decode("utf-8")
        except Exception:
            # If log was corrupted/tampered, we append a warning
            plaintext = f"[{timestamp}] [WARNING] Previous log corrupted or tampered!\n"

    # 2. Append new entry
    plaintext += new_entry

    # 3. Re-encrypt and save
    new_iv = os.urandom(12)
    cipher = AES.new(LOG_KEY, AES.MODE_GCM, nonce=new_iv)
    ciphertext, new_tag = cipher.encrypt_and_digest(plaintext.encode("utf-8"))

    with open(LOG_FILE, "wb") as f:
        f.write(new_iv)
        f.write(new_tag)
        f.write(ciphertext)


def read_secure_log() -> str:
    """
    Decrypts and returns the log contents (for admin viewing).
    """
    if not os.path.exists(LOG_FILE):
        return "No audit logs found."

    try:
        with open(LOG_FILE, "rb") as f:
            iv = f.read(12)
            tag = f.read(16)
            ciphertext = f.read()

        cipher = AES.new(LOG_KEY, AES.MODE_GCM, nonce=iv)
        return cipher.decrypt_and_verify(ciphertext, tag).decode("utf-8")
    except Exception:
        return "ERROR: Audit log integrity verification failed! File tampered."