# Cryptix Core v1.4.0 — Release Notes
**Theme**: Intelligent Encryption  
**Release Date**: 2026-08-22  

---

## 1. Overview
Cryptix Core v1.4.0 transitions the platform from a silent file encryption utility into an **intelligent, explainable data protection suite**. This release empowers users to make highly informed, machine-specific security decisions before executing cryptographic operations. 

It introduces a **Performance Service** that calibrates local hardware, a mathematical **Simulation Engine** that estimates resource consumption and runtimes, and a gorgeous **Takeoff Encryption Plan** visual panel. Cryptographically, it integrates the collision-resistant **XChaCha20-Poly1305** algorithm natively into the core streaming pipeline.

---

## 2. Major Additions & Technical Inventory

### 2.1 Pre-Flight Simulation Mode
*   **What it does**: Computes performance, sizing, memory consumption, and security parameters before modifying any file on disk.
*   **Calculations**:
    *   **Time Estimation**: 
        $$\text{Estimated Time} = \frac{\text{File Size (MB)}}{\text{Calibrated Speed (MB/s)}} + \text{Argon2id KDF Latency}$$
    *   **Memory Estimation**: Evaluates constant peak memory ceiling by pulling configuration Argon2 memory costs (`100 MB`) and adding PySide UI overhead (`~10 MB`).
    *   **Output Size Estimation**: Calculates the precise output size down to the exact byte by analyzing file size + magic headers (50 bytes) + filename length prefix (4 bytes) + encoded filename UTF-8 byte length.

### 2.2 Reusable Performance Service (`utils/performance.py`)
*   **Decoupled Design**: Isolated completely from GUI or simulation dialog states. Can be consumed by command-line interfaces or future Vault modules.
*   **Machine Calibration**: Runs a secure, lightweight 10MB test to capture true `aes_mb_s`, `chacha_mb_s`, and KDF latency metrics on your system, caching them inside `settings.json`.
*   **First-Launch Calibration Prompts**: On very first launch, the main window raises and activates a modal prompt asking if the user wants to calibrate. This optimizes estimates dynamically.

### 2.3 XChaCha20-Poly1305 Integration
*   **Primitives**: Incorporates `ALGO_XCHACHA = 3` using a 192-bit (24-byte) random nonce/IV. This mathematically eliminates any theoretical risk of random IV reuse collisions under infinite operations.
*   **Dynamic Container Parsing**: Upgraded `cryptix_engine/container.py` (`parse_header`) to dynamically read 24 bytes of IV if the algorithm ID is `3` (XChaCha), and 12 bytes if it is `1` (AES) or `2` (ChaCha20). This preserves absolute container integrity.

### 2.4 Explanatory UI Dialog
*   **Pre-Flight Dialog**: Styled in our tactical dark theme. Displays checklist status (`✓ Target Loaded`, `✓ Password Evaluated`), performance gauges, and stars-based confidence ratings.
*   **Collapsible Explanations**: Educates users about the *why* behind security primitives (e.g., Argon2id memory hardness, AEAD tag checks, and cipher acceleration differences).

---

## 3. Cryptographic & Security Properties
*   **Confidentiality**: Maintained across all ciphers via 256-bit keys.
*   **Authenticity & Integrity**: Enforced through AEAD tag validation at the end of the streaming pipeline.
*   **Collision Resistance**: Dramatically heightened on directory-walk bulk operations by choosing the new 24-byte nonce XChaCha algorithm.
*   **Memory Hygiene**: Zeroed key parameters securely on task completion.

---

## 4. Test & Verification Matrix
The automated test suite has been expanded from **12 to 17 tests**, adding full regression protection for:
1.  **Fallback Calibration Loading**: Verifies system falls back gracefully to default profiles if no calibration file is found.
2.  **Calibration Saving**: Assures measured speeds are correctly roundtripped and cached.
3.  **Simulation Sizing Calculations**: Proves output container sizes are estimated accurately down to the exact byte.
4.  **Confidence Scoring Logic**: Confirms that fresh profiles mark estimates as "High" confidence, while generic fallbacks are "Low."
5.  **XChaCha20-Poly1305 Roundtrip**: Ensures the new primitive encrypts, decrypts, and verifies successfully under streaming loads.

All tests are verified and fully operational under PyTest.

---

## 5. Backward Compatibility
*   **v1.3.0 Containers**: 100% compatible. When decrypting, `parse_header` detects version `01` and standard algorithm codes, correctly scaling its header parsing bounds.
*   **Upgrade Path**: No migrations required; simply replace old files and run calibration to unlock v1.4.0 estimations.
