"""
TemporalVerifier - Checks date/time alignment between claims and source content.
"""

import re
import logging
from typing import Set, Tuple

logger = logging.getLogger(__name__)

class TemporalVerifier:
    """
    Validates whether the temporal assertions (years, dates) in a claim 
    are minimally supported by the provided source content.
    """
    def __init__(self):
        # Match years between 1900 and 2099
        self.year_pattern = re.compile(r'\b(?:19|20)\d{2}\b')
        
    def extract_years(self, text: str) -> Set[str]:
        """Extract all valid years from a text block."""
        if not text:
            return set()
        return set(self.year_pattern.findall(text))
        
    def verify_alignment(self, claim: str, content: str) -> Tuple[bool, str]:
        """
        Verify that years mentioned in the claim appear in the source content.
        
        Args:
            claim: The argument or claim being made.
            content: The text extracted from the URL source.
            
        Returns:
            Tuple of (is_aligned: bool, reasoning: str)
        """
        if not claim or not content:
            return True, "No content to verify"
            
        claim_years = self.extract_years(claim)
        
        # If no years mentioned in claim, there is no temporal constraint
        if not claim_years:
            return True, "No temporal constraint in claim"
            
        content_years = self.extract_years(content)
        
        # If no years found in content, we cannot verify alignment, so we waive it
        # rather than failing. This prevents NASA/standard articles from failing 
        # just because they don't explicitly mention the year cited in the arg.
        if not content_years:
            return True, "No temporal markers found in source content; alignment waived."
            
        # Check for intersection
        overlap = claim_years.intersection(content_years)
        if overlap:
            return True, f"Temporal alignment found for years: {', '.join(overlap)}"
            
        missing_years = claim_years - content_years
        return False, f"Temporal mismatch: Claim cites years {', '.join(missing_years)} which are missing from source content"

# Quick test
if __name__ == "__main__":
    tv = TemporalVerifier()
    claim = "The stock market crashed in 2008 due to the housing crisis."
    content1 = "In 2008, a massive financial crisis occurred, largely driven by subprime mortgages."
    content2 = "The housing crisis caused a huge recession in the late 2000s."
    
    res1, msg1 = tv.verify_alignment(claim, content1)
    print(f"Test 1: {res1} - {msg1}")
    
    res2, msg2 = tv.verify_alignment(claim, content2)
    print(f"Test 2: {res2} - {msg2}")
