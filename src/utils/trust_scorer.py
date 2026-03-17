import re
import logging
from typing import Dict, List, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class TrustScorer:
    """
    Ranks source credibility based on domain authority tiers.
    Fulfills Audit Issue #08.
    """
    
    # Tier mapping: 1.0 (Highest) to 0.2 (Lowest)
    TIERS = {
        "AUTHORITATIVE": 1.0,  # Official bodies, academic institutions
        "CREDIBLE": 0.8,       # High-reputation news
        "GENERAL": 0.5,        # Standard blogs/news
        "UNDIRECTED": 0.3,      # Social media / unverified personal blogs
        "UNRELIABLE": 0.1       # Tabloids / known misinformation sites
    }

    # Regex patterns for domains
    PATTERNS = {
        "AUTHORITATIVE": [
            r"\.gov$", r"\.edu$", r"\.org$",  # General gov/edu/org (caution with .org)
            r"who\.int$", r"cdc\.gov$", r"nasa\.gov$", r"nih\.gov$",
            r"nature\.com$", r"science\.org$", r"thelancet\.com$"
        ],
        "CREDIBLE": [
            r"reuters\.com$", r"apnews\.com$", r"nytimes\.com$", 
            r"wsj\.com$", r"bbc\.co\.uk$", r"theguardian\.com$",
            r"economist\.com$", r"bloomberg\.com$"
        ],
        "UNRELIABLE": [
            r"dailymail\.co\.uk$", r"infowars\.com$", r"naturalnews\.com$",
            r"thegatewaypundit\.com$", r"breitbart\.com$"
        ],
        "UNDIRECTED": [
            r"twitter\.com$", r"x\.com$", r"facebook\.com$", r"reddit\.com$",
            r"medium\.com$", r"substack\.com$"
        ]
    }

    @classmethod
    def get_score(cls, url: str) -> float:
        """
        Extract domain from URL and return its trust score.
        """
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            if domain.startswith("www."):
                domain = domain[4:]
            
            # Check UNRELIABLE first
            for pattern in cls.PATTERNS["UNRELIABLE"]:
                if re.search(pattern, domain):
                    return cls.TIERS["UNRELIABLE"]
            
            # Check AUTHORITATIVE
            for pattern in cls.PATTERNS["AUTHORITATIVE"]:
                if re.search(pattern, domain):
                    return cls.TIERS["AUTHORITATIVE"]
            
            # Check CREDIBLE
            for pattern in cls.PATTERNS["CREDIBLE"]:
                if re.search(pattern, domain):
                    return cls.TIERS["CREDIBLE"]
            
            # Check UNDIRECTED
            for pattern in cls.PATTERNS["UNDIRECTED"]:
                if re.search(pattern, domain):
                    return cls.TIERS["UNDIRECTED"]
            
            # Default to General
            return cls.TIERS["GENERAL"]
            
        except Exception as e:
            logger.warning(f"Error scoring trust for URL {url}: {e}")
            return cls.TIERS["GENERAL"]

    @classmethod
    def get_tier_label(cls, score: float) -> str:
        """Return human-readable label for a score."""
        for label, val in cls.TIERS.items():
            if score >= val:
                return label
        return "GENERAL"
