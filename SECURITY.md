# Security Policy

## Supported Versions

The following versions of Cryptix currently receive security updates and maintenance.

| Version | Supported |
|----------|------------|
| 1.x      | Yes        |
| < 1.0    | No         |

---

## Reporting a Vulnerability

If you discover a security vulnerability in Cryptix, please report it responsibly.

Please include:
- description of the issue
- steps to reproduce
- affected component
- possible impact

Avoid publicly disclosing vulnerabilities before they are reviewed.

---

## Security Principles

Cryptix follows several core security principles:

- modern cryptographic algorithms
- authenticated encryption
- password-based key derivation
- modular architecture
- minimal plaintext exposure
- secure error handling
- metadata authentication using AEAD Additional Authenticated Data (AAD)

---

## Cryptographic Algorithms

Currently supported cryptographic primitives include:

- AES-256-GCM (authenticated encryption)
- ChaCha20-Poly1305 (authenticated encryption)
- Argon2id (memory-hard password-based key derivation, 100MB configuration)

Additional algorithms may be introduced in future versions.

---

## Important Security Notes

Cryptix is designed to protect local files against unauthorized access.

Cryptix does NOT protect against:
- malware infections
- keyloggers
- compromised operating systems
- weak passwords
- physical attacks on active systems

Users remain responsible for maintaining overall system security.

---

## Best Practices

Users are encouraged to:
- use strong passwords
- maintain secure backups
- keep systems updated
- avoid running unknown software
- securely store encrypted files

---

## Disclaimer

Cryptix is provided "AS IS" without warranty of any kind.

The developers are not responsible for:
- data loss
- corrupted files
- misuse of the software
- damages resulting from improper usage