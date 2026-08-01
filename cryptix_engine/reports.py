from dataclasses import dataclass
from typing import List, Optional


@dataclass
class IntegrityReport:
    schema_version: int = 1

    container_valid: bool = False
    version_supported: bool = False
    algorithm_supported: bool = False
    metadata_authenticated: bool = False
    ciphertext_authenticated: bool = False

    failure_stage: Optional[str] = None
    notes: List[str] = None

    def is_valid(self) -> bool:
        return (
            self.container_valid
            and self.version_supported
            and self.algorithm_supported
            and self.metadata_authenticated
            and self.ciphertext_authenticated
        )

@dataclass
class ContainerStructureReport:
    schema_version: int = 1

    container_detected: bool = False
    format_version: int | None = None
    algorithm: int | None = None
    header_valid: bool = False
    compatible: bool = False
    notes: List[str] = None

    def is_valid_structure(self) -> bool:
        return self.container_detected and self.header_valid

@dataclass
class SecurityAssessment:
    schema_version: int = 1

    password_entropy_bits: float = 0.0
    password_strength_level: str = ""
    keyfile_present: bool = False
    algorithm: int | None = None
    kdf_memory_mb: int = 0

    risk_profile: str = ""
    recommendations: List[str] = None    