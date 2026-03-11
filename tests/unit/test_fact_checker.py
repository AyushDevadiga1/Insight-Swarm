"""
Unit tests for FactChecker agent
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.agents.fact_checker import FactChecker, SourceVerification
from src.agents.base import DebateState


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client"""
    return Mock()


@pytest.fixture
def fact_checker(mock_llm_client):
    """Create a FactChecker instance with mocked client"""
    return FactChecker(mock_llm_client)


@pytest.fixture
def sample_debate_state():
    """Create a sample debate state with sources"""
    return DebateState(
        claim="Coffee consumption increases productivity by 15%",
        round=3,
        pro_arguments=[
            "Multiple studies show caffeine improves alertness and focus. See https://example-study.com/caffeine-effects",
            "Workplace productivity metrics increase with coffee breaks. Evidence at https://example-data.com/productivity"
        ],
        con_arguments=[
            "However, caffeine dependency can reduce effectiveness over time. Reference: https://bad-science.fake/caffeine-myth",
            "Some studies show no significant effect. See https://example.com/neutral-study"
        ],
        pro_sources=[
            ["https://example-study.com/caffeine-effects"],
            ["https://example-data.com/productivity"]
        ],
        con_sources=[
            ["https://bad-science.fake/caffeine-myth"],
            ["https://example.com/neutral-study"]
        ],
        verdict=None,
        confidence=None
    )


class TestSourceExtraction:
    """Test source extraction from debate state"""
    
    def test_extract_sources_with_claims(self, fact_checker, sample_debate_state):
        """Test that all sources are correctly extracted with their claims"""
        sources = fact_checker._extract_sources_with_claims(sample_debate_state)
        
        assert len(sources) == 4
        
        # Check PRO sources
        assert sources[0][0] == "https://example-study.com/caffeine-effects"
        assert sources[0][2] == "PRO"
        assert sources[1][0] == "https://example-data.com/productivity"
        assert sources[1][2] == "PRO"
        
        # Check CON sources
        assert sources[2][0] == "https://bad-science.fake/caffeine-myth"
        assert sources[2][2] == "CON"
        assert sources[3][0] == "https://example.com/neutral-study"
        assert sources[3][2] == "CON"
    
    def test_extract_sources_empty_debate_state(self, fact_checker):
        """Test extraction with empty debate state"""
        empty_state = DebateState(
            claim="Test claim",
            round=1,
            pro_arguments=[],
            con_arguments=[],
            pro_sources=[],
            con_sources=[],
            verdict=None,
            confidence=None
        )
        
        sources = fact_checker._extract_sources_with_claims(empty_state)
        assert sources == []
    
    def test_extract_sources_ignores_empty_urls(self, fact_checker):
        """Test that empty URLs are ignored"""
        state = DebateState(
            claim="Test claim",
            round=1,
            pro_arguments=["Test argument"],
            con_arguments=[],
            pro_sources=[["https://valid.com", "", "   "]],
            con_sources=[],
            verdict=None,
            confidence=None
        )
        
        sources = fact_checker._extract_sources_with_claims(state)
        assert len(sources) == 1
        assert sources[0][0] == "https://valid.com"


class TestFuzzyMatching:
    """Test fuzzy string matching logic"""
    
    def test_fuzzy_match_identical_text(self, fact_checker):
        """Test perfect match returns high score"""
        claim = "The study shows a 15% increase in productivity"
        source = "The study shows a 15% increase in productivity"
        
        score = fact_checker._fuzzy_match(claim, source)
        assert score >= 90
    
    def test_fuzzy_match_partial_match(self, fact_checker):
        """Test partial match (substring)"""
        claim = "15% increase in productivity"
        source = "Recent research demonstrates a 15% increase in productivity among test subjects"
        
        score = fact_checker._fuzzy_match(claim, source)
        assert score >= 60
    
    def test_fuzzy_match_no_match(self, fact_checker):
        """Test no match returns low score"""
        claim = "Coffee reduces productivity"
        source = "The study shows increased alertness from caffeine consumption"
        
        score = fact_checker._fuzzy_match(claim, source)
        assert score < 50
    
    def test_fuzzy_match_empty_inputs(self, fact_checker):
        """Test that empty inputs return 0"""
        assert fact_checker._fuzzy_match("", "text") == 0.0
        assert fact_checker._fuzzy_match("text", "") == 0.0
        assert fact_checker._fuzzy_match("", "") == 0.0
    
    def test_fuzzy_match_case_insensitive(self, fact_checker):
        """Test that matching is case-insensitive"""
        claim = "COFFEE INCREASES PRODUCTIVITY"
        source = "coffee increases productivity in a recent study published online"
        
        score = fact_checker._fuzzy_match(claim, source)
        assert score >= 60


