"""
src/utils/temporal_verifier.py — Final production version.
"""
import re, logging
from typing import Set, Tuple

logger = logging.getLogger(__name__)


class TemporalVerifier:
    def __init__(self):
        self.year_pattern = re.compile(r"\b(?:19|20)\d{2}\b")

    def extract_years(self, text: str) -> Set[str]:
        if not text: return set()
        return set(self.year_pattern.findall(text))

    def verify_alignment(self, claim: str, content: str) -> Tuple[bool, str]:
        if not claim or not content:
            return True, "No content to verify"
        claim_years = self.extract_years(claim)
        if not claim_years:
            return True, "No temporal constraint in claim"
        content_years = self.extract_years(content)
        if not content_years:
            return True, "No temporal markers in source — alignment waived."
        overlap = claim_years & content_years
        if overlap:
            return True, f"Temporal alignment found for years: {', '.join(sorted(overlap))}"
        missing = claim_years - content_years
        return False, f"Temporal mismatch: claim cites {', '.join(sorted(missing))} not found in source"
