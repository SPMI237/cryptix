import re
import math

def evaluate_password_strength(password: str) -> int:
    """
    Returns strength level:
    0 = none
    1 = weak
    2 = medium
    3 = strong
    4 = very strong
    """

    if not password:
        return 0

    score = 0
    length = len(password)

    # Length contribution
    if length >= 8:
        score += 1
    if length >= 12:
        score += 1
    if length >= 16:
        score += 1

    # Character variety
    if re.search(r"[a-z]", password):
        score += 1
    if re.search(r"[A-Z]", password):
        score += 1
    if re.search(r"[0-9]", password):
        score += 1
    if re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        score += 1

    # Weak if too short
    if length < 6:
        return 1

    # Map score to strength levels
    if score <= 2:
        return 1
    elif score <= 4:
        return 2
    elif score <= 6:
        return 3
    else:
        return 4