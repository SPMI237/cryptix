# cryptix_academy/sandbox.py

import os
import io
import secrets
from dataclasses import dataclass
from typing import List

import config
from cryptix_engine.kdf import derive_key, generate_salt
from cryptix_engine.container import parse_header
from cryptix_engine.aead import encrypt_stream
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
        self.assessment = ""
        self.security_preserved = False

    def add_step(self, stage: str, status: str, message: str, technical_detail: str):
        self.steps.append(TraceStep(stage, status, message, technical_detail))
        if status == "FAILED":
            self.success = False
            if self.failed_stage is None:
                self.failed_stage = stage


# =========================================================
# EXPERIMENT ABSTRACTION ENGINE
# =========================================================

def locate_tag_offset(container_bytes: bytes) -> int:
    """
    Dynamically calculates the tag offset by parsing the active algorithm ID.
    Supports AES (12-byte IV), ChaCha (12-byte IV), and XChaCha (24-byte IV).
    MAGIC (4) + VERSION (1) + ALGO (1) + SALT (16) = 22 bytes offset for IV.
    """
    algo_id = container_bytes[5]
    iv_len = 24 if algo_id == 3 else 12  # 3 is ALGO_XCHACHA
    return 22 + iv_len


def locate_filename_offset(container_bytes: bytes) -> int:
    """
    Dynamically calculates the filename length prefix offset by parsing the active algorithm ID.
    Supports AES (12-byte IV), ChaCha (12-byte IV), and XChaCha (24-byte IV).
    MAGIC (4) + VERSION (1) + ALGO (1) + SALT (16) = 22 bytes offset for IV.
    """
    algo_id = container_bytes[5]
    iv_len = 24 if algo_id == 3 else 12  # 3 is ALGO_XCHACHA
    # Tag starts right after IV (offset: 22 + iv_len) and is 16 bytes.
    # Filename length starts right after Tag.
    # Total offset: 22 + iv_len + 16 = 38 + iv_len
    return 38 + iv_len


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


