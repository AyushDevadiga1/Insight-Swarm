"""
src/utils/validation.py — Final production version.
Shared claim validation for both CLI (main.py) and UI (app.py).
"""
import re
from typing import Tuple


def validate_claim(claim: str) -> Tuple[bool, str]:
    """
    Returns (True, "") if claim is acceptable.
    Returns (False, reason) if rejected.
    """
    if not claim or not isinstance(claim, str):
        return False, "Claim cannot be empty."
    claim = claim.strip()
    if not claim:
        return False, "Claim cannot be empty."
    if len(claim) < 10:
        return False, "Claim too short (minimum 10 characters)."
    if len(claim) > 500:
        return False, "Claim too long (max 500 characters)."
    if len(claim.split()) < 3:
        return False, "Claim too short (minimum 3 words)."
    for pattern in [
        r"ignore\s+previous\s+instructions",
        r"ignore\s+all\s+previous",
        r"disregard\s+all\s+previous",
        r"\bsystem\s*:\s*",
    ]:
        if re.search(pattern, claim.lower()):
            return False, "Prompt injection detected — please enter a factual claim."
    return True, ""