class TestSourceVerification:
    """Test source verification logic"""
    
    @patch('requests.get')
    def test_verify_source_successful(self, mock_get, fact_checker):
        """Test successful source verification"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "Multiple studies show caffeine improves alertness and focus"
        mock_get.return_value = mock_response
        
        result = fact_checker._verify_source(
            "https://example.com/study",
            "caffeine improves alertness",
            "PRO"
        )
        
        assert result['url'] == "https://example.com/study"
        assert result['agent_source'] == "PRO"
        assert result['status'] in ["VERIFIED", "CONTENT_MISMATCH"]
        assert 0.0 <= result['confidence'] <= 1.0
        assert result['content_preview'] is not None
    
    @patch('requests.get')
    def test_verify_source_404(self, mock_get, fact_checker):
        """Test 404 response is marked as NOT_FOUND"""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        result = fact_checker._verify_source(
            "https://not-found.com",
            "some claim",
            "CON"
        )
        
        assert result['status'] == "NOT_FOUND"
        assert result['confidence'] == 0.0
        assert result['error'] == "404 Not Found"
    
    @patch('requests.get')
    def test_verify_source_timeout(self, mock_get, fact_checker):
        """Test timeout is handled gracefully"""
        import requests
        mock_get.side_effect = requests.Timeout()
        
        result = fact_checker._verify_source(
            "https://slow.com",
            "some claim",
            "PRO"
        )
        
        assert result['status'] == "TIMEOUT"
        assert result['confidence'] == 0.0
        assert "Timeout" in result['error']
    
    @patch('requests.get')
    def test_verify_source_connection_error(self, mock_get, fact_checker):
        """Test connection error is handled"""
        import requests
        mock_get.side_effect = requests.ConnectionError("Failed to connect")
        
        result = fact_checker._verify_source(
            "https://unreachable.com",
            "some claim",
            "CON"
        )
        
        assert result['status'] == "NOT_FOUND"
        assert result['confidence'] == 0.0
        assert "Connection" in result['error']


class TestFactCheckerGenerate:
    """Test the main generate() method"""
    
    @patch('src.agents.fact_checker.FactChecker._verify_source')
    def test_generate_returns_structured_response(self, mock_verify, fact_checker, sample_debate_state):
        """Test that generate() returns properly structured response"""
        # Mock verification results
        mock_verify.side_effect = [
            SourceVerification(
                url="https://example-study.com/caffeine-effects",
                status="VERIFIED",
                confidence=0.85,
                content_preview="Study content...",
                error=None,
                agent_source="PRO",
                matched_claim="caffeine improves"
            ),
            SourceVerification(
                url="https://example-data.com/productivity",
                status="VERIFIED",
                confidence=0.80,
                content_preview="Data content...",
                error=None,
                agent_source="PRO",
                matched_claim="productivity increases"
            ),
            SourceVerification(
                url="https://bad-science.fake/caffeine-myth",
                status="NOT_FOUND",
                confidence=0.0,
                content_preview=None,
                error="404 Not Found",
                agent_source="CON",
                matched_claim=None
            ),
            SourceVerification(
                url="https://example.com/neutral-study",
                status="VERIFIED",
                confidence=0.75,
                content_preview="Neutral content...",
                error=None,
                agent_source="CON",
                matched_claim="no effect"
            )
        ]
        
        response = fact_checker.generate(sample_debate_state)
        
        assert response['agent'] == "FACT_CHECKER"
        assert len(response['verification_results']) == 4
        assert response['verified_count'] == 3
        assert response['hallucinated_count'] == 1
        assert response['verification_rate'] == 0.75
        assert 0.0 <= response['overall_confidence'] <= 1.0
    
    def test_generate_with_no_sources(self, fact_checker):
        """Test generate() with empty sources"""
        empty_state = DebateState(
            claim="Test claim",
            round=3,
            pro_arguments=["Argument"],
            con_arguments=["Argument"],
            pro_sources=[[]],
            con_sources=[[]],
            verdict=None,
            confidence=None
        )
        
        response = fact_checker.generate(empty_state)
        
        assert response['agent'] == "FACT_CHECKER"
        assert len(response['verification_results']) == 0
        assert response['verified_count'] == 0
        assert response['hallucinated_count'] == 0
        assert response['verification_rate'] == 1.0  # No sources = perfect


class TestHallucinationDetection:
    """Test hallucination detection capabilities"""
    
    def test_hallucination_counting(self, fact_checker):
        """Test that hallucinations are correctly counted"""
        results = [
            {"status": "VERIFIED", "confidence": 0.9},
            {"status": "VERIFIED", "confidence": 0.85},
            {"status": "NOT_FOUND", "confidence": 0.0},  # Hallucinated
            {"status": "CONTENT_MISMATCH", "confidence": 0.30},  # Content doesn't match
            {"status": "VERIFIED", "confidence": 0.75},
        ]
        
        hallucinated = sum(1 for r in results if r['status'] in ["NOT_FOUND", "CONTENT_MISMATCH", "TIMEOUT"])
        assert hallucinated == 2
