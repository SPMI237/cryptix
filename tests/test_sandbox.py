# tests/test_sandbox.py

import pytest
from cryptix_academy.sandbox import (
    TamperLabSandbox,
    CiphertextTamperExperiment,
    MetadataTamperExperiment,
    VersionTamperExperiment,
    AlgorithmTamperExperiment,
    TruncationExperiment,
    TagTamperExperiment
)
from cryptix_engine.exceptions import FormatError, VersionMismatchError, AuthenticationError

def test_sandbox_safety_isolation():
    # Verify sandbox operates purely in memory with zero file locks
    sandbox = TamperLabSandbox()
    assert isinstance(sandbox.original_container, bytearray)
    assert len(sandbox.original_container) > 50

    # Assert original container is immutable across clone instances
    orig_clone = bytearray(sandbox.original_container)
    
    exp = CiphertextTamperExperiment()
    tampered_bytes, trace = sandbox.run_experiment(exp)

    # The returned mutated bytes must differ from original, but the original remains completely untouched!
    assert tampered_bytes != orig_clone
    assert sandbox.original_container == orig_clone
    assert trace.success is False
    assert trace.released_plaintext is False

def test_valid_sandbox_container_verifies():
    sandbox = TamperLabSandbox()
    
    # Assert that an untampered/original container verifies successfully with 100% success trace!
    # We test this by creating a mock 'No-Op' experiment that does not alter anything!
    from cryptix_academy.sandbox import TamperExperiment
    class NoOpExperiment(TamperExperiment):
        def __init__(self):
            super().__init__("No-Op", "Does nothing", "Valid verification", "Succeeds")
        def mutate(self, container_bytes):
            return bytearray(container_bytes)

    noop = NoOpExperiment()
    _, trace = sandbox.run_experiment(noop)
    
    assert trace.success is True
    assert trace.released_plaintext is True
    assert len(trace.steps) == 8  # MAGIC, VERSION, ALGO, SALT, IV, TAG, FILENAME, AUTHENTICATION
    assert all(step.status == "SUCCESS" for step in trace.steps)

def test_ciphertext_tamper_fails():
    sandbox = TamperLabSandbox()
    exp = CiphertextTamperExperiment()
    _, trace = sandbox.run_experiment(exp)

    # Ciphertext tampering must be caught in the AUTHENTICATION step, NOT the parser stage!
    assert trace.success is False
    assert trace.released_plaintext is False
    assert trace.failed_stage == "AUTHENTICATION"

def test_metadata_tamper_fails():
    sandbox = TamperLabSandbox()
    exp = MetadataTamperExperiment()
    _, trace = sandbox.run_experiment(exp)

    # Metadata (filename) tampering must be caught in the AUTHENTICATION stage due to AAD mismatch
    assert trace.success is False
    assert trace.released_plaintext is False
    assert trace.failed_stage == "AUTHENTICATION"

def test_version_tamper_fails():
    sandbox = TamperLabSandbox()
    exp = VersionTamperExperiment()
    _, trace = sandbox.run_experiment(exp)

    # Version mismatch must be caught in the VERSION stage during format checks before KDF processing!
    assert trace.success is False
    assert trace.released_plaintext is False
    assert trace.failed_stage == "VERSION"

def test_algorithm_tamper_fails():
    sandbox = TamperLabSandbox()
    exp = AlgorithmTamperExperiment()
    _, trace = sandbox.run_experiment(exp)

    # Swapping algorithm indicators must fail authentication checks on decryption
    assert trace.success is False
    assert trace.released_plaintext is False
    assert trace.failed_stage == "AUTHENTICATION"

def test_truncation_fails():
    sandbox = TamperLabSandbox()
    exp = TruncationExperiment()
    _, trace = sandbox.run_experiment(exp)

    # Truncation must be caught either in header parses or during streaming decryption checks
    assert trace.success is False
    assert trace.released_plaintext is False

def test_tag_tamper_fails():
    sandbox = TamperLabSandbox()
    exp = TagTamperExperiment()
    _, trace = sandbox.run_experiment(exp)

    # Mutating tag bytes fails MAC checks
    assert trace.success is False
    assert trace.released_plaintext is False
    assert trace.failed_stage == "AUTHENTICATION"
