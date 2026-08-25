# tests/test_sandbox.py

import pytest
from cryptix_academy.sandbox import (
    TamperLabSandbox,
    NoOpExperiment,
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

def test_tamper_independence():
    sandbox = TamperLabSandbox()
    orig_clone = bytearray(sandbox.original_container)

    # 1. Run Experiment A (Ciphertext)
    exp_a = CiphertextTamperExperiment()
    bytes_a1, trace_a1 = sandbox.run_experiment(exp_a)
    assert bytes_a1 != orig_clone

    # 2. Run Experiment B (Tag)
    exp_b = TagTamperExperiment()
    bytes_b, trace_b = sandbox.run_experiment(exp_b)
    assert bytes_b != orig_clone
    assert bytes_b != bytes_a1

    # 3. Run Experiment A again and assert identical mutant outputs (No cross-contamination!)
    bytes_a2, trace_a2 = sandbox.run_experiment(exp_a)
    assert bytes_a2 == bytes_a1
    assert sandbox.original_container == orig_clone

def test_original_untampered_container_control_group():
    sandbox = TamperLabSandbox()
    
    # Run the Control Group 'No-Op' experiment
    noop = NoOpExperiment()
    tampered_bytes, trace = sandbox.run_experiment(noop)

    assert trace.success is True
    assert trace.released_plaintext is True
    assert trace.assessment == "✓ SYSTEM INTEGRITY COMPLIANT"
    assert trace.security_preserved is True

    # Decrypt and verify matching plaintext programmatically inside control group
    from cryptix_engine.container import parse_header
    import io
    stream = io.BytesIO(tampered_bytes)
    header_data = parse_header(stream)
    ciphertext = stream.read()

    from cryptix_engine.aead import decrypt_stream
    out_stream = io.BytesIO()
    decrypt_stream(
        io.BytesIO(ciphertext),
        out_stream,
        sandbox.key,
        header_data["algorithm"],
        header_data["salt"],
        header_data["iv"],
        header_data["tag"],
        header_data["filename_bytes"]
    )
    assert out_stream.getvalue() == sandbox.original_payload

def test_byte_level_before_after_comparisons():
    sandbox = TamperLabSandbox()
    exp = CiphertextTamperExperiment()
    mutated_bytes, _ = sandbox.run_experiment(exp)

    # Call comparison helper natively driven by the backend
    diffs = sandbox.compare_containers(sandbox.original_container, mutated_bytes)
    assert len(diffs) == 1
    assert diffs[0]["status"] == "MODIFIED"
    assert diffs[0]["before"] != diffs[0]["after"]

    # Verify truncation outputs
    exp_trunc = TruncationExperiment()
    trunc_bytes, _ = sandbox.run_experiment(exp_trunc)
    # Explicitly assert that the normal sandbox container loses exactly 20 bytes when truncated!
    assert len(sandbox.original_container) - len(trunc_bytes) == 20
    
    diffs_trunc = sandbox.compare_containers(sandbox.original_container, trunc_bytes)
    assert any(d["status"] == "REMOVED" for d in diffs_trunc)
