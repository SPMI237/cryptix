# cryptix_academy/sandbox.py

import os
import time
import io
from dataclasses import dataclass, field
from typing import List, Dict

import config
from cryptix_engine.kdf import derive_key, generate_salt
from cryptix_engine.container import build_header, parse_header, build_aad
from cryptix_engine.aead import encrypt_stream, verify_stream
from cryptix_engine.exceptions import FormatError, VersionMismatchError, AuthenticationError
from cryptix_engine.constants import ALGO_AES, algorithm_name

@dataclass
class TraceStep:
    stage: str          # "MAGIC", "VERSION", "ALGO", "SALT", "IV", "TAG", "FILENAME", "CIPHERTEXT"
    status: str         # "SUCCESS", "FAILED"
    message: str
    technical_detail: str

class VerificationTrace:
    def __init__(self):
        self.steps: List[TraceStep] = []
        self.success = True
        self.failed_stage = None
        self.released_plaintext = False

    def add_step(self, stage: str, status: str, message: str, technical_detail: str):
        self.steps.append(TraceStep(stage, status, message, technical_detail))
        if status == "FAILED":
            self.success = False
            if self.failed_stage is None:
                self.failed_stage = stage


# =========================================================
# EXPERIMENT ABSTRACTION ENGINE
# =========================================================

class TamperExperiment:
    def __init__(self, name: str, description: str, objective: str, expected_security: str):
        self.name = name
        self.description = description
        self.objective = objective
        self.expected_security = expected_security

    def mutate(self, container_bytes: bytearray) -> bytearray:
        """
        Performs a deterministic mutation over the volatile container bytearray.
        """
        raise NotImplementedError


class CiphertextTamperExperiment(TamperExperiment):
    def __init__(self):
        super().__init__(
            name="Ciphertext Mutation",
            description="Flips a specific bit inside the encrypted ciphertext block.",
            objective="To verify whether an attacker can silently modify encrypted payload data without the decryption key.",
            expected_security="Cryptix must detect the ciphertext alteration and abort decryption before releasing plaintext."
        )

    def mutate(self, container_bytes: bytearray) -> bytearray:
        mutated = bytearray(container_bytes)
        # Flip the very last byte of the ciphertext payload deterministically
        mutated[-1] ^= 0xFF
        return mutated


class MetadataTamperExperiment(TamperExperiment):
    def __init__(self):
        super().__init__(
            name="Metadata (Filename) Mutation",
            description="Modifies a character in the public, unencrypted filename header.",
            objective="To demonstrate that Associated Data (AAD) guarantees filename authenticity even though the filename remains public/readable.",
            expected_security="Cryptix must detect the filename modification and abort verification via AAD mismatch."
        )

    def mutate(self, container_bytes: bytearray) -> bytearray:
        mutated = bytearray(container_bytes)
        
        # Locate the filename block
        # Format: MAGIC(4) + VERSION(1) + ALGO(1) + SALT(16) + IV(12) + TAG(16) = 50 bytes header offset
        # Next 4 bytes represent filename length big-endian
        filename_length = int.from_bytes(mutated[50:54], "big")
        
        # Alter the first byte of the filename deterministically
        if filename_length > 0:
            mutated[54] ^= 0x01
            
        return mutated


class VersionTamperExperiment(TamperExperiment):
    def __init__(self):
        super().__init__(
            name="Format Version Mutation",
            description="Alters the container format version byte inside the magic header zone.",
            objective="To prove that version-mismatch guard rails reject unsupported containers at the parsing phase prior to key processing.",
            expected_security="The parser must reject the mismatch immediately as an unsupported configuration."
        )

    def mutate(self, container_bytes: bytearray) -> bytearray:
        mutated = bytearray(container_bytes)
        # Version byte offset is 4 (right after MAGIC)
        mutated[4] ^= 0x01
        return mutated


class AlgorithmTamperExperiment(TamperExperiment):
    def __init__(self):
        super().__init__(
            name="Algorithm Selector Mutation",
            description="Alters the algorithm ID byte to spoof AES as ChaCha20.",
            objective="To prove that swapping algorithm indicators breaks the structured AEAD verification logic on decryption.",
            expected_security="The decryption cipher must raise an authentication verification error on mismatch."
        )

    def mutate(self, container_bytes: bytearray) -> bytearray:
        mutated = bytearray(container_bytes)
        # Algorithm ID offset is 5 (right after VERSION)
        mutated[5] = 2 if mutated[5] == 1 else 1  # Swaps AES (1) with ChaCha (2)
        return mutated


class TruncationExperiment(TamperExperiment):
    def __init__(self):
        super().__init__(
            name="Container Truncation",
            description="Slices off the trailing 20 bytes of the container stream.",
            objective="To verify that truncated, incomplete, or corrupted streams fail progressive integrity checks.",
            expected_security="The streaming verifier must raise an authentication error due to missing stream segments."
        )

    def mutate(self, container_bytes: bytearray) -> bytearray:
        mutated = bytearray(container_bytes)
        # Slices off trailing 20 bytes deterministically
        return mutated[:-20]


