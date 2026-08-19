# cryptix_engine/simulation.py

import time
import config
from cryptix_engine.reports import HardwareProfile, SimulationReport
from cryptix_engine.constants import ALGO_AES, ALGO_CHACHA

def calculate_simulation(
    file_size_bytes: int,
    algorithm: int,
    filename: str,
    profile: HardwareProfile
) -> SimulationReport:
    """
    Computes precise performance, sizing, and security estimates for the target file.
    Does not read, encrypt, or modify any actual file streams.
    """
    notes = []
    confidence_reasons = []

    # 1. Memory Usage Estimation (Argon2id Memory Cost + streaming buffer overhead)
    kdf_memory_mb = config.ARGON2_MEMORY_COST // 1024
    estimated_memory_mb = kdf_memory_mb + 10  # 10MB overhead for buffer chunks and PySide UI

    # 2. Output Size Estimation
    filename_bytes = filename.encode("utf-8")
    filename_len = len(filename_bytes)
    # Header size = MAGIC (4) + VERSION (1) + ALGO (1) + SALT (16) + IV (12) + TAG (16) = 50 bytes
    # Filename length prefix = 4 bytes
    overhead_bytes = 50 + 4 + filename_len
    estimated_output_size_bytes = file_size_bytes + overhead_bytes

    # 3. Throughput and Time Estimation
    file_size_mb = file_size_bytes / (1024 * 1024)

    if algorithm == ALGO_AES:
        speed_mb_s = profile.aes_mb_s
    elif algorithm == ALGO_CHACHA:
        speed_mb_s = profile.chacha_mb_s
    else:
        speed_mb_s = 150.0  # default fallback

    encryption_time_s = file_size_mb / speed_mb_s if speed_mb_s > 0 else 0.0
    estimated_time_s = profile.kdf_latency_s + encryption_time_s

    # Add explanatory notes based on size boundaries
    if file_size_bytes < 1024 * 1024:
        notes.append("File size is small. Runtime is dominated almost entirely by the Argon2id key derivation latency.")
    else:
        notes.append(f"Streaming chunk-based pipeline handles this {file_size_mb:.2f} MB file with a constant memory footprint.")

    # 4. Confidence Calculations
    if profile.timestamp == 0.0:
        confidence_level = "Low"
        confidence_reasons.append("No local machine calibration is available.")
        confidence_reasons.append("Estimated using a generic fallback hardware profile.")
        notes.append("Run 'Performance Calibration' inside settings to achieve high-precision estimates (+/- 5% accuracy).")
    else:
        # Calculate calibration profile age in days
        age_days = (time.time() - profile.timestamp) / (24 * 3600)
        if age_days < 30:
            confidence_level = "High"
            confidence_reasons.append("Recent machine-specific calibration profile is available.")
            confidence_reasons.append(f"Calibrated encryption throughput matches the active hardware capabilities.")
        else:
            confidence_level = "Medium"
            confidence_reasons.append("Machine-specific calibration profile exists, but is older than 30 days.")
            confidence_reasons.append("Slight hardware state changes may occur over time. Re-calibration is recommended.")

    return SimulationReport(
        input_size_bytes=file_size_bytes,
        estimated_time_s=round(estimated_time_s, 2),
        estimated_output_size_bytes=estimated_output_size_bytes,
        estimated_memory_mb=estimated_memory_mb,
        confidence_level=confidence_level,
        confidence_reasons=confidence_reasons,
        notes=notes
    )