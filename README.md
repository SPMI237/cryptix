Cryptix
Multi‑Algorithm Authenticated Encryption Suite
Cryptix is a security‑focused desktop encryption application designed to provide structured, authenticated local file protection using modern cryptographic primitives.

It implements:

- AES‑256‑GCM (AEAD)
- ChaCha20‑Poly1305 (AEAD)
- Argon2id memory‑hard key derivation
- Authenticated metadata binding (AAD)
- Structured, versioned encrypted container format

Cryptix is built as a modular, security‑oriented platform rather than a simple encryption wrapper.

---

# Core Security Features

- ✅ AES‑256‑GCM authenticated encryption  
- ✅ ChaCha20‑Poly1305 authenticated encryption  
- ✅ Argon2id password‑based key derivation (100MB memory configuration)  
- ✅ Metadata authentication using AEAD Additional Authenticated Data (AAD)  
- ✅ Structured binary container format with versioning  
- ✅ Streaming encryption/decryption for large files  
- ✅ File integrity verification mode  
- ✅ Secure delete option (basic overwrite)  
- ✅ Lockout mechanism (anti brute‑force protection)  
- ✅ Encrypted audit logging with tamper detection  
- ✅ Keyfile support (optional second factor)  
- ✅ Dark mode UI (PySide6)  

---

# Architecture Overview

Cryptix follows a modular architecture:

```
GUI (PySide6)
        ↓
Controller / Worker Thread
        ↓
Core Encryption Engine
        ↓
File Handler (Container Format + AAD)
        ↓
Logger (Encrypted Audit Log)
```

Cryptographic logic is fully separated from the GUI layer.

---

# File Format Specification

Encrypted files follow a structured binary layout:

```
[MAGIC]
[VERSION]
[ALGORITHM]
[SALT]
[IV]
[TAG]
[FILENAME_LENGTH]
[FILENAME]
[CIPHERTEXT]
```

Metadata fields are authenticated using AEAD Additional Authenticated Data (AAD).  
Any modification to header or filename results in authentication failure.

See: `FILE_FORMAT.md` for full specification.

---

# Threat Model Summary

Cryptix is designed to protect:

- Local confidential files
- Stolen storage devices
- Offline file analysis
- File tampering attempts

Cryptix does **NOT** protect against:

- Malware infections
- Keyloggers
- Compromised operating systems
- Weak user passwords
- Physical attacks on active systems

See: `THREAT_MODEL.md` for full threat model.

---

# Installation

Clone the repository:

```bash
git clone https://github.com/yourname/cryptix.git
cd cryptix
```

Create a virtual environment:

```bash
python -m venv venv
venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run:

```bash
python main.py
```

---

# Building Executable (Windows)

Cryptix can be packaged using PyInstaller:

```bash
python build.py
```

The executable will be generated in the `dist/` directory.

---

# Security Notice

Cryptix uses modern authenticated encryption primitives and memory‑hard key derivation.

However, security depends on:

- Strong password selection
- Secure operating system environment
- Protection against malware
- Safe device handling

Cryptix reduces risk but does not eliminate all attack vectors.

---

# License

Cryptix is distributed under the Business Source License (BSL) 1.1.

Source code is available for review, audit, and non‑commercial use.

See `LICENSE` for full terms.

---

# Author

Michel Idriss

---