# core/file_handler.py

import os
import io
import zipfile


import config
from cryptix_engine.kdf import generate_salt, derive_key
from cryptix_engine.container import build_header, parse_header
from cryptix_engine.exceptions import AuthenticationError
from cryptix_engine.container import build_aad
from cryptix_engine.container import parse_header
from cryptix_engine.aead import create_cipher



# =========================================================
# CUSTOM EXCEPTIONS
# =========================================================


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
        header_data = parse_header(f)
        ciphertext = f.read()

    algorithm = header_data["algorithm"]
    salt = header_data["salt"]
    iv = header_data["iv"]
    tag = header_data["tag"]
    filename_bytes = header_data["filename_bytes"]

    # Emit small progress before heavy KDF
    if progress_callback:
        progress_callback(5)

    key = derive_key(password, salt, keyfile_data)

    # Emit progress after KDF finishes
    if progress_callback:
        progress_callback(10)

    from cryptix_engine.aead import verify_stream
    from io import BytesIO

    with BytesIO(ciphertext) as input_stream:
        verify_stream(
            input_stream,
            key,
            algorithm,
            salt,
            iv,
            tag,
            filename_bytes,
            progress_callback=None,
        )

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
        # First overwrite
        f.seek(0)
        f.write(os.urandom(size))
        f.flush()
        os.fsync(f.fileno())

        # Second overwrite
        f.seek(0)
        f.write(os.urandom(size))
        f.flush()
        os.fsync(f.fileno())

    os.remove(file_path)

def secure_delete_folder(folder_path: str):
    """
    Securely delete a folder by overwriting and removing all files.
    Basic secure deletion (not forensic-grade).
    """

    if not os.path.isdir(folder_path):
        return

    # Walk through all files
    for root, dirs, files in os.walk(folder_path, topdown=False):
        for file in files:
            full_path = os.path.join(root, file)

            try:
                size = os.path.getsize(full_path)
                with open(full_path, "r+b") as f:
                    f.seek(0)
                    f.write(os.urandom(size))
                    f.flush()
                    os.fsync(f.fileno())

                    f.seek(0)
                    f.write(os.urandom(size))
                    f.flush()
                    os.fsync(f.fileno())
                os.remove(full_path)
            except Exception:
                pass  # Ignore failures silently

        # Remove empty directories
        for dir_name in dirs:
            dir_path = os.path.join(root, dir_name)
            try:
                os.rmdir(dir_path)
            except Exception:
                pass

    # Finally remove the root folder
    try:
        os.rmdir(folder_path)
    except Exception:
        pass


# =========================================================
# ENCRYPT
# =========================================================

def encrypt_path(input_path: str, password: str, keyfile_data=None,
                 algorithm=ALGO_AES, progress_callback=None,
                 secure_delete_original=False):

    salt = generate_salt()

# Emit small progress before heavy KDF
    if progress_callback:
        progress_callback(5)

    key = derive_key(password, salt, keyfile_data)

# Emit progress after KDF finishes
    if progress_callback:
        progress_callback(10)

    if os.path.isfile(input_path):

        original_name = os.path.basename(input_path)
        output_path = input_path + ".cryptix"

        iv = os.urandom(12)

        filename_bytes = original_name.encode("utf-8")
        
        from cryptix_engine.aead import encrypt_stream

        with open(input_path, "rb") as infile, \
            open(output_path, "wb") as outfile:

            encrypt_stream(
                infile,
                outfile,
                key,
                algorithm,
                salt,
                iv,
                filename_bytes,
                progress_callback=None,  # keep simple for now
    )

        if secure_delete_original:
           secure_delete(input_path)
           
        return output_path

    elif os.path.isdir(input_path):

        zip_buffer = io.BytesIO()

        # First count total files for progress calculation
        all_files = []
        for root, _, files in os.walk(input_path):
            for file in files:
                full_path = os.path.join(root, file)
                all_files.append(full_path)

        total_files = len(all_files)
        processed_files = 0

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
            for full_path in all_files:
                relative_path = os.path.relpath(full_path, input_path)
                zipf.write(full_path, relative_path)

                processed_files += 1

        # Emit ZIP progress (10% → 50%)
                if progress_callback and total_files > 0:
                    percent = 10 + int((processed_files / total_files) * 40)
                    progress_callback(percent)

        plaintext = zip_buffer.getvalue()
        original_name = os.path.basename(input_path) + ".zip"
        output_path = input_path + ".cryptix"

        iv = os.urandom(12)

        from cryptix_engine.aead import encrypt_stream
        from io import BytesIO

        filename_bytes = original_name.encode("utf-8")

        if progress_callback:
            progress_callback(50)

        with BytesIO(plaintext) as input_stream, \
            open(output_path, "wb") as outfile:

            encrypt_stream(
                input_stream,
                outfile,
                key,
                algorithm,
                salt,
                iv,
                filename_bytes,
                progress_callback=None,
            )

        if progress_callback:
            progress_callback(100)

        if secure_delete_original:
           secure_delete_folder(input_path)

        return output_path

    else:
        raise ValueError("Invalid path")


# =========================================================
# DECRYPT
# =========================================================

def decrypt_path(input_path: str, password: str, keyfile_data=None,
                 progress_callback=None, secure_delete_encrypted=False):


    with open(input_path, "rb") as f:
        header_data = parse_header(f)
        ciphertext = f.read()

    algorithm = header_data["algorithm"]
    salt = header_data["salt"]
    iv = header_data["iv"]
    tag = header_data["tag"]
    filename_bytes = header_data["filename_bytes"]

    # Emit small progress before heavy KDF
    if progress_callback:
        progress_callback(5)

    key = derive_key(password, salt, keyfile_data)

    # Emit progress after KDF finishes
    if progress_callback:
        progress_callback(10)

    try:
        cipher = create_cipher(algorithm, key, iv)
    except Exception:
        raise AuthenticationError("Corrupted metadata — invalid algorithm")

    header = build_header(algorithm, salt, iv)

    aad = build_aad(header, filename_bytes)
    cipher.update(aad)
    
    from cryptix_engine.aead import decrypt_stream

    from io import BytesIO

    plaintext_buffer = BytesIO()

    with BytesIO(ciphertext) as input_stream:
        decrypt_stream(
            input_stream,
            plaintext_buffer,
            key,
            algorithm,
            salt,
            iv,
            tag,
            filename_bytes,
            progress_callback=None,
        )

    plaintext = plaintext_buffer.getvalue()

    # Decode filename AFTER successful authentication
    try:
        original_name = filename_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise AuthenticationError("Corrupted metadata — invalid filename encoding")

    input_dir = os.path.dirname(os.path.abspath(input_path)) or os.getcwd()
    output_path = os.path.join(input_dir, original_name)
    os.makedirs(input_dir, exist_ok=True)

    if original_name.endswith(".zip"):
        zip_buffer = io.BytesIO(plaintext)
        with zipfile.ZipFile(zip_buffer, "r") as zipf:
            extract_path = output_path.replace(".zip", "")
            zipf.extractall(extract_path)

        if secure_delete_encrypted and os.path.isfile(input_path):
            secure_delete(input_path)

        return extract_path
    else:
        with open(output_path, "wb") as f:
            f.write(plaintext)

        if secure_delete_encrypted and os.path.isfile(input_path):
            secure_delete(input_path)

        return output_path