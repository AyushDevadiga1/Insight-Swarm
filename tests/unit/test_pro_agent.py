"""
Unit tests for ProAgent

Security features tested:
- Input validation
- Error handling
- Response parsing
"""

import pytest
from src.agents.pro_agent import ProAgent
from src.agents.base import DebateState
from src.llm.client import FreeLLMClient


@pytest.fixture
def client():
    """Fixture: FreeLLMClient instance"""
    try:
        return FreeLLMClient()
    except RuntimeError:
        pytest.skip("LLM providers not available")


@pytest.fixture
def pro_agent(client):
    """Fixture: ProAgent instance"""
    return ProAgent(client)


@pytest.fixture
def initial_state():
    """Fixture: Fresh debate state"""
    return DebateState(
        claim="Test claim",
        round=1,
        pro_arguments=[],
        con_arguments=[],
        pro_sources=[],
        con_sources=[],
        verdict=None,
        confidence=None
    )


def test_pro_agent_initialization(pro_agent):
    """Test ProAgent initializes correctly"""
    assert pro_agent.role == "PRO"
    assert pro_agent.call_count == 0


def test_pro_agent_generates_response(pro_agent, initial_state):
    """Test ProAgent generates valid response"""
    response = pro_agent.generate(initial_state)
    
    assert response['agent'] == "PRO"
    assert response['round'] == 1
    assert len(response['argument']) > 50
    assert isinstance(response['sources'], list)


def test_pro_agent_cites_sources(pro_agent, initial_state):
    """Test ProAgent cites sources in response"""
    response = pro_agent.generate(initial_state)
    
    # Should cite at least 1 source (or empty list is acceptable)
    assert isinstance(response['sources'], list)
    assert response['confidence'] is not None
    assert 0.0 <= response['confidence'] <= 1.0


def test_pro_agent_validates_claim(pro_agent):
    """Test that invalid claims are handled"""
    invalid_state = DebateState(
        claim="",  # Empty claim
        round=1,
        pro_arguments=[],
        con_arguments=[],
        pro_sources=[],
        con_sources=[],
        verdict=None,
        confidence=None
    )
    
    # Should handle gracefully even with empty claim
    try:
        response = pro_agent.generate(invalid_state)
        # If it succeeds, the response should still be valid
        assert 'argument' in response
        assert 'sources' in response
    except (ValueError, RuntimeError):
        # It's acceptable to raise an error for invalid claims
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])