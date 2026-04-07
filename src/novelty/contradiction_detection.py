"""
src/novelty/contradiction_detection.py
Cross-Source Evidence Contradiction Detection.
BUG FIX (D23): added None-guard in detect_directional_contradiction and
               analyze_contradiction_pair so SourceVerification objects
               with content_preview=None don't raise AttributeError.
"""

import re
import logging
from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


class EvidenceContradictionDetector:
    """
    Detects and analyzes contradictions between verified sources.
    Novel: Contradiction-aware fact-checking that produces context-dependent verdicts.
    """

    def __init__(self):
        self.contradiction_log = []
        self.temporal_patterns = {
            "outdated": r"(20\d{2}).*\b(old|outdated|superseded|replaced)\b",
            "recent":   r"\b(recent|latest|new|updated|current)\b.*(20\d{2})",
            "dated":    r"\bas of (january|february|march|april|may|june|july|august|"
                        r"september|october|november|december) (20\d{2})\b",
        }

    def extract_temporal_markers(self, content: str) -> List[int]:
        """Extract years mentioned in content."""
        if not content:
            return []
        years = []
        for match in re.findall(r'\b(19|20)\d{2}\b', content):
            try:
                y = int(match)
                if 1900 <= y <= 2099:
                    years.append(y)
            except ValueError:
                continue
        return sorted(set(years))

    def detect_temporal_contradiction(self, source1: Dict, source2: Dict) -> Optional[Dict]:
        """Detect if two sources contradict due to time difference."""
        content1 = self._safe_content(source1)
        content2 = self._safe_content(source2)

        years1 = self.extract_temporal_markers(content1)
        years2 = self.extract_temporal_markers(content2)

        if not years1 or not years2:
            return None

        time_gap = abs(max(years1) - max(years2))
        if time_gap >= 5:
            return {
                "type":            "temporal",
                "time_gap_years":  time_gap,
                "older_year":      min(max(years1), max(years2)),
                "newer_year":      max(max(years1), max(years2)),
                "severity":        "high" if time_gap >= 10 else "medium",
                "explanation":     f"Sources span {time_gap} years — may reflect evolving science",
            }
        return None

    def _safe_content(self, source) -> str:
        """
        Extract text content from a source dict or SourceVerification object.
        Returns empty string if content is None / unavailable.
        BUG FIX: prevents AttributeError when content_preview is None.
        """
        # Try 'content' first (plain dict), then 'content_preview' (SourceVerification)
        val = None
        if hasattr(source, "get"):
            val = source.get("content") or source.get("content_preview")
        if val is None:
            return ""
        return str(val)

    def detect_directional_contradiction(self, content1: str, content2: str) -> bool:
        """
        Detect if two sources make opposite directional claims.
        BUG FIX: guard against None / empty content before calling .lower().
        """
        if not content1 or not content2:
            return False

        positive_patterns = [
            r"\bbeneficial\b", r"\beffective\b", r"\bimproves?\b", r"\bincreases?\b",
            r"\breduces? risk\b", r"\bprevents?\b", r"\bpositively?\b", r"\bhelps?\b",
        ]
        negative_patterns = [
            r"\bharmful\b", r"\bineffective\b", r"\bworsens?\b", r"\bdecreases?\b",
            r"\bincreases? risk\b", r"\bcauses?\b", r"\bnegatively?\b", r"\bdamages?\b",
        ]

        c1 = content1.lower()
        c2 = content2.lower()

        pos1 = sum(1 for p in positive_patterns if re.search(p, c1))
        neg1 = sum(1 for p in negative_patterns if re.search(p, c1))
        pos2 = sum(1 for p in positive_patterns if re.search(p, c2))
        neg2 = sum(1 for p in negative_patterns if re.search(p, c2))

        source1_positive = pos1 > neg1 and pos1 >= 2
        source2_negative = neg2 > pos2 and neg2 >= 2
        source1_negative = neg1 > pos1 and neg1 >= 2
        source2_positive = pos2 > neg2 and pos2 >= 2

        return (source1_positive and source2_negative) or (source1_negative and source2_positive)

    def detect_jurisdictional_contradiction(self, source1: Dict, source2: Dict) -> Optional[Dict]:
        """Detect if sources contradict due to different jurisdictions/regions."""
        content1 = self._safe_content(source1)
        content2 = self._safe_content(source2)
        url1 = source1.get("url", "") if hasattr(source1, "get") else ""
        url2 = source2.get("url", "") if hasattr(source2, "get") else ""

        jurisdictions = {
            "US":  [r"\bfda\b", r"\bunited states\b", r"\bus\b", r"\.gov"],
            "EU":  [r"\bema\b", r"\beuropean\b", r"\beu\b", r"\.eu"],
            "UK":  [r"\bmhra\b", r"\buk\b", r"\bbritish\b", r"\.uk"],
            "WHO": [r"\bwho\b", r"\bworld health\b"],
        }

        def _regions(content: str, url: str) -> List[str]:
            detected = []
            for region, patterns in jurisdictions.items():
                for pattern in patterns:
                    if (content and re.search(pattern, content.lower())) or (url and pattern in url.lower()):
                        detected.append(region)
            return detected

        d1 = _regions(content1, url1)
        d2 = _regions(content2, url2)

        if d1 and d2 and not set(d1).intersection(set(d2)):
            return {
                "type":          "jurisdictional",
                "jurisdiction1": d1[0],
                "jurisdiction2": d2[0],
                "severity":      "medium",
                "explanation":   f"Different regulatory contexts: {d1[0]} vs {d2[0]}",
            }
        return None

    def analyze_contradiction_pair(self, source1, source2, claim: str) -> Optional[Dict]:
        """
        Comprehensive contradiction analysis between two sources.
        BUG FIX: uses _safe_content() so None content_preview never crashes.
        """
        # Only compare verified sources
        if (source1.get("status") if hasattr(source1, "get") else None) != "VERIFIED":
            return None
        if (source2.get("status") if hasattr(source2, "get") else None) != "VERIFIED":
            return None

        content1 = self._safe_content(source1)
        content2 = self._safe_content(source2)

        has_directional = self.detect_directional_contradiction(content1, content2)
        if not has_directional:
            return None

        temporal      = self.detect_temporal_contradiction(source1, source2)
        jurisdictional = self.detect_jurisdictional_contradiction(source1, source2)

        contradiction_data = {
            "source1_url":                    source1.get("url", "") if hasattr(source1, "get") else "",
            "source2_url":                    source2.get("url", "") if hasattr(source2, "get") else "",
            "source1_trust":                  source1.get("trust_score", 0.5) if hasattr(source1, "get") else 0.5,
            "source2_trust":                  source2.get("trust_score", 0.5) if hasattr(source2, "get") else 0.5,
            "has_directional_contradiction":  True,
            "temporal_factor":               temporal,
            "jurisdictional_factor":         jurisdictional,
            "resolution_strategy":           self._suggest_resolution(temporal, jurisdictional),
        }
        self.contradiction_log.append(contradiction_data)
        return contradiction_data

    def _suggest_resolution(self, temporal: Optional[Dict], jurisdictional: Optional[Dict]) -> str:
        if temporal and temporal.get("time_gap_years", 0) >= 10:
            return "temporal_priority_newer"
        if jurisdictional:
            return "context_dependent"
        if temporal:
            return "evolving_science"
        return "quality_weighted"

    def detect_contradictions(self, verification_results: List, claim: str) -> Dict[str, Any]:
        """
        Main contradiction detection across all verified sources.
        Accepts List[SourceVerification] or List[Dict].
        """
        verified_sources = [
            r for r in verification_results
            if (r.get("status") if hasattr(r, "get") else None) == "VERIFIED"
        ]

        if len(verified_sources) < 2:
            return {
                "contradictions_found":    False,
                "contradiction_count":     0,
                "contradiction_details":   [],
                "verdict_impact":          "none",
            }

        contradictions = []
        for i, source1 in enumerate(verified_sources):
            for source2 in verified_sources[i + 1:]:
                try:
                    contradiction = self.analyze_contradiction_pair(source1, source2, claim)
                    if contradiction:
                        contradictions.append(contradiction)
                except Exception as e:
                    logger.warning("Contradiction pair analysis failed (non-fatal): %s", e)

        if not contradictions:
            return {
                "contradictions_found":  False,
                "contradiction_count":   0,
                "contradiction_details": [],
                "verdict_impact":        "none",
            }

        has_temporal      = any(c.get("temporal_factor")      for c in contradictions)
        has_jurisdictional = any(c.get("jurisdictional_factor") for c in contradictions)

        return {
            "contradictions_found":             True,
            "contradiction_count":              len(contradictions),
            "contradiction_details":            contradictions,
            "has_temporal_contradictions":      has_temporal,
            "has_jurisdictional_contradictions": has_jurisdictional,
            "verdict_impact":                   "high" if len(contradictions) >= 3 else "medium",
            "recommended_verdict_modifier":     self._get_verdict_modifier(contradictions),
        }

    def _get_verdict_modifier(self, contradictions: List[Dict]) -> str:
        if not contradictions:
            return "none"
        temporal_count      = sum(1 for c in contradictions if c.get("temporal_factor"))
        jurisdictional_count = sum(1 for c in contradictions if c.get("jurisdictional_factor"))
        if temporal_count >= 2:
            return "EVOLVING_SCIENCE"
        if jurisdictional_count >= 1:
            return "CONTEXT_DEPENDENT"
        return "PARTIALLY_TRUE"

    def get_contradiction_summary(self) -> Dict[str, Any]:
        if not self.contradiction_log:
            return {"total_contradictions": 0}
        temporal_count      = sum(1 for c in self.contradiction_log if c.get("temporal_factor"))
        jurisdictional_count = sum(1 for c in self.contradiction_log if c.get("jurisdictional_factor"))
        return {
            "total_contradictions":       len(self.contradiction_log),
            "temporal_contradictions":    temporal_count,
            "jurisdictional_contradictions": jurisdictional_count,
        }


_detector = None


def get_contradiction_detector() -> EvidenceContradictionDetector:
    global _detector
    if _detector is None:
        _detector = EvidenceContradictionDetector()
    return _detector
