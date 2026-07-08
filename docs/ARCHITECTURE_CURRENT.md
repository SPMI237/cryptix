Cryptix Current Architecture (v1.2)

1. High-Level Overview
Cryptix v1.2 is a layered desktop application structured as:

text

User
  ↓
MainWindow (GUI Layer)
  ↓
WorkerThread (Execution Layer)
  ↓
File Handler (Workflow Layer)
  ↓
Crypto Modules (KDF + AEAD)
  ↓
Logger / Settings (Utility Layer)
  ↓
Filesystem

2. Layer Breakdown
2.1 GUI Layer — ui/main_window.py
Responsible for:

User interaction
File selection
Drag-and-drop
Password entry
UI feedback
Status indicators
Settings persistence
Benchmark trigger
Update check trigger
Does NOT perform cryptography directly.

Delegates heavy work to WorkerThread.

2.2 Execution Layer — WorkerThread
Responsible for:

Running encryption/decryption/verify asynchronously
Preventing UI freeze
Emitting progress signals
Handling batch operations
Acts as mediator between GUI and File Handler.

2.3 Workflow Layer — file_handler.py
Responsible for:

File format parsing
Container structure
Streaming encryption/decryption
Folder ZIP creation
Metadata binding (AAD)
Secure delete logic
Calls crypto primitives but does not implement them.

2.4 Crypto Layer
Includes:

kdf.py → Argon2id key derivation
aes_gcm.py → AES‑256‑GCM
ChaCha20‑Poly1305 usage via PyCryptodome
Pure cryptographic operations.

No UI awareness.

2.5 Utility Layer
Includes:

logger.py → Encrypted audit logging
settings.py → Persistent configuration
benchmark.py → Performance measurement
Independent of GUI where possible.

3. Data Flow Example — Encrypt File
text

User selects file
  ↓
MainWindow.start_encrypt()
  ↓
WorkerThread(mode="encrypt")
  ↓
file_handler.encrypt_path()
  ↓
derive_key()
  ↓
AES / ChaCha encryption
  ↓
Write structured container
  ↓
Return result
  ↓
MainWindow.on_success()

4. Current Coupling Observations
GUI directly knows file paths.
WorkerThread manages batch logic.
file_handler mixes file IO and crypto orchestration.
Crypto modules are relatively isolated.
Logger writes to AppData.
Settings loaded and applied in GUI.

5. Architectural Strengths
✅ Clear separation between GUI and crypto
✅ Crypto logic not embedded in UI
✅ File format explicitly versioned
✅ AAD metadata authentication
✅ Structured streaming

6. Architectural Weaknesses
⚠️ Engine is not yet isolated as a reusable module
⚠️ Workflow logic and crypto orchestration are combined in file_handler.py
⚠️ No formal engine API layer defined
⚠️ Some UI logic still mixed with workflow decisions

End of document.

