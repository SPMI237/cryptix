import hashlib
import config
from cryptix_engine.reports import ContainerStructureReport
from cryptix_engine.exceptions import FormatError, VersionMismatchError
from cryptix_engine.constants import algorithm_name


def build_header(algorithm: int, salt: bytes, iv: bytes) -> bytes:
    return (
        config.MAGIC_HEADER
        + config.VERSION.to_bytes(1, "big")
        + algorithm.to_bytes(1, "big")
        + salt
        + iv
    )

import config
from cryptix_engine.exceptions import FormatError, VersionMismatchError


def parse_header(stream):
    magic = stream.read(4)
    if magic != config.MAGIC_HEADER:
        raise FormatError("Invalid file format")

    version = int.from_bytes(stream.read(1), "big")
    if version != config.VERSION:
        raise VersionMismatchError(f"Unsupported file version: {version}")

    algorithm = int.from_bytes(stream.read(1), "big")
    salt = stream.read(16)
    iv = stream.read(12)
    tag = stream.read(16)

    filename_length = int.from_bytes(stream.read(4), "big")
    filename_bytes = stream.read(filename_length)

    return {
        "algorithm": algorithm,
        "salt": salt,
        "iv": iv,
        "tag": tag,
        "filename_bytes": filename_bytes,
    }

def build_aad(header: bytes, filename_bytes: bytes) -> bytes:
    filename_length_bytes = len(filename_bytes).to_bytes(4, "big")
    return header + filename_length_bytes + filename_bytes    

def analyze_container_structure(stream):
    report = ContainerStructureReport(
        container_detected=False,
        header_valid=False,
        compatible=False,
        notes=[]
    )

    try:
        magic = stream.read(4)
        if magic != config.MAGIC_HEADER:
            report.notes.append("Magic header not recognized.")
            return report

        report.container_detected = True
        report.header_valid = True

        version = int.from_bytes(stream.read(1), "big")
        report.format_version = version

        algorithm = int.from_bytes(stream.read(1), "big")
        report.algorithm = algorithm
        report.notes.append(f"Algorithm: {algorithm_name(algorithm)}")

        if version == config.VERSION:
            report.compatible = True
        else:
            report.compatible = False
            report.notes.append("Container version differs from current engine.")

    except Exception:
        report.notes.append("Failed to parse container structure.")

    return report


WORDLIST = [
    "RIVER", "EAGLE", "STONE", "OCEAN", "MOUNTAIN", "FOREST",
    "SHADOW", "FLAME", "STORM", "SUN", "MOON", "CLOUD",
    "IRON", "SILVER", "GOLD", "NORTH", "SOUTH", "EAST", "WEST",
    "WIND", "FROST", "EMBER", "LIGHT", "DUSK", "DAWN"
]


def generate_fingerprint(container_bytes: bytes) -> str:
    """
    Generate a human-readable fingerprint from full container hash.
    """
    digest = hashlib.sha256(container_bytes).digest()

    # Use first two bytes to index into word list
    word1 = WORDLIST[digest[0] % len(WORDLIST)]
    word2 = WORDLIST[digest[1] % len(WORDLIST)]

    # Use next two bytes as numeric suffix
    number = int.from_bytes(digest[2:4], "big") % 10000

    return f"{word1}-{word2}-{number:04d}"