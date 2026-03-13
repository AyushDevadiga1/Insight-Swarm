"""
Input validation and sanitization.
"""

import re
from typing import Tuple

class InputValidator:
    """Validates and sanitizes user input claims"""
    INJECTION_PATTERNS = [
        r"ignore\s+(previous|all|prior)\s+instructions?",
        r"disregard\s+(previous|all|prior)",
        r"system\s*:",
        r"<\|im_start\|>",
        r"<\|im_end\|>",
        r"<\|system\|>",
        r"```\s*system",
        r"act\s+as\s+(a\s+)?different",
        r"you\s+are\s+now",
        r"forget\s+(everything|all|your)"
    ]
    def validate_claim(self, claim: str) -> Tuple[bool, str, str]:
        if not claim or not claim.strip():
            return False, "Claim cannot be empty", ""
        sanitized = claim.strip()
        if len(sanitized) < 10:
            return False, "Claim too short (minimum 10 characters)", ""
        if len(sanitized) > 500:
            return False, "Claim too long (maximum 500 characters)", ""
        words = sanitized.split()
        if len(words) < 3:
            return False, "Claim too short (minimum 3 words)", ""
        claim_lower = sanitized.lower()
        for pattern in self.INJECTION_PATTERNS:
            if re.search(pattern, claim_lower):
                return False, "Invalid claim format detected", ""
        special_char_ratio = sum(1 for c in sanitized if not c.isalnum() and not c.isspace()) / len(sanitized)
        if special_char_ratio > 0.3:
            return False, "Too many special characters", ""
        return True, "", sanitized
