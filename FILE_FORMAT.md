# Cryptix File Format Specification

## Overview

Cryptix encrypted files use a structured binary format designed to support:
- multiple encryption algorithms
- authenticated encryption
- future extensibility
- version compatibility

The format stores metadata required for decryption while avoiding exposure of plaintext content.

---

# General Structure

Each encrypted file contains:

| Section | Purpose |
|----------|----------|
| Magic Header | Identify Cryptix file |
| Version | File format version |
| Algorithm ID | Encryption algorithm used |
| Salt | Key derivation salt |
| Nonce | Encryption nonce/IV |
| Authentication Tag | Integrity verification |
| Ciphertext | Encrypted file content |

---

# File Layout

Example layout:

```text
[MAGIC][VERSION][ALGORITHM][SALT][NONCE][TAG][CIPHERTEXT]
```

---

# Section Details

## 1. Magic Header

Purpose:
Identify files encrypted by Cryptix.

Example:

```text
CRX1
```

---

## 2. Version

Indicates Cryptix file format version.

Example:

```text
01
```

This allows future compatibility handling.

---

## 3. Algorithm Identifier

Specifies the encryption algorithm used.

Example values:

| ID | Algorithm |
|----|------------|
| 01 | AES-256-GCM |
| 02 | ChaCha20-Poly1305 |

Future algorithms may be added.

---

## 4. Salt

Used during password-based key derivation.

Purpose:
- prevent rainbow table attacks
- ensure unique derived keys

Generated securely for every encryption operation.

---

## 5. Nonce / Initialization Vector

Unique value required by authenticated encryption algorithms.

Requirements:
- randomly generated
- never reused with same key

---

## 6. Authentication Tag

Used to verify:
- integrity
- authenticity
- tampering detection

If verification fails:
- decryption must stop immediately

---

## 7. Ciphertext

Contains encrypted file content.

Plaintext data is never stored directly.

---

# Security Considerations

Cryptix file format is designed to:
- prevent plaintext leakage
- support authenticated encryption
- allow future extensibility
- separate metadata from encrypted content

---

# Future Compatibility

Future versions may introduce:
- additional algorithms
- metadata extensions
- compression support
- hybrid encryption modes

Backward compatibility mechanisms may be added in later releases.

---

# Notes

This specification describes the current Cryptix file structure and may evolve over time.