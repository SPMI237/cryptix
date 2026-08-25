Cryptix Core v1.5.0 — Stage 6: The Tamper Lab Architectural Specification
1. Introduction & Core Objective
The Tamper Lab is the centerpiece educational feature of the v1.5.0 — Cryptography Laboratory release.

Its core objective is to provide a memory-isolated, secure, and reproducible testing environment where students can programmatically execute deterministic modifications (attacks) on valid Cryptix containers, visually observing how the actual production verification pipeline defends the system and failing closed.

The central guiding principle is:

💡 "The Tamper Lab should not simulate Cryptix security. It should attack a real temporary Cryptix container and let the real Cryptix security machinery defend it."

2. Platform Bounded Isolation (Memory Only)
To preserve strict system integrity and prevent any accidental filesystem corruption:

The sandbox operates exclusively in volatile memory using io.BytesIO streams and mutable bytearray buffers.
No files are read from or written to the disk at any point.
Each experiment session generates a fresh, ephemeral 128-bit session key (secrets.token_hex(16)) and an immutable original container cache. Every mutation starts from a clean, fresh clone, ensuring complete experimental independence.
3. The Two Defensive Layers
The laboratory distinguishes between two distinct, progressive defensive boundaries:

3.1 Layer 1: Structural Format Validation
Evaluated by the authoritative parse_header() routine inside cryptix_engine/container.py. This layer validates Magic Headers, version compatibility, algorithm ID recognition, and boundary lengths before key derivation or cryptographic decrypt streams are initialized.

Anomalies: Swapping AES with XChaCha20 (triggering a 24-byte IV read shift) or modifying version bytes will be caught at this layer as a FormatError or VersionMismatchError.
3.2 Layer 2: Cryptographic AEAD Verification
Evaluated by verify_stream() inside cryptix_engine/aead.py. It progressively processes ciphertext and AAD bytes against the computed 16-byte authentication tag.

Anomalies: Ciphertext bit-flipping, filename metadata tampering, or tag manipulation are caught at this layer, raising AuthenticationError (MAC failed).
Fail-Closed Guarantee: Releasing unauthenticated plaintext before the tag is verified is mathematically prohibited. Under any tampering event, released_plaintext is set to False and zero plaintext bytes are ever returned.
4. Reusable Mutator Experiments
Each test case inherits from a generic TamperExperiment base class:

text

TamperExperiment
   ├── name
   ├── description
   ├── objective
   ├── expected_security (The modified container must not decrypt)
   └── mutate(container_bytes) -> bytearray
The six deterministic subclasses are:

CiphertextTamperExperiment: Flips the very last bit of the ciphertext payload deterministically.
MetadataTamperExperiment: Programmatically analyzes the active algorithm, calculates the dynamic filename length offset, and flips a bit in the unencrypted filename string.
VersionTamperExperiment: Targets offset 4 and increments the format version code.
AlgorithmTamperExperiment: Targets offset 5 and swaps AES (1) with ChaCha (2).
TruncationExperiment: Dynamically truncates the trailing portion of the container, safe against boundary crashes on small streams.
TagTamperExperiment: Targets offset 34 and flips a bit in the integrity seal.
5. Granular Verification Trace Engine
Instead of collapsing results, TamperLabSandbox.run_experiment() builds a structured VerificationTrace composed of 8 chronological TraceStep facts:

MAGIC -> VERSION -> ALGO -> SALT -> IV -> TAG -> FILENAME -> AUTHENTICATION
The UI dialog consumes this structured data and renders:

A Before & After Hex Inspector showing the mutated byte coordinates.
An Educational Trace Terminal showing exactly which layer of our defense pipeline caught and blocked the attack.