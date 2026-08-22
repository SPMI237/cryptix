Cryptix Core v1.4.0 — Architectural Specification (Simulation & XChaCha20)

1. Introduction
This specification outlines the design and integration protocols for the two main components of the v1.4.0 (Intelligent Encryption) release:

The Decoupled Performance Service & Simulation Engine: Machine-specific estimations that advise users prior to data execution.
Next-Generation Authenticated Cryptography: Integration of collision-resistant XChaCha20-Poly1305 (ALGO_XCHACHA = 3) into the binary pipeline.

2. Decoupled Performance Service (utils/performance.py)
2.1 The Throughput Cache Design
To prevent executing slow, CPU-blocking, and repetitive benchmarks every time a user requests a file simulation, we decoupling the measurement flow into a dedicated service.
The service stores a serialized HardwareProfile dataclass directly in settings.json:

JSON

{
    "hardware_profile": {
        "aes_mb_s": 224.52,
        "chacha_mb_s": 248.11,
        "kdf_latency_s": 0.115,
        "timestamp": 1787282312.42
    }
}

2.2 First-Launch Prompt Calibration Protocol
When MainWindow is initialized, if the cached "hardware_profile" is missing from the settings dictionary, the app triggers a 3.5-second delayed calibration reminder.
The popup raises the window to focus, prompting a secure 10MB memory-encryption run to record system performance. Once calibrated, this prompt is skipped on future boots.

3. The Estimation Formulas (cryptix_engine/simulation.py)
3.1 Time Estimation
Total time represents the additive latency of memory-hard key derivation plus linear encryption throughput:
Time (s)
=
KDF Latency (s)
+
File Size (MB)
Calibrated Cipher Speed (MB/s)
Time (s)=KDF Latency (s)+ 
Calibrated Cipher Speed (MB/s)
File Size (MB)
​
 

3.2 Sizing Estimator
Calculates precise, byte-aligned container sizing bounds based on metadata packaging rules:
Output (bytes)
=
File Size (bytes)
+
Header (50 bytes)
+
Filename Length Prefix (4 bytes)
+
Encoded Filename Length (bytes)
Output (bytes)=File Size (bytes)+Header (50 bytes)+Filename Length Prefix (4 bytes)+Encoded Filename Length (bytes)

3.3 Confidence Calculation Metrics
High Confidence (5 Stars): local calibration is present and has been calibrated within the last 30 days.
Medium Confidence (3 Stars): local calibration is present but is older than 30 days.
Low Confidence (1 Star): no local calibration is present. The engine utilizes conservative default benchmarks (150 MB/s for AES, 130 MB/s for ChaCha) and guides the user to run calibration.
4. XChaCha20-Poly1305 Protocol Integration
4.1 Nonce Expansion Strategy
Standard ChaCha20 uses a 96-bit (12-byte) IV. While highly secure, generating 12 bytes randomly exposes bulk operations (like folder encryption of millions of files) to a marginal birthday-bound collision risk.
XChaCha20-Poly1305 extends the nonce size to 192 bits (24 bytes), mathematically eliminating nonce-reuse concerns under random generation.

4.2 Dynamic Parsing Layout
Because XChaCha20-Poly1305 containers contain a larger IV block, the container parser must dynamically scale.
Inside parse_header, the loader parses the algorithm identifier first, and dynamically scales its IV read size to 24 bytes if algorithm == 3, preserving standard 12-byte reads for GCM and standard ChaCha.
This preserves full backward compatibility with older v1.3.0 containers.

5. Security & Decoupling Mandates
Read-Only Streams: The Simulation Engine operates only on numeric attributes and file metadata. It does not open, read, or write to active file streams, ensuring simulation can never corrupt data under failure.
UI Decoupling: Estimations are fully computed inside the standalone cryptix_engine sub-package. PySide6 is strictly restricted to presenting the outputs visually.
