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