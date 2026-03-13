"""
Unit tests for ProAgent
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

import pytest
from unittest.mock import Mock
from src.agents.pro_agent import ProAgent
from src.core.models import DebateState, AgentResponse
from src.llm.client import FreeLLMClient

@pytest.fixture
def mock_client():
    client = Mock(spec=FreeLLMClient)
    client.call_structured.return_value = AgentResponse(
        agent="PRO",
        round=1,
        argument="This is a strong argument for the claim with sources.",
        sources=["https://example.com/source1"]
    )
    return client

@pytest.fixture
def pro_agent(mock_client):
    return ProAgent(mock_client)

@pytest.fixture
def initial_state():
    return DebateState(claim="Test claim", round=1)

def test_pro_agent_initialization(pro_agent):
    assert pro_agent.role == "PRO"

def test_pro_agent_generates_response(pro_agent, initial_state):
    response = pro_agent.generate(initial_state)
    assert response.agent == "PRO"
    assert "argument" in response.argument.lower()
    assert len(response.sources) > 0

def test_pro_agent_validates_claim(pro_agent):
    invalid_state = DebateState(claim="")
    response = pro_agent.generate(invalid_state)
    assert hasattr(response, 'argument')

if __name__ == "__main__":
    pytest.main([__file__, "-v"])