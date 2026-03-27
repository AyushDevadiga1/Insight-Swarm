"""
src/utils/url_helper.py — Final production version.
"""
import re, logging
from typing import Optional
from urllib.parse import urlparse

logger    = logging.getLogger(__name__)
URL_RE    = re.compile(r"(https?://[^\s\)\]\}<>\"']+)")
BARE_DOMAIN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\-\.]+\.[A-Za-z]{2,}([/?#].*)?$")


class URLNormalizer:
    @staticmethod
    def sanitize_url(raw_input: str) -> Optional[str]:
        if not isinstance(raw_input, str):
            raw_input = str(raw_input)
        original = raw_input.strip()
        if not original:
            return None
        # Try embedded URL
        match = URL_RE.search(original)
        if match:
            return match.group(1).rstrip(".,;:!?)]}'\"")
        # Already valid http/https
        parsed = urlparse(original)
        if parsed.scheme in ("http","https") and parsed.netloc:
            return original
        # Bare domain heuristic
        if " " not in original and BARE_DOMAIN_RE.match(original):
            return "https://" + original
        return None

    @classmethod
    def sanitize_list(cls, list_of_lists: list) -> list:
        sanitized = []
        for round_sources in list_of_lists:
            new_round = [cls.sanitize_url(s) for s in round_sources]
            sanitized.append([u for u in new_round if u])
        skipped = sum(len(r) for r in list_of_lists) - sum(len(r) for r in sanitized)
        if skipped > 0:
            logger.info("URLNormalizer skipped %d non-URL sources", skipped)
        return sanitized
