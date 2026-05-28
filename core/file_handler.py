# core/file_handler.py

import os
import io
import zipfile

from Crypto.Cipher import AES, ChaCha20_Poly1305

import config
from core.kdf import generate_salt, derive_key


# =========================================================
# CUSTOM EXCEPTIONS
# =========================================================
class AuthenticationError(Exception):
    """Raised when password/keyfile is wrong or file is tampered."""
    pass


ALGO_AES = 1
ALGO_CHACHA = 2


# =========================================================
# VERIFY (Integrity Check Only)
# =========================================================

def verify_path(input_path: str, password: str, keyfile_data=None,
                progress_callback=None):
    """
    Verify integrity and authenticity of encrypted file
    without restoring plaintext.
    """

    with open(input_path, "rb") as f:
        magic = f.read(4)
        if magic != config.MAGIC_HEADER:
            raise ValueError("Invalid file format")

        version = int.from_bytes(f.read(1), "big")
        if version != config.VERSION:
            raise ValueError(f"Unsupported file version: {version}")

        algorithm = int.from_bytes(f.read(1), "big")
        salt = f.read(16)
        iv = f.read(12)
        tag = f.read(16)

        filename_length = int.from_bytes(f.read(4), "big")
        filename_bytes = f.read(filename_length)

        ciphertext = f.read()

    key = derive_key(password, salt, keyfile_data)

    if algorithm == ALGO_AES:
        cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
    elif algorithm == ALGO_CHACHA:
        cipher = ChaCha20_Poly1305.new(key=key, nonce=iv)
    else:
        raise ValueError("Unsupported algorithm")

    header = (
        config.MAGIC_HEADER
        + config.VERSION.to_bytes(1, "big")
        + algorithm.to_bytes(1, "big")
        + salt
        + iv
    )

    filename_length_bytes = len(filename_bytes).to_bytes(4, "big")
    aad = header + filename_length_bytes + filename_bytes
    cipher.update(aad)

    total_size = len(ciphertext)
    processed = 0
    CHUNK_SIZE = 64 * 1024
    offset = 0

    while offset < total_size:
        chunk = ciphertext[offset:offset + CHUNK_SIZE]
        cipher.decrypt(chunk)

        processed += len(chunk)
        offset += CHUNK_SIZE

        if progress_callback:
            percent = int((processed / total_size) * 100)
            progress_callback(percent)

    try:
        cipher.verify(tag)
    except ValueError:
        raise AuthenticationError("Integrity check failed — wrong password or tampered file")

    return "File integrity verified successfully."

# =========================================================
# SECURE DELETE
# =========================================================

def secure_delete(file_path: str):
    """
    Overwrite file with random data before deleting.
    Basic secure deletion (not forensic-grade).
    """
    if not os.path.isfile(file_path):
        return

    size = os.path.getsize(file_path)

    with open(file_path, "r+b") as f:
        f.write(os.urandom(size))
        f.flush()
        os.fsync(f.fileno())

    os.remove(file_path)


# =========================================================
# ENCRYPT
# =========================================================

