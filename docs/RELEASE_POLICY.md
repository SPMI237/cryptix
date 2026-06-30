Cryptix Release Policy

Versioning Model
Cryptix follows Semantic Versioning:

text

MAJOR.MINOR.PATCH
MAJOR: Architectural changes (e.g., Vault introduction)
MINOR: Feature additions and usability improvements
PATCH: Bug fixes and installer adjustments
Release Process
Every release must:

Pass regression testing:

File encryption
Folder encryption
Batch operations
Verify
Secure delete
Update checker
Installer validation
Be tagged in Git:

text

git tag vX.Y.Z
Include:
Updated CHANGELOG
Updated README
Correct version string in UI
Installer build
SHA256 hash (optional but recommended)
Distribution
Official binaries are distributed via:

GitHub Releases.

Installer executables are not tracked in Git repository.

Stability Principle
New features must not:

Break file format compatibility
Alter cryptographic primitives
Modify threat model without documentation
Reduce backward compatibility

End of document.

