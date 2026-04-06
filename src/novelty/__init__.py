"""
InsightSwarm Novelty Features Package
=====================================

This package contains research-grade novel features that differentiate
InsightSwarm from existing fact-checking systems.

Novel Contributions:
-------------------
1. **Adaptive Confidence Calibration**: Addresses underconfidence bias
2. **Argumentation Quality Analysis**: Detects logical fallacies
3. **Evidence Contradiction Detection**: Handles conflicting sources
4. **Claim Complexity Estimation**: Resource allocation based on difficulty
5. **Explainability Engine**: XAI for transparent fact-checking

Research Impact:
---------------
- First multi-agent fact-checker with integrated XAI
- Novel trust-weighted consensus with calibration
- Contradiction-aware verdict generation
- Complexity-based debate parameter adjustment

Usage:
------
These modules are integrated into the main debate orchestrator
to enhance verdict quality and transparency.
"""

from src.novelty.confidence_calibration import (
    AdaptiveConfidenceCalibrator,
    get_calibrator
)

from src.novelty.argumentation_analysis import (
    ArgumentationAnalyzer,
    get_argumentation_analyzer
)

from src.novelty.contradiction_detection import (
    EvidenceContradictionDetector,
    get_contradiction_detector
)

from src.novelty.claim_complexity import (
    ClaimComplexityEstimator,
    get_complexity_estimator
)

from src.novelty.explainability import (
    ExplainabilityEngine,
    get_explainability_engine
)

__all__ = [
    # Calibration
    "AdaptiveConfidenceCalibrator",
    "get_calibrator",
    
    # Argumentation
    "ArgumentationAnalyzer",
    "get_argumentation_analyzer",
    
    # Contradictions
    "EvidenceContradictionDetector",
    "get_contradiction_detector",
    
    # Complexity
    "ClaimComplexityEstimator",
    "get_complexity_estimator",
    
    # Explainability
    "ExplainabilityEngine",
    "get_explainability_engine",
]

__version__ = "1.0.0"
__author__ = "InsightSwarm Research Team"
