import math
import config
from dataclasses import dataclass
from typing import List
from cryptix_engine.constants import ALGO_AES, ALGO_CHACHA


# -----------------------------
# FACTS LAYER (objective data)
# -----------------------------

@dataclass
class SecurityFacts:
    schema_version: int = 1

    password_entropy_bits: float = 0.0
    keyfile_present: bool = False
    algorithm: int | None = None

    argon2_memory_mb: int = 0
    argon2_time_cost: int = 0
    argon2_parallelism: int = 0


def estimate_entropy(password: str) -> float:
    if not password:
        return 0.0

    charset = 0
    if any(c.islower() for c in password):
        charset += 26
    if any(c.isupper() for c in password):
        charset += 26
    if any(c.isdigit() for c in password):
        charset += 10
    if any(not c.isalnum() for c in password):
        charset += 32

    if charset == 0:
        return 0.0

    return len(password) * math.log2(charset)


def collect_security_facts(password: str, keyfile_present: bool, algorithm: int) -> SecurityFacts:
    entropy = estimate_entropy(password)

    return SecurityFacts(
        password_entropy_bits=round(entropy, 2),
        keyfile_present=keyfile_present,
        algorithm=algorithm,
        argon2_memory_mb=config.ARGON2_MEMORY_COST // 1024,
        argon2_time_cost=config.ARGON2_TIME_COST,
        argon2_parallelism=config.ARGON2_PARALLELISM
    )


# -----------------------------
# ADVISOR LAYER (interpretation)
# -----------------------------

def generate_security_advice(facts: SecurityFacts) -> dict:
    recommendations: List[str] = []
    risk_profile = ""

    if facts.password_entropy_bits < 40:
        risk_profile = "High risk against offline attack."
        recommendations.append("Use a longer password.")
    elif facts.password_entropy_bits < 80:
        risk_profile = "Moderate protection."
        recommendations.append("Consider increasing password length.")
    else:
        risk_profile = "Strong protection against offline attacks."

    if not facts.keyfile_present:
        recommendations.append("Consider adding a keyfile for additional protection.")
    else:
        recommendations.append("Store keyfile separately from the encrypted container.")

    return {
        "risk_profile": risk_profile,
        "recommendations": recommendations
    }