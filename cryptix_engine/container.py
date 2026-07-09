import config


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