class TagTamperExperiment(TamperExperiment):
    def __init__(self):
        super().__init__(
            name="Authentication Tag Mutation",
            description="Flips a specific bit inside the 16-byte integrity seal/tag.",
            objective="To demonstrate that the digital seal itself cannot be bypassed or silently manipulated by attackers.",
            expected_security="Cryptix must detect the tag mutation and reject the container immediately."
        )

    def mutate(self, container_bytes: bytearray) -> bytearray:
        mutated = bytearray(container_bytes)
        # Tag offset: GCM uses 12-byte nonce, so Tag offset starts at 4 + 1 + 1 + 16 + 12 = 34
        # Flip the first byte of the tag block deterministically
        mutated[34] ^= 0xFF
        return mutated


# =========================================================
# THE SANDBOX ENVIRONMENT
# =========================================================

class TamperLabSandbox:
    def __init__(self):
        self.original_payload = b"CONFIDENTIAL ACADEMY LAB DATA"
        self.filename = "lab_confidential.txt"
        self.password = "academy_sandbox_key_2026"
        self.algorithm = ALGO_AES

        # Generate fresh temporary session credentials in memory only
        self.salt = generate_salt()
        self.key = derive_key(self.password, self.salt)
        self.iv = os.urandom(12)

        # Build Original Container in memory
        self.original_container = self._generate_original_container()

    def _generate_original_container(self) -> bytearray:
        """
        Uses the actual, compiled Cryptix Engine serializer to package
        a fresh in-memory binary container.
        """
        input_stream = io.BytesIO(self.original_payload)
        output_stream = io.BytesIO()

        encrypt_stream(
            input_stream,
            output_stream,
            self.key,
            self.algorithm,
            self.salt,
            self.iv,
            self.filename.encode("utf-8")
        )

        return bytearray(output_stream.getvalue())

    def run_experiment(self, experiment: TamperExperiment) -> tuple[bytearray, VerificationTrace]:
        """
        Clones original bytes, runs the mutation, feeds the result directly to
        the active Cryptix verifier, and builds a structured VerificationTrace.
        Guarantees 100% fail-closed boundary isolation (0 plaintext bytes released).
        """
        tampered_bytes = experiment.mutate(self.original_container)
        trace = VerificationTrace()

        stream = io.BytesIO(tampered_bytes)

        # 1. MAGIC & VERSION HEADER PARSING STAGE
        try:
            magic = stream.read(4)
            if magic != config.MAGIC_HEADER:
                trace.add_step("MAGIC", "FAILED", "Magic header GCA1 not recognized.", f"Read value: {magic!r}")
                return tampered_bytes, trace
            
            trace.add_step("MAGIC", "SUCCESS", "Magic header validated successfully.", "Magic: GCA1")

            version_byte = stream.read(1)
            version = int.from_bytes(version_byte, "big")
            if version != config.VERSION:
                trace.add_step("VERSION", "FAILED", f"Unsupported container version: {version}", "Compatible: 01")
                return tampered_bytes, trace

            trace.add_step("VERSION", "SUCCESS", "Version compatibility confirmed.", f"Version: {version:02d}")

            # 2. ALGO & SALT PARSING
            algorithm = int.from_bytes(stream.read(1), "big")
            salt = stream.read(16)
            
            iv_len = 24 if algorithm == 3 else 12
            iv = stream.read(iv_len)
            tag = stream.read(16)

            filename_length = int.from_bytes(stream.read(4), "big")
            filename_bytes = stream.read(filename_length)

            trace.add_step("PARSER", "SUCCESS", "Container header parsing completed successfully.", 
                           f"Parsed Algorithm: {algorithm_name(algorithm)}")

        except Exception as e:
            trace.add_step("PARSER", "FAILED", f"Header parsing aborted due to stream corruption.", str(e))
            return tampered_bytes, trace

        # 3. CRYPTOGRAPHIC EVALUATION
        try:
            # Re-derive key
            key = derive_key(self.password, salt)

            # Re-read ciphertext segment
            ciphertext = stream.read()

            from cryptix_engine.aead import verify_stream
            
            # Feed tampered stream directly into actual verifier
            # If MAC verification fails, it raises AuthenticationError cleanly!
            with io.BytesIO(ciphertext) as input_stream:
                verify_stream(
                    input_stream,
                    key,
                    algorithm,
                    salt,
                    iv,
                    tag,
                    filename_bytes,
                    return_report=False
                )

            trace.add_step("AUTHENTICATION", "SUCCESS", "AEAD cryptographic authentication verified.", "Tag: Verified")
            trace.released_plaintext = True

        except (AuthenticationError, FormatError, VersionMismatchError) as e:
            trace.add_step("AUTHENTICATION", "FAILED", "Cryptographic tag check failed! Modification or wrong key detected.", str(e))
            trace.released_plaintext = False
        except Exception as e:
            trace.add_step("AUTHENTICATION", "FAILED", "Verification pipeline crashed due to structural corruption.", str(e))
            trace.released_plaintext = False

        return tampered_bytes, trace
