# Changelog

## v1.1.0 — Usability & Workflow Enhancement Update

### New Features
- Drag-and-drop support with semi-transparent overlay feedback
- Built-in secure password generator
- Multi-file batch encryption, decryption, and verification
- Secure delete after decryption option

### Improvements
- Upgraded password strength indicator to compact dynamic progress bar
- Improved single-file success messaging in batch mode
- Refined verify workflow UX messaging
- Strengthened folder secure delete handling

### Stability
- Preserved cryptographic core integrity (AES-256-GCM, ChaCha20-Poly1305, Argon2id)
- No changes to file format structure

## v1.0.0 — Initial Public Release

### Core Cryptography
- AES-256-GCM authenticated encryption
- ChaCha20-Poly1305 authenticated encryption
- Argon2id key derivation (100MB memory configuration)
- Metadata authentication using AEAD AAD
- Structured versioned encrypted container format

### Security Features
- Integrity verification mode
- Lockout protection (anti brute-force)
- Secure delete option (basic overwrite)
- Encrypted audit logging
- Optional keyfile support

### Architecture
- Modular core / UI separation
- Streaming encryption/decryption
- PySide6 migration (LGPL compliance)

### Documentation
- Threat model specification
- Security policy
- File format specification
- Third-party license transparency
- Custom Source-Available License v1.1