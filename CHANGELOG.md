# Changelog

## v1.4.0 — Intelligent Encryption Release

### Engine
- Integrated next-generation **XChaCha20-Poly1305** authenticated encryption (ALGO_XCHACHA = 3) utilizing 192-bit (24-byte) nonces.
- Upgraded container parsing to dynamically adjust IV-header read lengths (24 bytes for XChaCha, 12 bytes for GCM/ChaCha20).
- Created a decoupled **Performance Service** (`utils/performance.py`) automating local machine calibration.
- Added programmatic estimation formulas under `cryptix_engine/simulation.py` producing a structured `SimulationReport`.

### Explainable Security & GUI
- Implemented **Pre-Flight Simulation Mode**: Clicking Simulation displays a structured checklist, estimated time, memory ceilings, output sizes, and confidence levels.
- Designed a custom, high-contrast, scrollable **Simulation Dialog** (`ui/simulation_dialog.py`) with collapsible educational panels explaining cryptographic decisions (KDF memory-hardness, AEAD boundaries, and cipher acceleration).
- Implemented **First-Launch Calibration Prompts**: On initial app launch, users are prompted to run a fast, non-intrusive 5-second performance calibration to train the simulation model.
- Added dynamic badging badglets for XCHACHA (Purple highlight indicators) inside the settings HUD.

### Stability & Testing
- Expanded automated regression suite to **17 comprehensive tests** (`tests/test_simulation.py`, `tests/test_performance.py`, and `test_encrypt_decrypt_roundtrip_xchacha`).
- Added persistent `settings.json` and encrypted log assets to `.gitignore` rules to keep development repositories clean.


## v1.3.0 — Explainable Core Release

### Engine
- Full cryptographic engine extraction (cryptix_engine package)
- Structured exception hierarchy (CryptixError base class)
- Stream-based encryption, decryption, and verification

### Explainable Security
- Container Structure Analysis (no password)
- Authenticated Container Analysis (password required)
- IntegrityReport model with failure-stage tracking
- Deterministic container fingerprint system
- Security Advisor (facts + guidance + collapsible guarantees panel)
- Engine extraction completed
- Structured exception hierarchy
- CI enforced testing
- Dependency pinning
- Build documentation

### Stability
- pytest regression suite (12 tests)
- GitHub Actions CI enforcement on every push
- Pinned runtime and dev dependencies
- Reproducible build documentation (BUILD.md)
- Release SHA256 hash documentation
- Fixed startup crash when opening encrypted files via file association
- Improved installer configuration.

### Branding
- Application renamed to Cryptix Core
- Executable renamed to CryptixCore.exe
- Installer renamed to CryptixCore_Installer_v1.3.0.exe
- File extension remains `.cryptix` (platform-level container format)

### Distribution Improvements
- Windows installer with desktop and Start Menu integration
- `.cryptix` file association support
- Proper application icon integration

### System Integration
- Audit logs moved to user AppData for installed version compatibility
- Automatic GitHub update checker (non-intrusive)

### Usability & Transparency
- Performance benchmark mode (AES‑256‑GCM, ChaCha20‑Poly1305, Argon2id)
- Persistent user settings (theme, algorithm, secure delete preferences)

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