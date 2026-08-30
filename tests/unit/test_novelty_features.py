"""
Unit tests for all InsightSwarm novelty modules:
- ArgumentationAnalyzer
- EvidenceContradictionDetector
- ClaimComplexityEstimator
- ExplainabilityEngine
"""
import pytest

from src.novelty.argumentation_analysis import (
    ArgumentationAnalyzer,
    get_argumentation_analyzer,
)
from src.novelty.claim_complexity import (
    ClaimComplexityEstimator,
    get_complexity_estimator,
)
from src.novelty.contradiction_detection import (
    EvidenceContradictionDetector,
    get_contradiction_detector,
)
from src.novelty.explainability import (
    ExplainabilityEngine,
    get_explainability_engine,
)


class TestArgumentationAnalyzer:
    @pytest.fixture
    def analyzer(self):
        return get_argumentation_analyzer()

    def test_singleton(self, analyzer):
        assert analyzer is get_argumentation_analyzer()
        assert isinstance(analyzer, ArgumentationAnalyzer)

    def test_detect_ad_hominem_and_strawman(self, analyzer):
        text = "Only idiots would believe this corrupt source, so you're saying that everyone agrees."
        fallacies = analyzer.detect_fallacies(text)
        types = [f["type"] for f in fallacies]
        assert "ad_hominem" in types
        assert "strawman" in types

    def test_analyze_citation_quality_good(self, analyzer):
        arg = "According to a major study, data shows that walking reduces stress."
        sources = ["https://example.com/study1", "https://example.com/study2"]
        res = analyzer.analyze_citation_quality(arg, sources)
        assert res["sources_provided"] == 2
        assert res["evidence_markers"] > 0

    def test_analyze_rhetorical_techniques(self, analyzer):
        arg = "Obviously this is the best, most amazing discovery ever! Clearly it is true. Perhaps maybe not?"
        res = analyzer.analyze_rhetorical_techniques(arg)
        assert res["superlatives"] > 0
        assert res["certainty_claims"] > 0
        assert res["hedging"] > 0
        assert "rhetoric_score" in res

    def test_analyze_argument_full(self, analyzer):
        arg = "Research indicates that regular physical exercise improves cardiovascular health."
        sources = ["https://pubmed.ncbi.nlm.nih.gov/12345"]
        res = analyzer.analyze_argument(arg, sources, agent_type="PRO")
        assert res["agent"] == "PRO"
        assert 0.0 <= res["quality_score"] <= 1.0
        assert res["argument_class"] in ("excellent", "good", "fair", "poor")

    def test_compare_debate_quality(self, analyzer):
        pro_analysis = [analyzer.analyze_argument("Pro argument with study", ["https://nih.gov"], "PRO")]
        con_analysis = [analyzer.analyze_argument("Con rebuttal with bad logic", [], "CON")]
        comp = analyzer.compare_debate_quality(pro_analysis, con_analysis)
        assert "pro_average_quality" in comp
        assert "con_average_quality" in comp
        assert comp["higher_quality_side"] in ("PRO", "CON")


class TestEvidenceContradictionDetector:
    @pytest.fixture
    def detector(self):
        return get_contradiction_detector()

    def test_singleton(self, detector):
        assert detector is get_contradiction_detector()
        assert isinstance(detector, EvidenceContradictionDetector)

    def test_extract_temporal_markers(self, detector):
        text = "Reports published in 2012 and 2021 showed contrasting trends."
        years = detector.extract_temporal_markers(text)
        assert 2012 in years
        assert 2021 in years

    def test_detect_temporal_contradiction(self, detector):
        s1 = {"content": "Data from 2005 shows negative impact."}
        s2 = {"content": "A new 2022 study shows positive outcome."}
        res = detector.detect_temporal_contradiction(s1, s2)
        assert res is not None
        assert res["type"] == "temporal"
        assert res["time_gap_years"] == 17
        assert res["severity"] == "high"

    def test_detect_no_temporal_contradiction_close_years(self, detector):
        s1 = {"content": "Published in 2020."}
        s2 = {"content": "Published in 2021."}
        res = detector.detect_temporal_contradiction(s1, s2)
        assert res is None


class TestClaimComplexityEstimator:
    @pytest.fixture
    def estimator(self):
        return get_complexity_estimator()

    def test_singleton(self, estimator):
        assert estimator is get_complexity_estimator()
        assert isinstance(estimator, ClaimComplexityEstimator)

    def test_simple_claim_complexity(self, estimator):
        claim = "The sky is blue."
        res = estimator.estimate_complexity(claim)
        assert "overall_complexity" in res
        assert res["complexity_level"] in ("low", "medium", "high", "very_high")
        assert res["overall_complexity"] < 0.6

    def test_complex_medical_claim_complexity(self, estimator):
        claim = "Clinical trial placebo methodology indicates pathogen efficacy in patient symptoms."
        res = estimator.estimate_complexity(claim)
        assert "domain_complexity" in res
        assert res["domain_complexity"] > 0.0

    def test_recommend_debate_parameters(self, estimator):
        params_low = estimator.recommend_debate_parameters(0.2)
        assert params_low["recommended_rounds"] <= 3
        assert params_low["min_sources_required"] <= 4

        params_high = estimator.recommend_debate_parameters(0.85)
        assert params_high["recommended_rounds"] >= 3
        assert params_high["min_sources_required"] >= 5


class TestExplainabilityEngine:
    @pytest.fixture
    def engine(self):
        return get_explainability_engine()

    def test_singleton(self, engine):
        assert engine is get_explainability_engine()
        assert isinstance(engine, ExplainabilityEngine)

    def test_calculate_feature_importance(self, engine):
        state = {
            "pro_verification_rate": 0.9,
            "con_verification_rate": 0.3,
            "verification_results": [
                {"agent_source": "PRO", "status": "VERIFIED", "trust_score": 0.9},
                {"agent_source": "CON", "status": "VERIFIED", "trust_score": 0.4},
            ],
            "metrics": {
                "confidence_breakdown": {
                    "argument_quality_score": 0.8,
                    "consensus_score": 0.9,
                }
            }
        }
        importance = engine.calculate_feature_importance(state, final_confidence=0.85)
        assert "source_trust" in importance
        assert "verification_rate" in importance
        assert "argument_quality" in importance
        assert "consensus_agreement" in importance
        assert pytest.approx(sum(importance.values()), abs=0.05) == 1.0

    def test_generate_counterfactual(self, engine):
        state = {"confidence": 0.6}
        cf = engine.generate_counterfactual(state, "source_trust")
        assert "confidence would increase" in cf
        assert "60.0%" in cf
