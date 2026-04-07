"""
src/novelty/argumentation_analysis.py
FIXED: numpy import moved to top so `np` is always available inside class methods.
Previously np was imported at the bottom of the file, causing NameError inside
calculate_argument_structure_score() and compare_debate_quality().
"""

import re
import logging
from typing import List, Dict, Any
from collections import Counter

logger = logging.getLogger(__name__)

# ── numpy import at module level so all class methods can use np ──────────────
try:
    import numpy as np
except ImportError:
    class np:  # type: ignore[no-redef]
        """Minimal numpy shim for environments without numpy installed."""
        @staticmethod
        def mean(x):
            return sum(x) / len(x) if x else 0.0

        @staticmethod
        def std(x):
            if not x:
                return 0.0
            m = sum(x) / len(x)
            return (sum((i - m) ** 2 for i in x) / len(x)) ** 0.5


class ArgumentationAnalyzer:
    """
    Novel argumentation quality analysis system.
    Analyzes logical structure and rhetorical quality of agent arguments.
    """

    FALLACY_PATTERNS = {
        "ad_hominem": {
            "patterns": [
                r"\b(idiots?|morons?|stupid|dumb|ignorant)\b",
                r"\bcan't trust (him|her|them|those)\b",
                r"\b(biased|corrupt|dishonest) (person|people|source)\b",
            ],
            "description": "Attacks person rather than argument",
            "severity": "high",
        },
        "strawman": {
            "patterns": [
                r"\bso you're saying\b",
                r"\byou claim that\b.*\b(all|every|never|always)\b",
                r"\bif .* then (everyone|everything)\b",
            ],
            "description": "Misrepresents opponent's position",
            "severity": "high",
        },
        "false_dichotomy": {
            "patterns": [
                r"\beither .* or\b",
                r"\bonly two (options|choices|possibilities)\b",
                r"\bmust (choose|pick) (between|from)\b",
            ],
            "description": "Presents false binary choice",
            "severity": "medium",
        },
        "appeal_to_authority": {
            "patterns": [
                r"\bexperts? (say|claim|agree)\b",
                r"\bstudies? show\b(?!.*cite)",
                r"\bscience (says|proves)\b(?!.*source)",
            ],
            "description": "Unsupported appeal to authority",
            "severity": "medium",
        },
        "slippery_slope": {
            "patterns": [
                r"\bif .* then (eventually|ultimately|inevitably)\b",
                r"\bleads? to .* (which|that) leads? to\b",
                r"\bopens? the door to\b",
            ],
            "description": "Chain reaction without evidence",
            "severity": "medium",
        },
        "appeal_to_emotion": {
            "patterns": [
                r"\bimagine if .* (your|our) (children|family|loved ones)\b",
                r"\bthink of the (victims|suffering|tragedy)\b",
                r"\bhow (terrible|awful|horrible) (would|will) be\b",
            ],
            "description": "Emotion over evidence",
            "severity": "low",
        },
        "hasty_generalization": {
            "patterns": [
                r"\b(all|every|always|never) .* (are|is|do|does)\b",
                r"\bone (case|example|instance) (proves|shows)\b",
                r"\bI (know|met) (someone|a person) (who|that)\b",
            ],
            "description": "Generalizes from insufficient evidence",
            "severity": "high",
        },
        "circular_reasoning": {
            "patterns": [
                r"\bbecause .* (is|are) .* because\b",
                r"\bproves .* which proves\b",
                r"\btrue because .* true\b",
            ],
            "description": "Conclusion restates premise",
            "severity": "high",
        },
        "red_herring": {
            "patterns": [
                r"\bbut what about\b",
                r"\bthe real issue is\b",
                r"\binstead of .* let's talk about\b",
            ],
            "description": "Diverts to irrelevant topic",
            "severity": "medium",
        },
        "cherry_picking": {
            "patterns": [
                r"\bone study (found|showed|proved)\b",
                r"\bconvenient(ly)? ignor(es?|ing)\b",
                r"\bonly (citing|mentioning|using)\b",
            ],
            "description": "Selective evidence presentation",
            "severity": "high",
        },
    }

    def __init__(self):
        self.fallacy_stats = Counter()

    def detect_fallacies(self, argument: str) -> List[Dict[str, Any]]:
        detected = []
        argument_lower = argument.lower()
        for fallacy_type, config in self.FALLACY_PATTERNS.items():
            for pattern in config["patterns"]:
                for match in re.finditer(pattern, argument_lower, re.IGNORECASE):
                    detected.append({
                        "type":        fallacy_type,
                        "description": config["description"],
                        "severity":    config["severity"],
                        "match":       match.group(0),
                        "position":    match.start(),
                    })
                    self.fallacy_stats[fallacy_type] += 1
        return detected

    def analyze_citation_quality(self, argument: str, sources: List[str]) -> Dict[str, Any]:
        evidence_markers = [
            "study", "research", "according to", "found that", "shows that",
            "data", "statistics", "survey", "report", "analysis",
        ]
        marker_count = sum(
            len(re.findall(rf"\b{marker}\b", argument.lower()))
            for marker in evidence_markers
        )
        source_to_claim_ratio = len(sources) / max(marker_count, 1) if marker_count > 0 else 0
        return {
            "evidence_markers":       marker_count,
            "sources_provided":       len(sources),
            "source_to_claim_ratio":  round(source_to_claim_ratio, 2),
            "unsupported_claims":     marker_count > 0 and len(sources) == 0,
            "over_citing":            len(sources) > 10 and len(argument) < 500,
            "citation_quality":       "good" if 0.5 <= source_to_claim_ratio <= 2.0 else "poor",
        }

    def analyze_rhetorical_techniques(self, argument: str) -> Dict[str, Any]:
        techniques = {
            "repetition":         len(re.findall(r'\b(\w+)\b(?=.*\b\1\b)', argument.lower())),
            "rhetorical_questions": len(re.findall(r'\?\s*$', argument, re.MULTILINE)),
            "superlatives":       len(re.findall(
                r'\b(most|best|worst|greatest|terrible|amazing|incredible)\b',
                argument.lower()
            )),
            "certainty_claims":   len(re.findall(
                r'\b(obviously|clearly|undoubtedly|certainly|definitely|absolutely)\b',
                argument.lower()
            )),
            "hedging":            len(re.findall(
                r'\b(maybe|perhaps|possibly|might|could|seems)\b',
                argument.lower()
            )),
        }
        rhetoric_score = (
            techniques["repetition"]          * 0.1 +
            techniques["rhetorical_questions"] * 0.3 +
            techniques["superlatives"]         * 0.2 +
            techniques["certainty_claims"]     * 0.2 +
            max(0, techniques["certainty_claims"] - techniques["hedging"]) * 0.2
        )
        return {
            **techniques,
            "rhetoric_score": round(min(rhetoric_score, 10.0), 2),
            "rhetoric_level": "high" if rhetoric_score > 5 else "medium" if rhetoric_score > 2 else "low",
        }

    def calculate_argument_structure_score(self, argument: str, sources: List[str]) -> float:
        """Score the logical structure. BUG FIX: np now available at module level."""
        arg_len = len(argument)
        length_score = 0.3 if arg_len < 50 else 0.7 if arg_len > 1000 else 1.0

        sentences = re.split(r'[.!?]+', argument)
        sentence_lengths = [len(s.split()) for s in sentences if s.strip()]
        # np.std is now always available (real or shim)
        length_variance = float(np.std(sentence_lengths)) if len(sentence_lengths) > 1 else 0.0
        structure_score = min(1.0, length_variance / 10)

        evidence_score = 0.5
        if sources:
            referenced = sum(
                1 for src in sources
                if any(
                    domain in argument.lower()
                    for domain in [src.split('/')[2] if '/' in src else src]
                )
            )
            evidence_score = min(1.0, referenced / len(sources))

        return round(0.3 * length_score + 0.3 * structure_score + 0.4 * evidence_score, 3)

    def analyze_argument(self, argument: str, sources: List[str], agent_type: str) -> Dict[str, Any]:
        fallacies       = self.detect_fallacies(argument)
        citation        = self.analyze_citation_quality(argument, sources)
        rhetoric        = self.analyze_rhetorical_techniques(argument)
        structure_score = self.calculate_argument_structure_score(argument, sources)

        fallacy_penalty  = len(fallacies) * 0.15
        rhetoric_penalty = rhetoric["rhetoric_score"] * 0.05
        citation_bonus   = 0.2 if citation["citation_quality"] == "good" else 0.0

        quality_score = max(0.0, min(1.0,
            structure_score + citation_bonus - fallacy_penalty - rhetoric_penalty
        ))

        return {
            "agent":             agent_type,
            "quality_score":     round(quality_score, 3),
            "fallacies_detected": len(fallacies),
            "fallacy_details":   fallacies[:3],
            "citation_analysis": citation,
            "rhetoric_analysis": rhetoric,
            "structure_score":   structure_score,
            "word_count":        len(argument.split()),
            "argument_class":    self._classify_argument_quality(quality_score),
        }

    def _classify_argument_quality(self, score: float) -> str:
        if score >= 0.8: return "excellent"
        if score >= 0.6: return "good"
        if score >= 0.4: return "fair"
        return "poor"

    def compare_debate_quality(
        self,
        pro_analyses: List[Dict],
        con_analyses: List[Dict],
    ) -> Dict[str, Any]:
        """BUG FIX: np.mean now available at module level."""
        pro_avg = float(np.mean([a["quality_score"] for a in pro_analyses])) if pro_analyses else 0.0
        con_avg = float(np.mean([a["quality_score"] for a in con_analyses])) if con_analyses else 0.0
        pro_fallacies = sum(a["fallacies_detected"] for a in pro_analyses)
        con_fallacies = sum(a["fallacies_detected"] for a in con_analyses)
        return {
            "pro_average_quality":  round(pro_avg, 3),
            "con_average_quality":  round(con_avg, 3),
            "quality_gap":          round(abs(pro_avg - con_avg), 3),
            "pro_total_fallacies":  pro_fallacies,
            "con_total_fallacies":  con_fallacies,
            "higher_quality_side":  "PRO" if pro_avg > con_avg else "CON",
            "debate_quality":       "high" if min(pro_avg, con_avg) > 0.6 else "low",
        }


_analyzer = None


def get_argumentation_analyzer() -> ArgumentationAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = ArgumentationAnalyzer()
    return _analyzer
