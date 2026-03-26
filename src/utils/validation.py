"""
src/utils/validation.py
Claim validation utilities shared between main.py CLI and app.py Streamlit UI.
Previously, main.py had validate_claim() inline and app.py tried to import it
from a file that did not exist — crashing at startup (B2-P2 fix).
"""
import re
from typing import Tuple


def validate_claim(claim: str) -> Tuple[bool, str]:
    """Validate a user-submitted claim for safety and minimum quality.

    Returns:
        (True, "")             — claim is acceptable
        (False, reason_str)    — claim is rejected; reason_str explains why
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

    # Basic prompt-injection guard
    injection_patterns = [
        r"ignore\s+previous\s+instructions",
        r"ignore\s+all\s+previous",
        r"disregard\s+all\s+previous",
        r"\bsystem\s*:\s*",
    ]
    for pattern in injection_patterns:
        if re.search(pattern, claim.lower()):
            return False, "Prompt injection detected — please enter a factual claim."

    return True, ""
