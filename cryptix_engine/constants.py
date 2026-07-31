ALGO_AES = 1
ALGO_CHACHA = 2

def algorithm_name(algo_id: int) -> str:
    if algo_id == ALGO_AES:
        return "AES-256-GCM"
    elif algo_id == ALGO_CHACHA:
        return "ChaCha20-Poly1305"
    else:
        return f"Unknown ({algo_id})"