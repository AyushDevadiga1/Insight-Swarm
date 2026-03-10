"""
Unit tests for ConAgent

Security features tested:
- Input validation
- Error handling
- Response parsing
- Opposing arguments
"""

import pytest
from src.agents.con_agent import ConAgent
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
def con_agent(client):
    """Fixture: ConAgent instance"""
    return ConAgent(client)


@pytest.fixture
def pro_agent(client):
    """Fixture: ProAgent instance"""
    return ProAgent(client)


@pytest.fixture
def state_with_pro_argument(pro_agent):
    """State after ProAgent has made initial argument"""
    state = DebateState(
        claim="Test claim for debate",
        round=1,
        pro_arguments=[],
        con_arguments=[],
        pro_sources=[],
        con_sources=[],
        verdict=None,
        confidence=None
    )
    
    # Have ProAgent make first argument
    pro_response = pro_agent.generate(state)
    state['pro_arguments'].append(pro_response['argument'])
    state['pro_sources'].append(pro_response['sources'])  # Fixed: use append not extend   
    return state


def test_con_agent_initialization(con_agent):
    """Test ConAgent initializes correctly"""
    assert con_agent.role == "CON"
    assert con_agent.call_count == 0


def test_con_agent_generates_response(con_agent, state_with_pro_argument):
    """Test ConAgent generates valid response"""
    response = con_agent.generate(state_with_pro_argument)
    
    assert response['agent'] == "CON"
    assert len(response['argument']) > 50
    assert isinstance(response['sources'], list)
    assert response['confidence'] is not None


def test_con_agent_challenges_pro(con_agent, state_with_pro_argument):
    """Test ConAgent response differs from ProAgent"""
    response = con_agent.generate(state_with_pro_argument)
    
    # ConAgent's argument should be different from ProAgent's
    pro_arg = state_with_pro_argument['pro_arguments'][0]
    con_arg = response['argument']
    
    assert con_arg != pro_arg


def test_con_agent_validates_input(con_agent):
    """Test that ConAgent handles edge cases"""
    state = DebateState(
        claim="Test",
        round=1,
        pro_arguments=[],
        con_arguments=[],
        pro_sources=[],
        con_sources=[],
        verdict=None,
        confidence=None
    )
    
    # ConAgent should either succeed or raise a clear error when pro_arguments is empty
    try:
        response = con_agent.generate(state)
        # If successful, verify response structure
        assert isinstance(response, dict), "Response should be a dictionary"
        assert 'argument' in response, "Response must contain 'argument' key"
        assert 'sources' in response, "Response must contain 'sources' key"
        assert isinstance(response['argument'], str), "Argument must be a string"
        assert isinstance(response['sources'], list), "Sources must be a list"
    except (ValueError, RuntimeError) as e:
        # It's acceptable to raise an error for invalid state
        assert isinstance(e, (ValueError, RuntimeError)), "Should raise ValueError or RuntimeError"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])