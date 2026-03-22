"""
validation.py - Utilities for validating user inputs.
"""
from typing import Tuple
import re

def validate_claim(claim: str) -> Tuple[bool, str]:
    """Validates a user-submitted claim for safety and quality."""
    if not claim or not claim.strip():
        return False, "Claim cannot be empty."

    stripped = claim.strip()

    # Align with the UI's displayed minimum of 10 characters
    if len(stripped) < 10:
        return False, "Claim too short (minimum 10 characters)."

    # Align with the UI's allowed maximum
    if len(stripped) > 500:
        return False, "Claim too long (max 500 characters)."

    # Must contain at least one word longer than 2 characters
    words = stripped.split()
    if not any(len(w) > 2 for w in words):
        return False, "Claim must contain at least one meaningful word."

    # Unicode safety: reject RTL override, zero-width, and BOM characters
    UNSAFE_RANGES = [
        (0x200B, 0x200F),   # Zero-width spaces and marks
        (0x202A, 0x202E),   # RTL/LTR override characters
        (0xFFF0, 0xFFFF),   # Specials block including BOM
    ]
    for char in stripped:
        cp = ord(char)
        for lo, hi in UNSAFE_RANGES:
            if lo <= cp <= hi:
                return False, "Claim contains unsupported control characters."

    # Prompt injection patterns
    injection_patterns = [
        r"ignore\s+previous\s+instructions",
        r"ignore\s+all\s+previous",
        r"disregard\s+all\s+previous",
        r"\bsystem\s*:\s*",
    ]
    for pattern in injection_patterns:
        if re.search(pattern, stripped.lower()):
            return False, "Prompt injection detected."

    return True, ""
