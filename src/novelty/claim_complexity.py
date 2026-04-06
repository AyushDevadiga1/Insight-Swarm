"""
NOVELTY FEATURE: Multi-Dimensional Claim Complexity Estimation
===============================================================

Novel Contribution:
------------------
Automatically estimates claim verification difficulty BEFORE debate starts:

1. **Semantic Complexity**: Number of entities, relationships, qualifiers
2. **Temporal Complexity**: Time-dependent claims require historical analysis
3. **Domain Complexity**: Technical claims need domain expertise
4. **Evidence Availability**: Estimates how much evidence exists

Research Impact:
---------------
- First fact-checker with complexity-aware resource allocation
- Novel: Adjusts debate rounds, source requirements based on complexity
- Enables fair comparison (simple vs complex claims need different evaluation)

Application:
-----------
- Simple claims → 2 rounds, 3 sources minimum
- Complex claims → 4 rounds, 7 sources minimum
- Guides human-in-the-loop decisions (when to request expert review)
"""

import re
import logging
from typing import Dict, Any, List, Tuple

logger = logging.getLogger(__name__)


class ClaimComplexityEstimator:
    """
    Estimates verification complexity of claims before debate starts.
    
    Novel: Complexity-aware resource allocation for multi-agent fact-checking.
    """
    
    def __init__(self):
        # Domain-specific vocabulary (indicates technical complexity)
        self.technical_domains = {
            "medical": [
                "efficacy", "clinical", "pathogen", "antibody", "enzyme", "metabolism",
                "placebo", "trial", "dose", "symptoms", "diagnosis", "treatment",
            ],
            "scientific": [
                "hypothesis", "correlation", "causation", "control group", "methodology",
                "statistical", "significance", "experiment", "measurement", "variable",
            ],
            "legal": [
                "statute", "precedent", "jurisdiction", "liability", "plaintiff",
                "defendant", "ruling", "constitutional", "amendment", "law",
            ],
            "economic": [
                "gdp", "inflation", "recession", "monetary", "fiscal", "tariff",
                "market", "stock", "bonds", "interest rate", "deficit",
            ],
        }
        
        # Complexity indicators
        self.complexity_markers = {
            "causal": ["causes", "leads to", "results in", "because of", "due to"],
            "comparative": ["more than", "less than", "better", "worse", "compared to"],
            "quantitative": ["percent", "%", "times", "increase", "decrease", "rate"],
            "temporal": ["will", "would", "by 2030", "in the future", "historically"],
            "conditional": ["if", "unless", "provided that", "assuming", "given"],
        }
    
    def count_entities(self, claim: str) -> int:
        """
        Count named entities (people, places, organizations).
        Novel: More entities → higher complexity.
        """
        # Simple heuristic: Capitalized words (excluding sentence starts)
        words = claim.split()
        entities = 0
        
        for i, word in enumerate(words):
            # Skip first word (sentence start)
            if i == 0:
                continue
            # Count capitalized words (likely entities)
            if word and word[0].isupper() and len(word) > 1:
                entities += 1
        
        return entities
    
    def detect_domain(self, claim: str) -> Tuple[str, int]:
        """
        Detect technical domain and count domain-specific terms.
        Novel: Domain detection for complexity assessment.
        """
        claim_lower = claim.lower()
        domain_scores = {}
        
        for domain, vocabulary in self.technical_domains.items():
            score = sum(1 for term in vocabulary if term in claim_lower)
            if score > 0:
                domain_scores[domain] = score
        
        if not domain_scores:
            return "general", 0
        
        dominant_domain = max(domain_scores, key=domain_scores.get)
        return dominant_domain, domain_scores[dominant_domain]
    
    def detect_complexity_markers(self, claim: str) -> Dict[str, int]:
        """Count different types of complexity indicators."""
        claim_lower = claim.lower()
        marker_counts = {}
        
        for marker_type, keywords in self.complexity_markers.items():
            count = sum(1 for kw in keywords if kw in claim_lower)
            marker_counts[marker_type] = count
        
        return marker_counts
    
    def estimate_semantic_complexity(self, claim: str) -> float:
        """
        Estimate semantic complexity (0.0 - 1.0).
        
        Novel: Combines multiple linguistic features.
        """
        # Word count (longer claims generally more complex)
        word_count = len(claim.split())
        length_score = min(1.0, word_count / 30)  # Normalized to 30 words
        
        # Entity count
        entity_count = self.count_entities(claim)
        entity_score = min(1.0, entity_count / 5)  # Normalized to 5 entities
        
        # Clause count (approximate via commas and conjunctions)
        clause_indicators = claim.count(',') + claim.lower().count(' and ') + claim.lower().count(' or ')
        clause_score = min(1.0, clause_indicators / 3)
        
        # Combine
        semantic = 0.4 * length_score + 0.3 * entity_score + 0.3 * clause_score
        return round(semantic, 3)
    
    def estimate_domain_complexity(self, claim: str) -> float:
        """
        Estimate domain/technical complexity (0.0 - 1.0).
        
        Novel: Domain-specific vocabulary analysis.
        """
        domain, term_count = self.detect_domain(claim)
        
        if domain == "general":
            return 0.2  # Low complexity for general claims
        
        # Technical domains ranked by verification difficulty
        domain_difficulty = {
            "medical": 0.9,
            "scientific": 0.8,
            "legal": 0.7,
            "economic": 0.6,
        }
        
        base_difficulty = domain_difficulty.get(domain, 0.5)
        
        # Adjust by term density
        term_density = min(1.0, term_count / 3)
        
        return round(base_difficulty * (0.6 + 0.4 * term_density), 3)
    
    def estimate_temporal_complexity(self, claim: str) -> float:
        """
        Estimate temporal complexity (0.0 - 1.0).
        
        Novel: Future/historical claims harder to verify.
        """
        claim_lower = claim.lower()
        
        # Future predictions (highest complexity)
        future_markers = ["will", "going to", "by 2030", "by 2040", "in the future"]
        if any(marker in claim_lower for marker in future_markers):
            return 0.9
        
        # Historical claims (medium-high complexity)
        past_markers = ["historically", "in the past", "used to", "previously"]
        if any(marker in claim_lower for marker in past_markers):
            return 0.7
        
        # Time-specific claims (medium complexity)
        year_pattern = r'\b(19|20)\d{2}\b'
        if re.search(year_pattern, claim):
            return 0.6
        
        # Present claims (lowest complexity)
        return 0.3
    
    def estimate_evidence_availability(self, claim: str) -> float:
        """
        Estimate how much evidence likely exists (0.0 - 1.0).
        
        Novel: Predicts verification feasibility before searching.
        Lower score = less evidence = harder to verify.
        """
        claim_lower = claim.lower()
        
        # Well-studied topics (high evidence)
        common_topics = [
            "covid", "vaccine", "climate", "smoking", "cancer", "earth", "moon",
            "election", "president", "government", "diet", "exercise", "water",
        ]
        if any(topic in claim_lower for topic in common_topics):
            return 0.9
        
        # Specific events/people (medium evidence)
        entity_count = self.count_entities(claim)
        if entity_count >= 2:
            return 0.6
        
        # Abstract/theoretical claims (low evidence)
        abstract_markers = ["philosophy", "meaning of life", "true happiness", "best way"]
        if any(marker in claim_lower for marker in abstract_markers):
            return 0.2
        
        # Default: moderate evidence availability
        return 0.5
    
    def estimate_complexity(self, claim: str) -> Dict[str, Any]:
        """
        Main complexity estimation method.
        
        Returns comprehensive complexity profile for research analysis.
        """
        # Calculate individual complexity dimensions
        semantic = self.estimate_semantic_complexity(claim)
        domain = self.estimate_domain_complexity(claim)
        temporal = self.estimate_temporal_complexity(claim)
        evidence_avail = self.estimate_evidence_availability(claim)
        
        # Detect specific markers
        markers = self.detect_complexity_markers(claim)
        detected_domain, domain_term_count = self.detect_domain(claim)
        
        # Overall complexity (weighted average)
        overall = (
            0.3 * semantic +
            0.3 * domain +
            0.2 * temporal +
            0.2 * (1.0 - evidence_avail)  # Low evidence → high complexity
        )
        
        # Classify complexity tier
        if overall >= 0.7:
            tier = "very_high"
            recommended_rounds = 4
            recommended_sources = 7
        elif overall >= 0.5:
            tier = "high"
            recommended_rounds = 3
            recommended_sources = 5
        elif overall >= 0.3:
            tier = "medium"
            recommended_rounds = 3
            recommended_sources = 4
        else:
            tier = "low"
            recommended_rounds = 2
            recommended_sources = 3
        
        logger.info(
            f"Claim complexity: {overall:.2f} ({tier}) - "
            f"Semantic: {semantic:.2f}, Domain: {domain:.2f}, "
            f"Temporal: {temporal:.2f}, Evidence: {evidence_avail:.2f}"
        )
        
        return {
            "overall_complexity": round(overall, 3),
            "complexity_tier": tier,
            "semantic_complexity": semantic,
            "domain_complexity": domain,
            "temporal_complexity": temporal,
            "evidence_availability": evidence_avail,
            "detected_domain": detected_domain,
            "domain_term_count": domain_term_count,
            "complexity_markers": markers,
            "recommended_debate_rounds": recommended_rounds,
            "recommended_min_sources": recommended_sources,
            "requires_expert_review": overall >= 0.7 or domain in ["medical", "legal"],
        }
    
    def adjust_debate_parameters(self, base_rounds: int, base_sources: int,
                                 complexity_profile: Dict) -> Dict[str, int]:
        """
        Novel: Adjust debate parameters based on complexity.
        
        Simple claims waste resources with too many rounds.
        Complex claims need more thorough investigation.
        """
        complexity = complexity_profile["overall_complexity"]
        
        # Adjust rounds
        if complexity >= 0.7:
            rounds = max(base_rounds, 4)
        elif complexity <= 0.3:
            rounds = min(base_rounds, 2)
        else:
            rounds = base_rounds
        
        # Adjust source requirements
        if complexity >= 0.7:
            sources = max(base_sources, complexity_profile["recommended_min_sources"])
        elif complexity <= 0.3:
            sources = max(3, base_sources - 1)  # At least 3 sources
        else:
            sources = base_sources
        
        return {
            "adjusted_rounds": rounds,
            "adjusted_min_sources": sources,
            "reasoning": f"Complexity tier: {complexity_profile['complexity_tier']}",
        }


# Singleton
_estimator = None

def get_complexity_estimator() -> ClaimComplexityEstimator:
    """Get singleton estimator instance."""
    global _estimator
    if _estimator is None:
        _estimator = ClaimComplexityEstimator()
    return _estimator