class NoOpExperiment(TamperExperiment):
    def __init__(self):
        super().__init__(
            name="No-Op",
            description="Maintains the container in its pristine, original form.",
            objective="To verify that the unmodified, authenticated container decrypts and validates successfully as our control baseline.",
            expected_security="Cryptix must decrypt and authenticate this pristine container, verifying system integrity."
        )

    def mutate(self, container_bytes: bytearray) -> bytearray:
        return bytearray(container_bytes)


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
        
        # Locate the filename length offset dynamically based on algorithm IV size
        length_offset = locate_filename_offset(mutated)
        filename_length = int.from_bytes(mutated[length_offset:length_offset + 4], "big")
        
        # Alter the first byte of the filename block deterministically
        if filename_length > 0:
            filename_start = length_offset + 4
            mutated[filename_start] ^= 0x01
            
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
            description="Slices off the trailing portion of the container stream.",
            objective="To verify that truncated, incomplete, or corrupted streams fail progressive integrity checks.",
            expected_security="The streaming verifier must raise an authentication error due to missing stream segments."
        )

    def mutate(self, container_bytes: bytearray) -> bytearray:
        mutated = bytearray(container_bytes)
        # Safely slice off a portion without exceeding bounds on unusually small containers
        trunc_len = min(20, len(mutated) // 2)
        return mutated[:-trunc_len] if trunc_len > 0 else mutated


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
        # Locate the tag offset dynamically based on active algorithm IV length
        tag_offset = locate_tag_offset(mutated)
        # Flip the first byte of the tag block deterministically
        mutated[tag_offset] ^= 0xFF
        return mutated


# =========================================================
# THE SANDBOX ENVIRONMENT
# =========================================================

class TamperLabSandbox:
    def __init__(self):
        self.original_payload = b"CONFIDENTIAL ACADEMY LAB DATA"
        self.filename = "lab_confidential.txt"
        
        # Generate an ephemeral session password (temporary and unique per session)
        self.password = secrets.token_hex(16)
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

    @staticmethod
    def compare_containers(original: bytes, tampered: bytes) -> List[dict]:
        """
        Compares original and tampered containers byte-by-byte and returns a structured list
        of offsets and modification differences for the visual Before/After Hex Inspector.
        """
        differences = []
        min_len = min(len(original), len(tampered))

        for idx in range(min_len):
            orig_byte = original[idx]
            tamp_byte = tampered[idx]
            if orig_byte != tamp_byte:
                differences.append({
                    "offset": f"0x{idx:04X}",
                    "before": f"{orig_byte:02X}",
                    "after": f"{tamp_byte:02X}",
                    "status": "MODIFIED"
                })

        # Capture truncation boundary differences
        if len(tampered) < len(original):
            differences.append({
                "offset": f"0x{len(tampered):04X}",
                "before": f"{original[len(tampered)]:02X}...",
                "after": "[TRUNCATED]",
                "status": "REMOVED"
            })

        return differences

    def run_experiment(self, experiment: TamperExperiment) -> tuple[bytearray, VerificationTrace]:
        """
        Clones original bytes, runs the mutation, feeds the result directly to
        the active Cryptix verifier, and builds a structured, granular VerificationTrace.
        Guarantees 100% fail-closed boundary isolation (0 plaintext bytes released).
        """
        tampered_bytes = experiment.mutate(self.original_container)
        trace = VerificationTrace()

        stream = io.BytesIO(tampered_bytes)

        # 1. THE AUTHORITATIVE PARSER AND INTEGRITY CHECK
        try:
            # Re-read and parse header data natively using the actual parse_header() routine!
            header_data = parse_header(stream)

            # Record granular progress trace details
            trace.add_step("MAGIC", "SUCCESS", "Magic GCA1 header validated.", "Value: GCA1")
            trace.add_step("VERSION", "SUCCESS", "Format Version compatible.", f"Version: {config.VERSION:02d}")

            algorithm = header_data["algorithm"]
            salt = header_data["salt"]
            iv = header_data["iv"]
            tag = header_data["tag"]
            filename_bytes = header_data["filename_bytes"]

            trace.add_step("ALGO", "SUCCESS", f"Algorithm recognized: {algorithm_name(algorithm)}", f"ID: {algorithm:02d}")
            trace.add_step("SALT", "SUCCESS", f"Salt extracted successfully.", f"Salt length: {len(salt)} bytes")
            trace.add_step("IV", "SUCCESS", f"Initialization Vector (Nonce) extracted.", f"IV length: {len(iv)} bytes")
            trace.add_step("TAG", "SUCCESS", f"Authentication Tag extracted.", f"Tag length: {len(tag)} bytes")
            trace.add_step("FILENAME", "SUCCESS", f"Associated filename extracted: {filename_bytes.decode('utf-8', errors='replace')}", f"Length: {len(filename_bytes)} bytes")

        except FormatError as e:
            trace.add_step("MAGIC", "FAILED", "Magic GCA1 header verification failed.", str(e))
        except VersionMismatchError as e:
            # Record Magic as successful before checking Version
            trace.add_step("MAGIC", "SUCCESS", "Magic GCA1 header validated.", "Value: GCA1")
            trace.add_step("VERSION", "FAILED", "Format Version check failed.", str(e))
        except Exception as e:
            trace.add_step("PARSER", "FAILED", "Header parsing failed due to structural corruption.", str(e))

        # 2. CRYPTOGRAPHIC VERIFICATION STAGE
        if trace.success:
            try:
                # Re-derive key
                key = derive_key(self.password, salt)

                # Re-read remaining ciphertext segment
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

        # 3. EXPECTED VS ACTUAL SECURITY OUTCOME ASSESSMENT
        is_control_group = (experiment.name == "No-Op")
        if is_control_group:
            if trace.success and trace.released_plaintext:
                trace.assessment = "✓ SYSTEM INTEGRITY COMPLIANT"
                trace.security_preserved = True
            else:
                trace.assessment = "🚨 SYSTEM INTEGRITY BREACHED!"
                trace.security_preserved = False
        else:
            # Tamper experiments must fail and release ZERO plaintext
            if not trace.success and not trace.released_plaintext:
                trace.assessment = "✓ SECURITY BOUNDARY PRESERVED"
                trace.security_preserved = True
            else:
                trace.assessment = "🚨 SECURITY BOUNDARY VIOLATION!"
                trace.security_preserved = False

        return tampered_bytes, trace
