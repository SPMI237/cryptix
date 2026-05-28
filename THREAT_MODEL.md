# Cryptix Threat Model

## Overview

This document defines the threat model, assumptions, security guarantees, and limitations of Cryptix.

Cryptix is designed as a local file encryption platform focused on protecting sensitive data against unauthorized access.

---

# Security Objectives

Cryptix aims to provide:

- confidentiality of encrypted files
- integrity verification
- authenticated encryption
- secure password-based key derivation
- protection against offline file access

---

# Assets Protected

Cryptix is intended to protect:

- local files
- confidential documents
- backups
- sensitive user data
- encrypted archives

---

# Threat Actors

Potential threat actors include:

- unauthorized local users
- device thieves
- malicious individuals with file access
- attackers attempting offline file analysis

---

# Threats Mitigated

Cryptix is designed to mitigate:

| Threat | Protection |
|--------|-------------|
| Unauthorized file access | Yes |
| Stolen storage devices | Yes |
| Offline brute-force attacks | Partially mitigated via Argon2id |
| File tampering | Yes via authenticated encryption |
| Metadata manipulation | Partially mitigated |

---

# Threats NOT Mitigated

Cryptix does NOT protect against:

| Threat | Status |
|--------|--------|
| Keyloggers | Not mitigated |
| Malware infections | Not mitigated |
| Compromised operating systems | Not mitigated |
| Weak user passwords | User responsibility |
| Physical attacks on active systems | Not mitigated |
| Memory extraction attacks | Limited protection |

---

# Trust Assumptions

Cryptix assumes:

- the operating system is reasonably secure
- the user chooses strong passwords
- cryptographic libraries are trustworthy
- the execution environment is not actively compromised

---

# Cryptographic Assumptions

Cryptix relies on the security of:

- AES-256-GCM
- ChaCha20-Poly1305
- Argon2id
- secure random number generation

If these primitives are broken or improperly implemented, security guarantees may fail.

---

# File Security Model

Encrypted files are intended to remain confidential without the correct password.

Cryptix stores:
- salts
- nonces
- metadata
- authentication tags

Cryptix does NOT store:
- plaintext passwords
- encryption keys
- plaintext file contents

---

# Security Boundaries

Cryptix focuses on:
- encryption and decryption security
- local data protection
- integrity verification

Cryptix does not attempt to replace:
- antivirus software
- operating system security
- full disk encryption
- endpoint protection systems

---

# User Responsibilities

Users are responsible for:

- maintaining strong passwords
- securing their operating system
- keeping backups
- protecting access to their devices

---

# Future Security Improvements

Planned future enhancements may include:

- secure file shredding
- memory hardening
- MFA integration
- hardware-backed key storage
- plugin security isolation

---

# Disclaimer

No software can guarantee absolute security.

Cryptix reduces risk but cannot eliminate all attack vectors.