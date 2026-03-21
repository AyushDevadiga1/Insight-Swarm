"""
validation.py - Utilities for validating user inputs.
"""
from typing import Tuple
import re

def validate_claim(claim: str) -> Tuple[bool, str]:
    """Validates a user-submitted claim for safety and quality."""
    if not claim or not claim.strip():
        return False, "Claim cannot be empty."
    
    if len(claim) > 300:
        return False, "Claim too long (max 300 characters)."
    
    if len(claim.split()) < 3:
        return False, "Claim too short (minimum 3 words)."
    
    # Prompt injection patterns with boundaries to avoid false positives in scientific claims (#28)
    injection_patterns = [
        r"ignore\s+previous\s+instructions",
        r"ignore\s+all\s+previous",
        r"disregard\s+all\s+previous",
        r"\bsystem\s*:\s*",  # Matches 'system:' but not 'ecosystem:'
    ]
    
    for pattern in injection_patterns:
        if re.search(pattern, claim.lower()):
            return False, "Prompt injection detected."
    
    return True, ""
