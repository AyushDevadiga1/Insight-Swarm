"""
URLHelper - Utilities for sanitizing and normalizing URLs cited by agents.
"""
import re
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Constants for URL detection
URL_RE = re.compile(r"(https?://[^\s\)\]\}<>\"']+)")
BARE_DOMAIN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\-\.]+\.[A-Za-z]{2,}([/?#].*)?$")

class URLNormalizer:
    """Consolidated utility for URL sanitization."""
    
    @staticmethod
    def sanitize_url(raw_input: str) -> str | None:
        """
        Extracts and normalizes a single URL from a string.
        Returns None if no valid URL can be determined.
        """
        if not isinstance(raw_input, str):
            raw_input = str(raw_input)
            
        original = raw_input.strip()
        if not original:
            return None

        # 1. Try to extract an embedded URL (e.g. "Source - https://example.com")
        match = URL_RE.search(original)
        if match:
            return match.group(1)

        # 2. Check if it's already a valid http/https URL
        parsed = urlparse(original)
        if parsed.scheme in ("http", "https") and parsed.netloc:
            return original

        # 3. Heuristic: bare domains like 'www.example.com' -> add https://
        if " " not in original and BARE_DOMAIN_RE.match(original):
            return "https://" + original

        return None

    @classmethod
    def sanitize_list(cls, list_of_lists: list[list[str]]) -> list[list[str]]:
        """Sanitizes a nested list of sources (per round)."""
        sanitized = []
        skipped = 0
        for round_sources in list_of_lists:
            new_round = []
            for s in round_sources:
                result = cls.sanitize_url(s)
                if result:
                    new_round.append(result)
                else:
                    skipped += 1
            sanitized.append(new_round)
            
        if skipped:
            logger.info("URLNormalizer skipped %d non-URL sources", skipped)
        return sanitized
