"""
Unit tests for ConAgent
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

import pytest
from unittest.mock import Mock
from src.agents.con_agent import ConAgent
from src.core.models import DebateState, AgentResponse
from src.llm.client import FreeLLMClient

@pytest.fixture
def mock_client():
    client = Mock(spec=FreeLLMClient)
    client.call_structured.return_value = AgentResponse(
        agent="CON",
        round=1,
        argument="This is a strong opposing argument for the claim.",
        sources=["https://example.com/source2"]
    )
    return client

@pytest.fixture
def con_agent(mock_client):
    return ConAgent(mock_client)

@pytest.fixture
def state_with_pro_argument():
    state = DebateState(
        claim="Test claim",
        round=1,
        pro_arguments=["Pro argument"],
        pro_sources=[["https://example.com/source1"]]
    )
    return state

def test_con_agent_initialization(con_agent):
    assert con_agent.role == "CON"

def test_con_agent_generates_response(con_agent, state_with_pro_argument):
    response = con_agent.generate(state_with_pro_argument)
    assert response.agent == "CON"
    assert len(response.argument) > 20

def test_con_agent_challenges_pro(con_agent, state_with_pro_argument):
    response = con_agent.generate(state_with_pro_argument)
    assert response.argument != state_with_pro_argument.pro_arguments[0]

if __name__ == "__main__":
    pytest.main([__file__, "-v"])