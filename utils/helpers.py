import re

def evaluate_password_strength(password: str) -> int:
    """
    Returns strength level:
    0 = none
    1 = weak
    2 = medium
    3 = strong
    """

    if not password:
        return 0

    length = len(password)

    # Count character types
    types = 0
    if re.search(r"[a-z]", password):
        types += 1
    if re.search(r"[A-Z]", password):
        types += 1
    if re.search(r"[0-9]", password):
        types += 1
    if re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        types += 1

    # Weak
    if length < 6:
        return 1

    # Medium
    if length >= 6 and types >= 2:
        return 2

    # Strong
    if length >= 8 and types >= 3:
        return 3

    return 1