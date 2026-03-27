"""
src/utils/trust_scorer.py — Final production version.
"""
import re, logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class TrustScorer:
    TIERS = {"AUTHORITATIVE":1.0,"CREDIBLE":0.8,"GENERAL":0.5,"UNDIRECTED":0.3,"UNRELIABLE":0.1}

    PATTERNS = {
        "AUTHORITATIVE": [r"\.gov$",r"\.edu$",r"who\.int$",r"cdc\.gov$",r"nasa\.gov$",
                          r"nih\.gov$",r"nature\.com$",r"science\.org$",r"thelancet\.com$"],
        "CREDIBLE":      [r"reuters\.com$",r"apnews\.com$",r"nytimes\.com$",r"wsj\.com$",
                          r"bbc\.co\.uk$",r"theguardian\.com$",r"economist\.com$",r"bloomberg\.com$"],
        "UNRELIABLE":    [r"dailymail\.co\.uk$",r"infowars\.com$",r"naturalnews\.com$",
                          r"thegatewaypundit\.com$",r"breitbart\.com$"],
        "UNDIRECTED":    [r"twitter\.com$",r"x\.com$",r"facebook\.com$",r"reddit\.com$",
                          r"medium\.com$",r"substack\.com$"],
    }

    @classmethod
    def get_score(cls, url: str) -> float:
        try:
            domain = urlparse(url).netloc.lower().lstrip("www.")
            for t in ("UNRELIABLE","AUTHORITATIVE","CREDIBLE","UNDIRECTED"):
                if any(re.search(p, domain) for p in cls.PATTERNS[t]):
                    return cls.TIERS[t]
            return cls.TIERS["GENERAL"]
        except Exception as e:
            logger.warning("Error scoring trust for URL %s: %s", url, e)
            return cls.TIERS["GENERAL"]

    @classmethod
    def get_tier_label(cls, score: float) -> str:
        if score is None: return "GENERAL"
        score = float(score)
        for label, threshold in sorted(cls.TIERS.items(), key=lambda x: x[1], reverse=True):
            if score >= threshold:
                return label
        return "UNRELIABLE"
