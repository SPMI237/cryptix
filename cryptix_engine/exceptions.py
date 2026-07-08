class AuthenticationError(Exception):
    """Raised when authentication fails (wrong password or tampered file)."""
    pass


class FormatError(Exception):
    """Raised when container format is invalid."""
    pass


class VersionMismatchError(Exception):
    """Raised when file format version is unsupported."""
    pass