def encrypt_path(input_path: str, password: str, keyfile_data=None,
                 algorithm=ALGO_AES, progress_callback=None,
                 secure_delete_original=False):

    salt = generate_salt()
    key = derive_key(password, salt, keyfile_data)

    if os.path.isfile(input_path):

        total_size = os.path.getsize(input_path)
        processed = 0

        original_name = os.path.basename(input_path)
        output_path = input_path + ".cryptix"

        iv = os.urandom(12)

        if algorithm == ALGO_AES:
            cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
        elif algorithm == ALGO_CHACHA:
            cipher = ChaCha20_Poly1305.new(key=key, nonce=iv)
        else:
            raise ValueError("Unsupported algorithm")

        header = (
            config.MAGIC_HEADER
            + config.VERSION.to_bytes(1, "big")
            + algorithm.to_bytes(1, "big")
            + salt
            + iv
        )

        filename_bytes = original_name.encode("utf-8")
        filename_length = len(filename_bytes).to_bytes(4, "big")

        aad = header + filename_length + filename_bytes
        cipher.update(aad)

        with open(input_path, "rb") as infile, \
             open(output_path, "wb") as outfile:

            outfile.write(header)
            outfile.write(b"\x00" * 16)
            outfile.write(filename_length)
            outfile.write(filename_bytes)

            while True:
                chunk = infile.read(64 * 1024)
                if not chunk:
                    break

                encrypted_chunk = cipher.encrypt(chunk)
                outfile.write(encrypted_chunk)

                processed += len(chunk)

                if progress_callback:
                    percent = int((processed / total_size) * 100)
                    progress_callback(percent)

            tag = cipher.digest()

            outfile.seek(len(header))
            outfile.write(tag)

        if secure_delete_original:
           secure_delete(input_path)
           
        return output_path

    elif os.path.isdir(input_path):

        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(input_path):
                for file in files:
                    full_path = os.path.join(root, file)
                    relative_path = os.path.relpath(full_path, input_path)
                    zipf.write(full_path, relative_path)

        plaintext = zip_buffer.getvalue()
        original_name = os.path.basename(input_path) + ".zip"
        output_path = input_path + ".cryptix"

        iv = os.urandom(12)

        if algorithm == ALGO_AES:
            cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
        elif algorithm == ALGO_CHACHA:
            cipher = ChaCha20_Poly1305.new(key=key, nonce=iv)
        else:
            raise ValueError("Unsupported algorithm")

        header = (
            config.MAGIC_HEADER
            + config.VERSION.to_bytes(1, "big")
            + algorithm.to_bytes(1, "big")
            + salt
            + iv
        )

        filename_bytes = original_name.encode("utf-8")
        filename_length = len(filename_bytes).to_bytes(4, "big")

        aad = header + filename_length + filename_bytes
        cipher.update(aad)

        ciphertext, tag = cipher.encrypt_and_digest(plaintext)

        with open(output_path, "wb") as f:
            f.write(header)
            f.write(tag)
            f.write(filename_length)
            f.write(filename_bytes)
            f.write(ciphertext)

        if secure_delete_original:
           secure_delete(input_path)

        return output_path

    else:
        raise ValueError("Invalid path")


# =========================================================
# DECRYPT
# =========================================================

def decrypt_path(input_path: str, password: str, keyfile_data=None,
                 progress_callback=None):

    with open(input_path, "rb") as f:

        magic = f.read(4)
        if magic != config.MAGIC_HEADER:
            raise ValueError("Invalid file format")

        version = int.from_bytes(f.read(1), "big")
        if version != config.VERSION:
            raise ValueError(f"Unsupported file version: {version}")

        algorithm = int.from_bytes(f.read(1), "big")
        salt = f.read(16)
        iv = f.read(12)
        tag = f.read(16)

        filename_length = int.from_bytes(f.read(4), "big")
        filename_bytes = f.read(filename_length)
        original_name = filename_bytes.decode("utf-8")

        ciphertext = f.read()

    key = derive_key(password, salt, keyfile_data)

    if algorithm == ALGO_AES:
        cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
    elif algorithm == ALGO_CHACHA:
        cipher = ChaCha20_Poly1305.new(key=key, nonce=iv)
    else:
        raise ValueError("Unsupported algorithm")

    header = (
        config.MAGIC_HEADER
        + config.VERSION.to_bytes(1, "big")
        + algorithm.to_bytes(1, "big")
        + salt
        + iv
    )

    filename_length_bytes = len(filename_bytes).to_bytes(4, "big")
    aad = header + filename_length_bytes + filename_bytes
    cipher.update(aad)

    total_size = len(ciphertext)
    processed = 0
    decrypted_chunks = []

    CHUNK_SIZE = 64 * 1024
    offset = 0

    while offset < total_size:
        chunk = ciphertext[offset:offset + CHUNK_SIZE]
        decrypted_chunk = cipher.decrypt(chunk)
        decrypted_chunks.append(decrypted_chunk)

        processed += len(chunk)
        offset += CHUNK_SIZE

        if progress_callback:
            percent = int((processed / total_size) * 100)
            progress_callback(percent)

    try:
        cipher.verify(tag)
    except ValueError:
        raise AuthenticationError("Authentication failed — wrong password or tampered file")

    plaintext = b"".join(decrypted_chunks)

    input_dir = os.path.dirname(os.path.abspath(input_path)) or os.getcwd()
    output_path = os.path.join(input_dir, original_name)
    os.makedirs(input_dir, exist_ok=True)

    if original_name.endswith(".zip"):
        zip_buffer = io.BytesIO(plaintext)
        with zipfile.ZipFile(zip_buffer, "r") as zipf:
            extract_path = output_path.replace(".zip", "")
            zipf.extractall(extract_path)
        return extract_path

    else:
        with open(output_path, "wb") as f:
            f.write(plaintext)
        return output_path