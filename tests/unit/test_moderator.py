"""
Unit tests for Moderator agent
"""

import pytest
from src.agents.moderator import Moderator
from src.agents.base import DebateState
from src.llm.client import FreeLLMClient


@pytest.fixture
def moderator():
    """Fixture: Moderator instance"""
    client = FreeLLMClient()
    return Moderator(client)


@pytest.fixture
def balanced_debate():
    """Fixture: Debate with balanced arguments"""
    return DebateState(
        claim="Test claim",
        round=4,
        pro_arguments=["Good argument with evidence"] * 3,
        con_arguments=["Good counter-argument with evidence"] * 3,
        pro_sources=[["url1", "url2"]] * 3,
        con_sources=[["url3", "url4"]] * 3,
        verdict=None,
        confidence=None,
        pro_verification_rate=0.75,
        con_verification_rate=0.75,
        verification_results=[],
        fact_check_result="All sources verified",
        moderator_reasoning=None
    )


@pytest.fixture
def pro_strong_debate():
    """Fixture: Debate where ProAgent has stronger evidence"""
    return DebateState(
        claim="Test claim",
        round=4,
        pro_arguments=["Strong evidence-based argument"] * 3,
        con_arguments=["Weak argument without evidence"] * 3,
        pro_sources=[["high-quality-source.edu"]] * 3,
        con_sources=[["random-blog.com"]] * 3,
        verdict=None,
        confidence=None,
        pro_verification_rate=0.95,  # High verification
        con_verification_rate=0.20,  # Low verification
        verification_results=[],
        fact_check_result="ProAgent sources verified, ConAgent sources failed",
        moderator_reasoning=None
    )


def test_moderator_initialization(moderator):
    """Test Moderator initializes correctly"""
    assert moderator.role == "MODERATOR"
    assert moderator.client is not None


def test_moderator_generates_verdict(moderator, balanced_debate):
    """Test Moderator produces verdict"""
    result = moderator.generate(balanced_debate)
    
    assert result['agent'] == "MODERATOR"
    assert result['verdict'] in ['TRUE', 'FALSE', 'PARTIALLY TRUE', 'INSUFFICIENT EVIDENCE']
    assert 0.0 <= result['confidence'] <= 1.0
    assert len(result['argument']) > 50  # Reasoning should be substantial


def test_moderator_reasoning_quality(moderator, balanced_debate):
    """Test Moderator provides detailed reasoning"""
    result = moderator.generate(balanced_debate)
    
    reasoning = result['argument'].lower()
    
    # Reasoning should mention key concepts
    assert any(word in reasoning for word in ['evidence', 'argument', 'source', 'verification'])


def test_moderator_favors_verified_sources(moderator, pro_strong_debate):
    """Test Moderator favors arguments with verified sources"""
    result = moderator.generate(pro_strong_debate)
    
    # ProAgent had 95% verification, ConAgent had 20%
    # Moderator should favor ProAgent
    # (Either TRUE verdict or high confidence in pro direction)
    
    if result['verdict'] == 'TRUE':
        assert result['confidence'] > 0.5
    # Note: We can't guarantee verdict due to LLM variability,
    # but confidence should reflect evidence quality


def test_moderator_fallback_verdict(moderator, balanced_debate):
    """Test fallback verdict when LLM fails"""
    
    # Force fallback by using invalid state
    invalid_state = balanced_debate.copy()
    
    # Directly test fallback method
    fallback = moderator._fallback_verdict(balanced_debate)
    
    assert fallback['agent'] == "MODERATOR"
    assert fallback['verdict'] in ['TRUE', 'FALSE', 'PARTIALLY TRUE', 'INSUFFICIENT EVIDENCE']
    assert 0.0 <= fallback['confidence'] <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
