"""
TrustScorer — Ranks source credibility based on domain authority tiers.
P2-3 fix: get_tier_label() now handles None input and uses correct descending comparison.
"""
import re
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class TrustScorer:
    TIERS = {
        "AUTHORITATIVE": 1.0,
        "CREDIBLE":       0.8,
        "GENERAL":        0.5,
        "UNDIRECTED":     0.3,
        "UNRELIABLE":     0.1,
    }

    PATTERNS = {
        "AUTHORITATIVE": [
            r"\.gov$", r"\.edu$",
            r"who\.int$", r"cdc\.gov$", r"nasa\.gov$", r"nih\.gov$",
            r"nature\.com$", r"science\.org$", r"thelancet\.com$",
        ],
        "CREDIBLE": [
            r"reuters\.com$", r"apnews\.com$", r"nytimes\.com$",
            r"wsj\.com$", r"bbc\.co\.uk$", r"theguardian\.com$",
            r"economist\.com$", r"bloomberg\.com$",
        ],
        "UNRELIABLE": [
            r"dailymail\.co\.uk$", r"infowars\.com$", r"naturalnews\.com$",
            r"thegatewaypundit\.com$", r"breitbart\.com$",
        ],
        "UNDIRECTED": [
            r"twitter\.com$", r"x\.com$", r"facebook\.com$", r"reddit\.com$",
            r"medium\.com$", r"substack\.com$",
        ],
    }

    @classmethod
    def get_score(cls, url: str) -> float:
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            if domain.startswith("www."):
                domain = domain[4:]

            for pattern in cls.PATTERNS["UNRELIABLE"]:
                if re.search(pattern, domain):
                    return cls.TIERS["UNRELIABLE"]
            for pattern in cls.PATTERNS["AUTHORITATIVE"]:
                if re.search(pattern, domain):
                    return cls.TIERS["AUTHORITATIVE"]
            for pattern in cls.PATTERNS["CREDIBLE"]:
                if re.search(pattern, domain):
                    return cls.TIERS["CREDIBLE"]
            for pattern in cls.PATTERNS["UNDIRECTED"]:
                if re.search(pattern, domain):
                    return cls.TIERS["UNDIRECTED"]
            return cls.TIERS["GENERAL"]
        except Exception as e:
            logger.warning("Error scoring trust for URL %s: %s", url, e)
            return cls.TIERS["GENERAL"]

    @classmethod
    def get_tier_label(cls, score: float) -> str:
        """
        P2-3 fix: handle None score; use sorted descending comparison so
        each tier matches exactly the right score range.
        e.g. score=0.4 → UNDIRECTED (0.3 ≤ 0.4 < 0.5), not GENERAL.
        """
        if score is None:
            return "GENERAL"
        score = float(score)
        # Sort tiers descending by threshold so highest match wins
        for label, threshold in sorted(cls.TIERS.items(), key=lambda x: x[1], reverse=True):
            if score >= threshold:
                return label
        return "UNRELIABLE"
