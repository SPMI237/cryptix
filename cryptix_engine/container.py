import config


def build_header(algorithm: int, salt: bytes, iv: bytes) -> bytes:
    return (
        config.MAGIC_HEADER
        + config.VERSION.to_bytes(1, "big")
        + algorithm.to_bytes(1, "big")
        + salt
        + iv
    )