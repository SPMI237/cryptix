class CryptixError(Exception):
    """Base class for all Cryptix engine errors."""
    def __init__(self, *args, **kwargs):
        self.report = kwargs.pop("report", None)
        super().__init__(*args, **kwargs)


class AuthenticationError(CryptixError):
    """Raised when authentication fails (wrong password or tampered file)."""
    pass


class FormatError(CryptixError):
    """Raised when container format is invalid."""
    pass


class VersionMismatchError(CryptixError):
    """Raised when file format version is unsupported."""
    pass