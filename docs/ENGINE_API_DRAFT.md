Cryptix Engine — API Draft (v0.1)

1. Purpose
The Cryptix Engine is the cryptographic foundation of the Cryptix platform.

It is responsible for:

Key derivation
Authenticated encryption
Container format handling
Metadata authentication (AAD)
Streaming encryption/decryption
Integrity verification
It is NOT responsible for:

GUI
File dialogs
ZIP creation
Installer logic
OS integration
User interaction
The engine must remain UI‑agnostic and platform‑agnostic.

2. Core Design Principle
The engine operates on streams, not files.

Applications (Cryptix Core, Cryptix Vault) provide the input/output streams.

The engine performs secure transformation.

3. Public API (Draft)
3.1 Key Derivation
Python

derive_key(password: str, salt: bytes, keyfile_data: bytes | None) -> bytes
Guarantees:

Returns 256-bit key
Uses Argon2id
Deterministic given same inputs
3.2 Encrypt Stream
Python

encrypt_stream(
    input_stream,
    output_stream,
    password: str,
    filename: str,
    algorithm: int,
    keyfile_data: bytes | None,
    progress_callback: callable | None
) -> None
Responsibilities:

Generate salt
Derive key
Generate IV
Apply AEAD (AES‑GCM or ChaCha20‑Poly1305)
Bind metadata via AAD
Write container structure
Stream data securely
Must NOT:

Open files
Manage file paths
Perform secure deletion
3.3 Decrypt Stream
Python

decrypt_stream(
    input_stream,
    output_stream,
    password: str,
    keyfile_data: bytes | None,
    progress_callback: callable | None
) -> dict
Returns metadata:

Python

{
    "original_filename": str,
    "algorithm": int,
    "version": int
}
Guarantees:

No plaintext is released before tag verification
Metadata integrity verified via AAD
Raises AuthenticationError if invalid
3.4 Verify Stream
Python

verify_stream(
    input_stream,
    password: str,
    keyfile_data: bytes | None,
    progress_callback: callable | None
) -> bool
Returns:

True if integrity verified
Raises AuthenticationError if tampered

4. Container Format Ownership
The engine owns:

text

[MAGIC]
[VERSION]
[ALGORITHM]
[SALT]
[IV]
[TAG]
[FILENAME_LENGTH]
[FILENAME]
[CIPHERTEXT]
Applications must not modify container structure directly.

5. Engine Guarantees
The engine guarantees:

Confidentiality (AEAD)
Integrity
Metadata authentication
Deterministic parsing
Version enforcement
The engine does NOT guarantee:

Protection against active malware
OS-level memory safety beyond Python limits
Secure deletion of filesystem artifacts
6. Non‑Goals (Engine)
The engine must not:

Depend on PySide
Use GUI components
Access Windows registry
Know about installers
Assume file paths
Mount virtual drives
7. Progress Reporting Contract
Progress must be:

Deterministic
Monotonic
Independent of UI
Non-blocking
Applications may visualize progress however they choose.

8. Future Extensions
Engine may later support:

Public‑key hybrid encryption
Multi‑recipient encryption
Alternate KDF parameters
Alternate container versions
Backward compatibility must be preserved when possible.

End of document.

